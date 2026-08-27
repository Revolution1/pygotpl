"""Run a shared warm-render benchmark against Python and Go."""

from __future__ import annotations

import argparse
import gc
import hashlib
import json
import os
import platform
import shutil
import statistics
import subprocess
import time
from collections.abc import Callable
from io import StringIO
from pathlib import Path
from typing import Literal, NotRequired, TypedDict, cast

from gotpl import HTMLTemplate, Template
from gotpl.funcs.sprig import text_func_map

PROJECT_ROOT = Path(__file__).parent.parent
DEFAULT_FIXTURE = Path(__file__).parent / "fixtures" / "literal.json"
GO_BENCHMARK = Path(__file__).parent / "go" / "main.go"

BenchmarkMode = Literal[
    "warm_render",
    "cold_render",
    "writer_render",
    "named_render",
]


class BenchmarkRequest(TypedDict):
    engine: str
    name: str
    template: str
    data: object
    function_profile: NotRequired[str]
    execute_template: NotRequired[str]


class BenchmarkFixture(TypedDict):
    schema_version: int
    id: str
    request: BenchmarkRequest
    mode: NotRequired[BenchmarkMode]
    warmup: int
    iterations: int


class BenchmarkResult(TypedDict):
    runtime: str
    case_id: str
    mode: str
    iterations: int
    ns_per_op: float
    allocations_per_op: float | None
    bytes_per_op: float | None


class WarmBenchmarkResult(BenchmarkResult):
    output_sha256: str


class ComparisonResult(TypedDict):
    schema_version: int
    case_id: str
    python: WarmBenchmarkResult
    go: WarmBenchmarkResult
    python_to_go_ratio: float
    environment: NotRequired[dict[str, str]]


class Distribution(TypedDict):
    values: list[float]
    median: float
    minimum: float
    maximum: float
    relative_standard_deviation: float


class SampledComparison(TypedDict):
    schema_version: int
    case_id: str
    samples: int
    python_ns_per_op: Distribution
    go_ns_per_op: Distribution
    python_to_go_ratio: Distribution
    go_allocations_per_op: Distribution
    go_bytes_per_op: Distribution
    output_sha256: str
    environment: dict[str, str]


def load_benchmark(path: Path) -> BenchmarkFixture:
    """Load and minimally validate a shared benchmark fixture."""

    raw: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"invalid benchmark fixture: {path}")
    raw_dict = cast(dict[str, object], raw)
    if raw_dict.get("schema_version") != 1:
        raise ValueError(f"invalid benchmark fixture: {path}")
    required = {"schema_version", "id", "request", "warmup", "iterations"}
    allowed = required | {"mode"}
    if not required <= set(raw_dict) or not set(raw_dict) <= allowed:
        raise ValueError(f"invalid benchmark fixture keys: {path}")
    raw_request = raw_dict["request"]
    if not isinstance(raw_request, dict):
        raise ValueError(f"unsupported benchmark request: {path}")
    request = cast(dict[str, object], raw_request)
    if request.get("engine") not in {"html", "text"}:
        raise ValueError(f"unsupported benchmark request: {path}")
    if raw_dict.get("mode", "warm_render") not in {
        "warm_render",
        "cold_render",
        "writer_render",
        "named_render",
    }:
        raise ValueError(f"unsupported benchmark mode: {path}")
    if raw_dict.get("mode") == "named_render" and not isinstance(
        request.get("execute_template"), str
    ):
        raise ValueError(f"named benchmark requires execute_template: {path}")
    if not isinstance(raw_dict["warmup"], int) or not isinstance(
        raw_dict["iterations"], int
    ):
        raise ValueError(f"invalid benchmark iteration counts: {path}")
    if raw_dict["warmup"] < 0 or raw_dict["iterations"] < 1:
        raise ValueError(f"invalid benchmark iteration range: {path}")
    return cast(BenchmarkFixture, raw_dict)


def measure_python(fixture: BenchmarkFixture) -> WarmBenchmarkResult:
    """Measure the fixture's declared rendering path through the public API."""

    operation, output_sha256 = prepare_python_operation(fixture)
    for _ in range(fixture["warmup"]):
        operation()

    gc_was_enabled = gc.isenabled()
    gc.disable()
    try:
        started = time.perf_counter_ns()
        for _ in range(fixture["iterations"]):
            operation()
        elapsed = time.perf_counter_ns() - started
    finally:
        if gc_was_enabled:
            gc.enable()

    return WarmBenchmarkResult(
        runtime="python",
        case_id=fixture["id"],
        mode=fixture.get("mode", "warm_render"),
        iterations=fixture["iterations"],
        ns_per_op=elapsed / fixture["iterations"],
        allocations_per_op=None,
        bytes_per_op=None,
        output_sha256=output_sha256,
    )


def prepare_python_operation(
    fixture: BenchmarkFixture,
) -> tuple[Callable[[], object], str]:
    """Build the public Python operation shared by timing and memory tools."""

    request = fixture["request"]
    profile = request.get("function_profile")
    if profile is None:
        functions = None
    elif profile == "sprig-v3.3.0":
        functions = text_func_map()
    else:
        raise ValueError(f"unsupported function profile: {profile}")
    template_type = HTMLTemplate if request["engine"] == "html" else Template
    mode = fixture.get("mode", "warm_render")
    execute_template = request.get("execute_template")

    def build_template() -> HTMLTemplate | Template:
        return template_type(
            request["template"],
            name=request["name"],
            functions=functions,
        )

    def render_string(template: HTMLTemplate | Template) -> str:
        if execute_template is None:
            return template.render(request["data"])
        return template.render_template(execute_template, request["data"])

    template = build_template()
    reference_output = render_string(template)
    writer = StringIO()

    def render_to_writer(current: HTMLTemplate | Template) -> None:
        writer.seek(0)
        writer.truncate(0)
        if execute_template is None:
            current.render_to(writer, request["data"])
        else:
            current.render_template_to(execute_template, writer, request["data"])

    def cold_operation() -> None:
        render_to_writer(build_template())

    def writer_operation() -> None:
        render_to_writer(template)

    def string_operation() -> str:
        return render_string(template)

    operation: Callable[[], object] = (
        cold_operation
        if mode == "cold_render"
        else writer_operation
        if mode == "writer_render"
        else string_operation
    )
    return (
        operation,
        hashlib.sha256(reference_output.encode()).hexdigest(),
    )


def measure_go(path: Path) -> WarmBenchmarkResult:
    """Measure the fixture with Go's matching native template engine."""

    if shutil.which("go") is None:
        raise RuntimeError("the Go benchmark requires the Go toolchain")
    environment = os.environ.copy()
    environment["GOCACHE"] = str(PROJECT_ROOT / ".cache" / "go-build")
    process = subprocess.run(
        ["go", "run", "main.go", str(path.resolve())],
        cwd=GO_BENCHMARK.parent,
        env=environment,
        capture_output=True,
        check=False,
        text=True,
        timeout=120,
    )
    if process.returncode != 0:
        raise RuntimeError(f"Go benchmark failed: {process.stderr}")
    raw: object = json.loads(process.stdout)
    if not isinstance(raw, dict):
        raise RuntimeError("Go benchmark returned an invalid result")
    raw_dict = cast(dict[str, object], raw)
    if raw_dict.get("runtime") != "go":
        raise RuntimeError("Go benchmark returned an invalid result")
    return cast(WarmBenchmarkResult, raw_dict)


def compare(path: Path) -> ComparisonResult:
    """Run both engines and return a machine-readable comparison."""

    fixture = load_benchmark(path)
    python_result = measure_python(fixture)
    go_result = measure_go(path)
    if python_result.get("output_sha256") != go_result.get("output_sha256"):
        raise RuntimeError(
            "Python and Go benchmark outputs differ; refusing to compare timings"
        )
    return ComparisonResult(
        schema_version=1,
        case_id=fixture["id"],
        python=python_result,
        go=go_result,
        python_to_go_ratio=python_result["ns_per_op"] / go_result["ns_per_op"],
    )


def summarize_measurements(values: list[float]) -> Distribution:
    """Summarize independent benchmark samples without hiding raw values."""

    if not values:
        raise ValueError("at least one benchmark sample is required")
    average = statistics.mean(values)
    return Distribution(
        values=values,
        median=statistics.median(values),
        minimum=min(values),
        maximum=max(values),
        relative_standard_deviation=(
            statistics.pstdev(values) / average if len(values) > 1 else 0.0
        ),
    )


def compare_samples(path: Path, *, samples: int = 7) -> SampledComparison:
    """Run independent comparisons and report their distribution."""

    if samples < 1:
        raise ValueError("benchmark sample count must be positive")
    runs = [compare(path) for _ in range(samples)]
    go_allocations = [run["go"]["allocations_per_op"] for run in runs]
    go_bytes = [run["go"]["bytes_per_op"] for run in runs]
    if any(value is None for value in (*go_allocations, *go_bytes)):
        raise RuntimeError("Go benchmark did not report allocation metrics")
    return SampledComparison(
        schema_version=1,
        case_id=runs[0]["case_id"],
        samples=samples,
        python_ns_per_op=summarize_measurements(
            [run["python"]["ns_per_op"] for run in runs]
        ),
        go_ns_per_op=summarize_measurements([run["go"]["ns_per_op"] for run in runs]),
        python_to_go_ratio=summarize_measurements(
            [run["python_to_go_ratio"] for run in runs]
        ),
        go_allocations_per_op=summarize_measurements(
            [cast(float, value) for value in go_allocations]
        ),
        go_bytes_per_op=summarize_measurements(
            [cast(float, value) for value in go_bytes]
        ),
        output_sha256=runs[0]["python"]["output_sha256"],
        environment={
            "python": platform.python_version(),
            "go": go_version(),
            "platform": platform.platform(),
            "machine": platform.machine(),
        },
    )


def go_version() -> str:
    """Return the current Go toolchain description for benchmark metadata."""

    process = subprocess.run(
        ["go", "version"],
        capture_output=True,
        check=False,
        text=True,
        timeout=10,
    )
    return process.stdout.strip() if process.returncode == 0 else "unavailable"


def main() -> None:
    """Run the command-line benchmark comparison."""

    parser = argparse.ArgumentParser()
    parser.add_argument("fixture", nargs="?", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--samples", type=int, default=1)
    arguments = parser.parse_args()
    result = (
        compare(arguments.fixture)
        if arguments.samples == 1
        else compare_samples(arguments.fixture, samples=arguments.samples)
    )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
