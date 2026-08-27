"""Compare gotpl with capability-matched Mako and Chameleon operations."""

from __future__ import annotations

import argparse
import gc
import hashlib
import json
import platform
import time
from collections.abc import Callable, Mapping, Sequence
from importlib import import_module
from importlib.metadata import version
from pathlib import Path
from typing import Any, Literal, NotRequired, TypedDict, cast

from chameleon import PageTemplate, PageTextTemplate
from mako.template import Template as MakoTemplate

from benchmarks.compare import Distribution, summarize_measurements
from gotpl import HTMLTemplate, Template

PYTHON_ENGINE_FIXTURE_DIR = Path(__file__).parent / "python_engines" / "fixtures"
DEFAULT_FIXTURES = tuple(sorted(PYTHON_ENGINE_FIXTURE_DIR.glob("*.json")))

try:
    _tracemalloc: Any | None = import_module("tracemalloc")
except ModuleNotFoundError:
    _tracemalloc = None


class ExpectedOutput(TypedDict):
    gotpl: str
    mako: str
    chameleon: str


class PythonEngineFixture(TypedDict):
    schema_version: int
    id: str
    engine: Literal["text", "html"]
    gotpl_template: str
    mako_template: str
    chameleon_template: str
    data: dict[str, object]
    expected_output: ExpectedOutput
    warmup: int
    iterations: int
    cold_iterations: int


class EnginePhase(TypedDict):
    gotpl_ns_per_op: Distribution
    mako_ns_per_op: Distribution
    chameleon_ns_per_op: Distribution
    gotpl_to_mako_ratio: Distribution
    gotpl_to_chameleon_ratio: Distribution


class EngineMemory(TypedDict):
    samples: int
    measurement: str
    gotpl_peak_traced_bytes_per_render: Distribution
    mako_peak_traced_bytes_per_render: Distribution
    chameleon_peak_traced_bytes_per_render: Distribution
    gotpl_retained_traced_bytes_per_render: Distribution
    mako_retained_traced_bytes_per_render: Distribution
    chameleon_retained_traced_bytes_per_render: Distribution


class EngineFixtureResult(TypedDict):
    case_id: str
    samples: int
    warm_iterations: int
    cold_iterations: int
    output_sha256: dict[str, str]
    warm_render: EnginePhase
    cold_render: EnginePhase
    memory: NotRequired[EngineMemory]


class EngineCapabilities(TypedDict):
    mako_async: Literal["unsupported"]
    chameleon_async: Literal["unsupported"]
    mako_html_escaping: str
    chameleon_html_escaping: str
    html_comparison: str


class PythonEngineReport(TypedDict):
    schema_version: int
    samples: int
    environment: dict[str, str]
    capabilities: EngineCapabilities
    fixtures: list[EngineFixtureResult]


_REQUIRED_KEYS = {
    "schema_version",
    "id",
    "engine",
    "gotpl_template",
    "mako_template",
    "chameleon_template",
    "data",
    "expected_output",
    "warmup",
    "iterations",
    "cold_iterations",
}


def load_python_engine_fixture(path: Path) -> PythonEngineFixture:
    """Load and validate a Mako and Chameleon comparison fixture."""

    raw: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"invalid Python-engine benchmark fixture: {path}")
    fixture = cast(dict[str, object], raw)
    expected = fixture.get("expected_output")
    if (
        set(fixture) != _REQUIRED_KEYS
        or fixture.get("schema_version") != 1
        or fixture.get("engine") not in {"text", "html"}
        or not isinstance(fixture.get("id"), str)
        or not isinstance(fixture.get("gotpl_template"), str)
        or not isinstance(fixture.get("mako_template"), str)
        or not isinstance(fixture.get("chameleon_template"), str)
        or not isinstance(fixture.get("data"), dict)
        or not isinstance(expected, dict)
        or set(expected) != {"gotpl", "mako", "chameleon"}
        or any(not isinstance(value, str) for value in expected.values())
        or not isinstance(fixture.get("warmup"), int)
        or not isinstance(fixture.get("iterations"), int)
        or not isinstance(fixture.get("cold_iterations"), int)
        or cast(int, fixture["warmup"]) < 0
        or cast(int, fixture["iterations"]) < 1
        or cast(int, fixture["cold_iterations"]) < 1
    ):
        raise ValueError(f"invalid Python-engine benchmark fixture: {path}")
    data = cast(dict[object, object], fixture["data"])
    if any(not isinstance(key, str) for key in data):
        raise ValueError(f"invalid Python-engine benchmark fixture data: {path}")
    return cast(PythonEngineFixture, fixture)


def _gotpl_template(fixture: PythonEngineFixture) -> Template | HTMLTemplate:
    template_type = HTMLTemplate if fixture["engine"] == "html" else Template
    return template_type(fixture["gotpl_template"])


def _mako_template(fixture: PythonEngineFixture) -> MakoTemplate:
    filters = ["h"] if fixture["engine"] == "html" else ["str"]
    return MakoTemplate(
        fixture["mako_template"],
        default_filters=filters,
        strict_undefined=True,
    )


def _chameleon_template(fixture: PythonEngineFixture) -> object:
    template_type = PageTemplate if fixture["engine"] == "html" else PageTextTemplate
    return template_type(fixture["chameleon_template"], auto_reload=False)


def _render_mako(template: MakoTemplate, data: Mapping[str, object]) -> str:
    return cast(str, template.render(**data))


def _render_chameleon(template: object, data: Mapping[str, object]) -> str:
    return cast(Callable[..., str], template)(**data)


def _validate_outputs(
    fixture: PythonEngineFixture,
    gotpl_output: str,
    mako_output: str,
    chameleon_output: str,
) -> dict[str, str]:
    outputs = {
        "gotpl": gotpl_output,
        "mako": mako_output,
        "chameleon": chameleon_output,
    }
    if outputs != fixture["expected_output"]:
        raise RuntimeError(
            f"benchmark output differs for {fixture['id']!r}; refusing to time it"
        )
    return {
        name: hashlib.sha256(output.encode()).hexdigest()
        for name, output in outputs.items()
    }


def _time_operation(
    operation: Callable[[], object],
    *,
    iterations: int,
    warmup: int,
) -> float:
    for _ in range(warmup):
        operation()
    gc_was_enabled = gc.isenabled()
    gc.disable()
    try:
        started = time.perf_counter_ns()
        for _ in range(iterations):
            operation()
        elapsed = time.perf_counter_ns() - started
    finally:
        if gc_was_enabled:
            gc.enable()
    return elapsed / iterations


def _phase(
    gotpl_values: list[float],
    mako_values: list[float],
    chameleon_values: list[float],
) -> EnginePhase:
    return EnginePhase(
        gotpl_ns_per_op=summarize_measurements(gotpl_values),
        mako_ns_per_op=summarize_measurements(mako_values),
        chameleon_ns_per_op=summarize_measurements(chameleon_values),
        gotpl_to_mako_ratio=summarize_measurements(
            [
                gotpl_value / mako_value
                for gotpl_value, mako_value in zip(
                    gotpl_values, mako_values, strict=True
                )
            ]
        ),
        gotpl_to_chameleon_ratio=summarize_measurements(
            [
                gotpl_value / chameleon_value
                for gotpl_value, chameleon_value in zip(
                    gotpl_values, chameleon_values, strict=True
                )
            ]
        ),
    )


def measure_engine_fixture_samples(
    fixture: PythonEngineFixture,
    *,
    samples: int = 7,
) -> EngineFixtureResult:
    """Measure warm and cold public rendering across all three engines."""

    if samples < 1:
        raise ValueError("Python-engine benchmark sample count must be positive")
    warm = {name: [] for name in ("gotpl", "mako", "chameleon")}
    cold = {name: [] for name in ("gotpl", "mako", "chameleon")}
    output_sha256: dict[str, str] = {}
    data = fixture["data"]
    for _ in range(samples):
        gotpl_template = _gotpl_template(fixture)
        mako_template = _mako_template(fixture)
        chameleon_template = _chameleon_template(fixture)
        output_sha256 = _validate_outputs(
            fixture,
            gotpl_template.render(data),
            _render_mako(mako_template, data),
            _render_chameleon(chameleon_template, data),
        )
        warm["gotpl"].append(
            _time_operation(
                lambda template=gotpl_template: template.render(data),
                iterations=fixture["iterations"],
                warmup=fixture["warmup"],
            )
        )
        warm["mako"].append(
            _time_operation(
                lambda template=mako_template: _render_mako(template, data),
                iterations=fixture["iterations"],
                warmup=fixture["warmup"],
            )
        )
        warm["chameleon"].append(
            _time_operation(
                lambda template=chameleon_template: _render_chameleon(template, data),
                iterations=fixture["iterations"],
                warmup=fixture["warmup"],
            )
        )
        cold["gotpl"].append(
            _time_operation(
                lambda: _gotpl_template(fixture).render(data),
                iterations=fixture["cold_iterations"],
                warmup=fixture["warmup"],
            )
        )
        cold["mako"].append(
            _time_operation(
                lambda: _render_mako(_mako_template(fixture), data),
                iterations=fixture["cold_iterations"],
                warmup=fixture["warmup"],
            )
        )
        cold["chameleon"].append(
            _time_operation(
                lambda: _render_chameleon(_chameleon_template(fixture), data),
                iterations=fixture["cold_iterations"],
                warmup=fixture["warmup"],
            )
        )
    return EngineFixtureResult(
        case_id=fixture["id"],
        samples=samples,
        warm_iterations=fixture["iterations"],
        cold_iterations=fixture["cold_iterations"],
        output_sha256=output_sha256,
        warm_render=_phase(warm["gotpl"], warm["mako"], warm["chameleon"]),
        cold_render=_phase(cold["gotpl"], cold["mako"], cold["chameleon"]),
    )


def _retained_delta(before: Any, after: Any) -> float:
    return float(
        max(0, sum(item.size_diff for item in after.compare_to(before, "traceback")))
    )


def _memory_values(
    operation: Callable[[], object],
    *,
    samples: int,
) -> tuple[list[float], list[float]]:
    tracemalloc = _tracemalloc
    if tracemalloc is None:
        raise RuntimeError("Python-engine memory benchmark requires tracemalloc")
    peaks: list[float] = []
    retained: list[float] = []
    tracemalloc.start()
    try:
        operation()
        for _ in range(samples):
            gc.collect()
            before = tracemalloc.take_snapshot()
            baseline, _ = tracemalloc.get_traced_memory()
            tracemalloc.reset_peak()
            result = operation()
            _, peak = tracemalloc.get_traced_memory()
            after = tracemalloc.take_snapshot()
            peaks.append(float(max(0, peak - baseline)))
            retained.append(_retained_delta(before, after))
            del result, before, after
    finally:
        tracemalloc.stop()
    return peaks, retained


def measure_engine_memory(
    fixture: PythonEngineFixture,
    *,
    samples: int = 25,
) -> EngineMemory:
    """Measure warm-render traced memory for the supplementary engines."""

    if samples < 1:
        raise ValueError("Python-engine memory sample count must be positive")
    tracemalloc = _tracemalloc
    if tracemalloc is None:
        raise RuntimeError("Python-engine memory benchmark requires tracemalloc")
    if tracemalloc.is_tracing():
        raise RuntimeError(
            "Python-engine memory benchmark requires tracemalloc to be stopped"
        )
    data = fixture["data"]
    gotpl_template = _gotpl_template(fixture)
    mako_template = _mako_template(fixture)
    chameleon_template = _chameleon_template(fixture)
    _validate_outputs(
        fixture,
        gotpl_template.render(data),
        _render_mako(mako_template, data),
        _render_chameleon(chameleon_template, data),
    )
    gotpl_peak, gotpl_retained = _memory_values(
        lambda: gotpl_template.render(data), samples=samples
    )
    mako_peak, mako_retained = _memory_values(
        lambda: _render_mako(mako_template, data), samples=samples
    )
    chameleon_peak, chameleon_retained = _memory_values(
        lambda: _render_chameleon(chameleon_template, data), samples=samples
    )
    return EngineMemory(
        samples=samples,
        measurement="tracemalloc-single-render",
        gotpl_peak_traced_bytes_per_render=summarize_measurements(gotpl_peak),
        mako_peak_traced_bytes_per_render=summarize_measurements(mako_peak),
        chameleon_peak_traced_bytes_per_render=summarize_measurements(chameleon_peak),
        gotpl_retained_traced_bytes_per_render=summarize_measurements(gotpl_retained),
        mako_retained_traced_bytes_per_render=summarize_measurements(mako_retained),
        chameleon_retained_traced_bytes_per_render=summarize_measurements(
            chameleon_retained
        ),
    )


def build_python_engine_report(
    paths: Sequence[Path] = DEFAULT_FIXTURES,
    *,
    samples: int = 7,
    iterations: int | None = None,
    warmup: int | None = None,
    memory_samples: int = 25,
) -> PythonEngineReport:
    """Build the complete supplementary Python-engine report."""

    if not paths or samples < 1 or memory_samples < 0:
        raise ValueError("invalid Python-engine report configuration")
    fixtures: list[PythonEngineFixture] = []
    for path in paths:
        fixture = load_python_engine_fixture(path)
        if iterations is not None:
            fixture["iterations"] = iterations
            fixture["cold_iterations"] = iterations
        if warmup is not None:
            fixture["warmup"] = warmup
        fixtures.append(fixture)
    results = [
        measure_engine_fixture_samples(fixture, samples=samples) for fixture in fixtures
    ]
    if memory_samples:
        for fixture, result in zip(fixtures, results, strict=True):
            result["memory"] = measure_engine_memory(fixture, samples=memory_samples)
    return PythonEngineReport(
        schema_version=1,
        samples=samples,
        environment={
            "python": platform.python_version(),
            "gotpl": version("gotpl"),
            "mako": version("Mako"),
            "chameleon": version("Chameleon"),
            "platform": platform.platform(),
            "machine": platform.machine(),
        },
        capabilities={
            "mako_async": "unsupported",
            "chameleon_async": "unsupported",
            "mako_html_escaping": "MarkupSafe h default filter in benchmark",
            "chameleon_html_escaping": "context-appropriate PageTemplate escaping",
            "html_comparison": "context-appropriate escaping",
        },
        fixtures=results,
    )


def main() -> None:
    """Run the supplementary Python-engine comparison from the command line."""

    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", action="append", type=Path, dest="fixtures")
    parser.add_argument("--samples", type=int, default=7)
    parser.add_argument("--iterations", type=int)
    parser.add_argument("--warmup", type=int)
    parser.add_argument("--memory-samples", type=int, default=25)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    report = build_python_engine_report(
        DEFAULT_FIXTURES if arguments.fixtures is None else arguments.fixtures,
        samples=arguments.samples,
        iterations=arguments.iterations,
        warmup=arguments.warmup,
        memory_samples=arguments.memory_samples,
    )
    encoded = json.dumps(report, indent=2, sort_keys=True)
    if arguments.output is None:
        print(encoded)
    else:
        arguments.output.write_text(encoded + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
