"""Measure parser and compiler baselines against Go's native parser."""

from __future__ import annotations

import argparse
import gc
import json
import os
import platform
import shutil
import subprocess
import time
from collections.abc import Callable
from pathlib import Path
from typing import TypedDict, cast

from gotpl.compile import compile_template
from gotpl.parse import parse_template

from .compare import (
    BenchmarkFixture,
    BenchmarkResult,
    Distribution,
    go_version,
    load_benchmark,
    summarize_measurements,
)

PROJECT_ROOT = Path(__file__).parent.parent
DEFAULT_FIXTURE = Path(__file__).parent / "fixtures" / "parser.json"
GO_BENCHMARK = Path(__file__).parent / "go" / "parser.go"


class ParserComparison(TypedDict):
    schema_version: int
    case_id: str
    python_parse: BenchmarkResult
    python_compile: BenchmarkResult
    python_parse_compile: BenchmarkResult
    go_parse: BenchmarkResult
    python_parse_compile_to_go_parse_ratio: float


class SampledParserComparison(TypedDict):
    schema_version: int
    case_id: str
    samples: int
    python_parse_ns_per_op: Distribution
    python_compile_ns_per_op: Distribution
    python_parse_compile_ns_per_op: Distribution
    go_parse_ns_per_op: Distribution
    python_parse_compile_to_go_parse_ratio: Distribution
    go_allocations_per_op: Distribution
    go_bytes_per_op: Distribution
    environment: dict[str, str]


def _measure(
    fixture: BenchmarkFixture,
    mode: str,
    operation: Callable[[], object],
) -> BenchmarkResult:
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
    return BenchmarkResult(
        runtime="python",
        case_id=fixture["id"],
        mode=mode,
        iterations=fixture["iterations"],
        ns_per_op=elapsed / fixture["iterations"],
        allocations_per_op=None,
        bytes_per_op=None,
    )


def measure_python_parser(fixture: BenchmarkFixture) -> tuple[BenchmarkResult, ...]:
    """Measure isolated parse, isolated compile, and their cold combination."""

    source = fixture["request"]["template"]
    parsed = parse_template(source)
    parse_result = _measure(fixture, "parse", lambda: parse_template(source))
    compile_result = _measure(fixture, "compile", lambda: compile_template(parsed))
    combined_result = _measure(
        fixture,
        "parse_compile",
        lambda: compile_template(parse_template(source)),
    )
    return parse_result, compile_result, combined_result


def measure_go_parser(path: Path) -> BenchmarkResult:
    """Measure Go's combined parser/compiler phase on the shared fixture."""

    if shutil.which("go") is None:
        raise RuntimeError("the Go benchmark requires the Go toolchain")
    environment = os.environ.copy()
    environment["GOCACHE"] = str(PROJECT_ROOT / ".cache" / "go-build")
    process = subprocess.run(
        ["go", "run", str(GO_BENCHMARK), str(path)],
        cwd=PROJECT_ROOT,
        env=environment,
        capture_output=True,
        check=False,
        text=True,
        timeout=120,
    )
    if process.returncode != 0:
        raise RuntimeError(f"Go parser benchmark failed: {process.stderr}")
    raw: object = json.loads(process.stdout)
    if not isinstance(raw, dict):
        raise RuntimeError("Go parser benchmark returned an invalid result")
    raw_dict = cast(dict[str, object], raw)
    if raw_dict.get("runtime") != "go":
        raise RuntimeError("Go parser benchmark returned an invalid result")
    return cast(BenchmarkResult, raw_dict)


def compare_parser(path: Path) -> ParserComparison:
    """Return Python phase baselines and the Go parse comparison."""

    fixture = load_benchmark(path)
    parse_result, compile_result, combined_result = measure_python_parser(fixture)
    go_result = measure_go_parser(path)
    return ParserComparison(
        schema_version=1,
        case_id=fixture["id"],
        python_parse=parse_result,
        python_compile=compile_result,
        python_parse_compile=combined_result,
        go_parse=go_result,
        python_parse_compile_to_go_parse_ratio=(
            combined_result["ns_per_op"] / go_result["ns_per_op"]
        ),
    )


def compare_parser_samples(path: Path, *, samples: int = 7) -> SampledParserComparison:
    """Run independent parser comparisons and preserve every distribution."""

    if samples < 1:
        raise ValueError("parser benchmark sample count must be positive")
    runs = [compare_parser(path) for _ in range(samples)]
    go_allocations = [run["go_parse"]["allocations_per_op"] for run in runs]
    go_bytes = [run["go_parse"]["bytes_per_op"] for run in runs]
    if any(value is None for value in (*go_allocations, *go_bytes)):
        raise RuntimeError("Go parser benchmark did not report allocation metrics")
    return SampledParserComparison(
        schema_version=1,
        case_id=runs[0]["case_id"],
        samples=samples,
        python_parse_ns_per_op=summarize_measurements(
            [run["python_parse"]["ns_per_op"] for run in runs]
        ),
        python_compile_ns_per_op=summarize_measurements(
            [run["python_compile"]["ns_per_op"] for run in runs]
        ),
        python_parse_compile_ns_per_op=summarize_measurements(
            [run["python_parse_compile"]["ns_per_op"] for run in runs]
        ),
        go_parse_ns_per_op=summarize_measurements(
            [run["go_parse"]["ns_per_op"] for run in runs]
        ),
        python_parse_compile_to_go_parse_ratio=summarize_measurements(
            [run["python_parse_compile_to_go_parse_ratio"] for run in runs]
        ),
        go_allocations_per_op=summarize_measurements(
            [cast(float, value) for value in go_allocations]
        ),
        go_bytes_per_op=summarize_measurements(
            [cast(float, value) for value in go_bytes]
        ),
        environment={
            "python": platform.python_version(),
            "go": go_version(),
            "platform": platform.platform(),
            "machine": platform.machine(),
        },
    )


def main() -> None:
    """Run the parser/compiler baseline comparison."""

    parser = argparse.ArgumentParser()
    parser.add_argument("fixture", nargs="?", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--samples", type=int, default=1)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    result = (
        compare_parser(arguments.fixture)
        if arguments.samples == 1
        else compare_parser_samples(arguments.fixture, samples=arguments.samples)
    )
    encoded = json.dumps(result, indent=2, sort_keys=True)
    if arguments.output is None:
        print(encoded)
    else:
        arguments.output.write_text(encoded + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
