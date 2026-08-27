"""Compare equivalent gotpl and Jinja public rendering operations."""

from __future__ import annotations

import argparse
import asyncio
import gc
import hashlib
import json
import platform
import time
from collections.abc import Awaitable, Callable, Mapping, Sequence
from functools import partial
from importlib import import_module
from importlib.metadata import version
from pathlib import Path
from typing import Any, Literal, NotRequired, TypedDict, cast

from jinja2 import DictLoader, Environment, StrictUndefined
from jinja2 import Template as JinjaTemplate

from benchmarks.compare import Distribution, summarize_measurements
from gotpl import HTMLTemplate, Template

PROJECT_ROOT = Path(__file__).parent.parent
JINJA_FIXTURE_DIR = Path(__file__).parent / "jinja" / "fixtures"
DEFAULT_FIXTURES = tuple(sorted(JINJA_FIXTURE_DIR.glob("*.json")))

try:
    _tracemalloc: Any | None = import_module("tracemalloc")
except ModuleNotFoundError:
    _tracemalloc = None


class JinjaFixture(TypedDict):
    schema_version: int
    id: str
    engine: Literal["text", "html"]
    gotpl_template: str
    jinja_template: str
    data: dict[str, object]
    expected_output: str
    function_profile: NotRequired[Literal["identity"]]
    warmup: int
    iterations: int
    cold_iterations: int
    cache_iterations: int


class PairDistribution(TypedDict):
    gotpl_ns_per_op: Distribution
    jinja_ns_per_op: Distribution
    gotpl_to_jinja_ratio: Distribution


class MemoryPair(TypedDict):
    samples: int
    measurement: str
    gotpl_peak_traced_bytes_per_render: Distribution
    jinja_peak_traced_bytes_per_render: Distribution
    gotpl_retained_traced_bytes_per_render: Distribution
    jinja_retained_traced_bytes_per_render: Distribution
    gotpl_retained_traced_blocks_per_render: Distribution
    jinja_retained_traced_blocks_per_render: Distribution


class FixtureComparison(TypedDict):
    case_id: str
    samples: int
    warm_iterations: int
    cold_iterations: int
    output_sha256: str
    warm_render: PairDistribution
    cold_render: PairDistribution
    memory: NotRequired[MemoryPair]


class CacheComparison(TypedDict):
    case_id: str
    samples: int
    iterations: int
    cache_size: int
    auto_reload: bool
    enabled_ns_per_op: Distribution
    disabled_ns_per_op: Distribution
    enabled_to_disabled_ratio: Distribution


class AsyncComparison(TypedDict):
    case_id: str
    samples: int
    iterations: int
    concurrency: int
    sync_function: PairDistribution
    async_sync_function: PairDistribution
    immediate_coroutine: PairDistribution
    scheduled_coroutine: PairDistribution
    concurrent_coroutines: PairDistribution


class JinjaConfiguration(TypedDict):
    jinja_optimized: bool
    jinja_auto_reload: bool
    jinja_cache_size: int
    html_policy: str


JinjaReport = TypedDict(
    "JinjaReport",
    {
        "schema_version": int,
        "samples": int,
        "environment": dict[str, str],
        "configuration": JinjaConfiguration,
        "fixtures": list[FixtureComparison],
        "cache": CacheComparison,
        "async": AsyncComparison,
    },
)


_REQUIRED_FIXTURE_KEYS = {
    "schema_version",
    "id",
    "engine",
    "gotpl_template",
    "jinja_template",
    "data",
    "expected_output",
    "warmup",
    "iterations",
    "cold_iterations",
    "cache_iterations",
}
_ALLOWED_FIXTURE_KEYS = _REQUIRED_FIXTURE_KEYS | {"function_profile"}


def load_jinja_fixture(path: Path) -> JinjaFixture:
    """Load and validate an equivalent-work Jinja benchmark fixture."""

    raw: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"invalid Jinja benchmark fixture: {path}")
    fixture = cast(dict[str, object], raw)
    if (
        fixture.get("schema_version") != 1
        or not set(fixture) >= _REQUIRED_FIXTURE_KEYS
        or not set(fixture) <= _ALLOWED_FIXTURE_KEYS
        or fixture.get("engine") not in {"text", "html"}
        or fixture.get("function_profile") not in {None, "identity"}
        or not isinstance(fixture.get("id"), str)
        or not isinstance(fixture.get("gotpl_template"), str)
        or not isinstance(fixture.get("jinja_template"), str)
        or not isinstance(fixture.get("data"), dict)
        or not isinstance(fixture.get("expected_output"), str)
        or not isinstance(fixture.get("warmup"), int)
        or not isinstance(fixture.get("iterations"), int)
        or not isinstance(fixture.get("cold_iterations"), int)
        or not isinstance(fixture.get("cache_iterations"), int)
        or cast(int, fixture["warmup"]) < 0
        or cast(int, fixture["iterations"]) < 1
        or cast(int, fixture["cold_iterations"]) < 1
        or cast(int, fixture["cache_iterations"]) < 1
    ):
        raise ValueError(f"invalid Jinja benchmark fixture: {path}")
    data = cast(dict[object, object], fixture["data"])
    if any(not isinstance(key, str) for key in data):
        raise ValueError(f"invalid Jinja benchmark fixture data: {path}")
    return cast(JinjaFixture, fixture)


def _sync_identity(value: object) -> object:
    return value


async def _immediate_identity(value: object) -> object:
    return value


async def _scheduled_identity(value: object) -> object:
    await asyncio.sleep(0)
    return value


def _function_map(
    fixture: JinjaFixture,
    identity: Callable[[object], object] = _sync_identity,
) -> dict[str, Callable[[object], object]]:
    if fixture.get("function_profile") is None:
        return {}
    return {"identity": identity}


def _gotpl_template(
    fixture: JinjaFixture,
    functions: Mapping[str, Callable[..., object]],
) -> Template | HTMLTemplate:
    template_type = HTMLTemplate if fixture["engine"] == "html" else Template
    return template_type(fixture["gotpl_template"], functions=functions)


def _jinja_environment(
    fixture: JinjaFixture,
    functions: Mapping[str, Callable[..., object]],
    *,
    enable_async: bool = False,
    cache_size: int = 400,
    loader: DictLoader | None = None,
) -> Environment:
    environment = Environment(
        autoescape=fixture["engine"] == "html",
        auto_reload=False,
        cache_size=cache_size,
        enable_async=enable_async,
        loader=loader,
        optimized=True,
        undefined=StrictUndefined,
    )
    environment.globals.update(functions)
    return environment


def _jinja_template(
    fixture: JinjaFixture,
    functions: Mapping[str, Callable[..., object]],
    *,
    enable_async: bool = False,
) -> JinjaTemplate:
    return _jinja_environment(
        fixture,
        functions,
        enable_async=enable_async,
    ).from_string(fixture["jinja_template"])


def _render_jinja(template: JinjaTemplate, data: Mapping[str, object]) -> str:
    return template.render(**data)


def _render_cold_gotpl(
    fixture: JinjaFixture,
    functions: Mapping[str, Callable[..., object]],
) -> str:
    return _gotpl_template(fixture, functions).render(fixture["data"])


def _render_cold_jinja(
    fixture: JinjaFixture,
    functions: Mapping[str, Callable[..., object]],
) -> str:
    return _render_jinja(
        _jinja_template(fixture, functions),
        fixture["data"],
    )


async def _render_jinja_async(
    template: JinjaTemplate, data: Mapping[str, object]
) -> str:
    return await template.render_async(**data)


def _validate_output(fixture: JinjaFixture, *outputs: str) -> str:
    expected = fixture["expected_output"]
    if any(output != expected for output in outputs):
        raise RuntimeError(
            f"benchmark output differs for {fixture['id']!r}; refusing to time it"
        )
    return hashlib.sha256(expected.encode()).hexdigest()


def _time_sync(
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


async def _time_async(
    operation: Callable[[], Awaitable[object]],
    *,
    iterations: int,
    warmup: int,
) -> float:
    for _ in range(warmup):
        await operation()
    gc_was_enabled = gc.isenabled()
    gc.disable()
    try:
        started = time.perf_counter_ns()
        for _ in range(iterations):
            await operation()
        elapsed = time.perf_counter_ns() - started
    finally:
        if gc_was_enabled:
            gc.enable()
    return elapsed / iterations


async def _time_concurrent(
    operation: Callable[[], Awaitable[object]],
    *,
    iterations: int,
    warmup: int,
    concurrency: int,
) -> float:
    for _ in range(warmup):
        await operation()
    gc_was_enabled = gc.isenabled()
    gc.disable()
    try:
        started = time.perf_counter_ns()
        completed = 0
        while completed < iterations:
            width = min(concurrency, iterations - completed)
            await asyncio.gather(*(operation() for _ in range(width)))
            completed += width
        elapsed = time.perf_counter_ns() - started
    finally:
        if gc_was_enabled:
            gc.enable()
    return elapsed / iterations


def _pair(gotpl_values: list[float], jinja_values: list[float]) -> PairDistribution:
    return PairDistribution(
        gotpl_ns_per_op=summarize_measurements(gotpl_values),
        jinja_ns_per_op=summarize_measurements(jinja_values),
        gotpl_to_jinja_ratio=summarize_measurements(
            [
                gotpl_value / jinja_value
                for gotpl_value, jinja_value in zip(
                    gotpl_values, jinja_values, strict=True
                )
            ]
        ),
    )


def measure_fixture_samples(
    fixture: JinjaFixture,
    *,
    samples: int = 7,
) -> FixtureComparison:
    """Measure equivalent warm and cold public operations in both engines."""

    if samples < 1:
        raise ValueError("Jinja benchmark sample count must be positive")
    gotpl_warm: list[float] = []
    jinja_warm: list[float] = []
    gotpl_cold: list[float] = []
    jinja_cold: list[float] = []
    output_sha256 = ""
    functions = _function_map(fixture)
    for _ in range(samples):
        gotpl_template = _gotpl_template(fixture, functions)
        jinja_template = _jinja_template(fixture, functions)
        data = fixture["data"]
        output_sha256 = _validate_output(
            fixture,
            gotpl_template.render(data),
            _render_jinja(jinja_template, data),
        )
        gotpl_warm.append(
            _time_sync(
                partial(gotpl_template.render, data),
                iterations=fixture["iterations"],
                warmup=fixture["warmup"],
            )
        )
        jinja_warm.append(
            _time_sync(
                partial(_render_jinja, jinja_template, data),
                iterations=fixture["iterations"],
                warmup=fixture["warmup"],
            )
        )
        gotpl_cold.append(
            _time_sync(
                partial(_render_cold_gotpl, fixture, functions),
                iterations=fixture["cold_iterations"],
                warmup=fixture["warmup"],
            )
        )
        jinja_cold.append(
            _time_sync(
                partial(_render_cold_jinja, fixture, functions),
                iterations=fixture["cold_iterations"],
                warmup=fixture["warmup"],
            )
        )
    return FixtureComparison(
        case_id=fixture["id"],
        samples=samples,
        warm_iterations=fixture["iterations"],
        cold_iterations=fixture["cold_iterations"],
        output_sha256=output_sha256,
        warm_render=_pair(gotpl_warm, jinja_warm),
        cold_render=_pair(gotpl_cold, jinja_cold),
    )


def measure_cache_samples(
    fixture: JinjaFixture,
    *,
    samples: int = 7,
    iterations: int | None = None,
    warmup: int | None = None,
) -> CacheComparison:
    """Measure Jinja loader-cache behavior separately from render ratios."""

    if samples < 1:
        raise ValueError("Jinja cache sample count must be positive")
    resolved_iterations = fixture["iterations"] if iterations is None else iterations
    resolved_warmup = fixture["warmup"] if warmup is None else warmup
    if resolved_iterations < 1 or resolved_warmup < 0:
        raise ValueError("Jinja cache benchmark counts are out of range")
    enabled_values: list[float] = []
    disabled_values: list[float] = []
    functions = _function_map(fixture)
    data = fixture["data"]
    loader = DictLoader({"benchmark": fixture["jinja_template"]})
    for _ in range(samples):
        enabled = _jinja_environment(
            fixture,
            functions,
            cache_size=400,
            loader=loader,
        )
        disabled = _jinja_environment(
            fixture,
            functions,
            cache_size=0,
            loader=loader,
        )

        def render(environment: Environment) -> str:
            return _render_jinja(environment.get_template("benchmark"), data)

        _validate_output(fixture, render(enabled), render(disabled))
        enabled_values.append(
            _time_sync(
                partial(render, enabled),
                iterations=resolved_iterations,
                warmup=resolved_warmup,
            )
        )
        disabled_values.append(
            _time_sync(
                partial(render, disabled),
                iterations=resolved_iterations,
                warmup=resolved_warmup,
            )
        )
    return CacheComparison(
        case_id=fixture["id"],
        samples=samples,
        iterations=resolved_iterations,
        cache_size=400,
        auto_reload=False,
        enabled_ns_per_op=summarize_measurements(enabled_values),
        disabled_ns_per_op=summarize_measurements(disabled_values),
        enabled_to_disabled_ratio=summarize_measurements(
            [
                enabled / disabled
                for enabled, disabled in zip(
                    enabled_values, disabled_values, strict=True
                )
            ]
        ),
    )


async def _measure_async_once(
    fixture: JinjaFixture,
    *,
    iterations: int,
    warmup: int,
    concurrency: int,
) -> dict[str, tuple[float, float]]:
    data = fixture["data"]

    def build_pair(
        function: Callable[[object], object],
        *,
        enable_async: bool,
    ) -> tuple[Template | HTMLTemplate, JinjaTemplate]:
        functions = _function_map(fixture, function)
        return (
            _gotpl_template(fixture, functions),
            _jinja_template(fixture, functions, enable_async=enable_async),
        )

    sync_gotpl, sync_jinja = build_pair(_sync_identity, enable_async=False)
    async_sync_gotpl, async_sync_jinja = build_pair(_sync_identity, enable_async=True)
    immediate_gotpl, immediate_jinja = build_pair(
        _immediate_identity, enable_async=True
    )
    scheduled_gotpl, scheduled_jinja = build_pair(
        _scheduled_identity, enable_async=True
    )
    _validate_output(
        fixture,
        sync_gotpl.render(data),
        _render_jinja(sync_jinja, data),
        await async_sync_gotpl.render_async(data),
        await _render_jinja_async(async_sync_jinja, data),
        await immediate_gotpl.render_async(data),
        await _render_jinja_async(immediate_jinja, data),
        await scheduled_gotpl.render_async(data),
        await _render_jinja_async(scheduled_jinja, data),
    )

    sync = (
        _time_sync(
            lambda: sync_gotpl.render(data),
            iterations=iterations,
            warmup=warmup,
        ),
        _time_sync(
            lambda: _render_jinja(sync_jinja, data),
            iterations=iterations,
            warmup=warmup,
        ),
    )
    async_sync = (
        await _time_async(
            lambda: async_sync_gotpl.render_async(data),
            iterations=iterations,
            warmup=warmup,
        ),
        await _time_async(
            lambda: _render_jinja_async(async_sync_jinja, data),
            iterations=iterations,
            warmup=warmup,
        ),
    )
    immediate = (
        await _time_async(
            lambda: immediate_gotpl.render_async(data),
            iterations=iterations,
            warmup=warmup,
        ),
        await _time_async(
            lambda: _render_jinja_async(immediate_jinja, data),
            iterations=iterations,
            warmup=warmup,
        ),
    )
    scheduled = (
        await _time_async(
            lambda: scheduled_gotpl.render_async(data),
            iterations=iterations,
            warmup=warmup,
        ),
        await _time_async(
            lambda: _render_jinja_async(scheduled_jinja, data),
            iterations=iterations,
            warmup=warmup,
        ),
    )
    concurrent = (
        await _time_concurrent(
            lambda: scheduled_gotpl.render_async(data),
            iterations=iterations,
            warmup=warmup,
            concurrency=concurrency,
        ),
        await _time_concurrent(
            lambda: _render_jinja_async(scheduled_jinja, data),
            iterations=iterations,
            warmup=warmup,
            concurrency=concurrency,
        ),
    )
    return {
        "sync_function": sync,
        "async_sync_function": async_sync,
        "immediate_coroutine": immediate,
        "scheduled_coroutine": scheduled,
        "concurrent_coroutines": concurrent,
    }


async def measure_async_samples(
    fixture: JinjaFixture,
    *,
    samples: int = 7,
    iterations: int = 20_000,
    warmup: int = 1_000,
    concurrency: int = 32,
) -> AsyncComparison:
    """Compare equivalent sync and async function boundaries."""

    if (
        samples < 1
        or iterations < 1
        or warmup < 0
        or concurrency < 1
        or fixture.get("function_profile") != "identity"
    ):
        raise ValueError("invalid Jinja async benchmark configuration")
    runs = [
        await _measure_async_once(
            fixture,
            iterations=iterations,
            warmup=warmup,
            concurrency=concurrency,
        )
        for _ in range(samples)
    ]

    def comparison(name: str) -> PairDistribution:
        return _pair(
            [run[name][0] for run in runs],
            [run[name][1] for run in runs],
        )

    return AsyncComparison(
        case_id=fixture["id"],
        samples=samples,
        iterations=iterations,
        concurrency=concurrency,
        sync_function=comparison("sync_function"),
        async_sync_function=comparison("async_sync_function"),
        immediate_coroutine=comparison("immediate_coroutine"),
        scheduled_coroutine=comparison("scheduled_coroutine"),
        concurrent_coroutines=comparison("concurrent_coroutines"),
    )


def _retained_delta(before: Any, after: Any) -> tuple[float, float]:
    statistics = after.compare_to(before, "traceback")
    return (
        float(max(0, sum(item.size_diff for item in statistics))),
        float(max(0, sum(item.count_diff for item in statistics))),
    )


def _measure_memory_operation(
    operation: Callable[[], object],
    *,
    samples: int,
) -> tuple[list[float], list[float], list[float]]:
    tracemalloc = _tracemalloc
    if tracemalloc is None:
        raise RuntimeError("Jinja memory benchmark requires tracemalloc")
    peaks: list[float] = []
    retained_bytes: list[float] = []
    retained_blocks: list[float] = []
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
            size_delta, count_delta = _retained_delta(before, after)
            peaks.append(float(max(0, peak - baseline)))
            retained_bytes.append(size_delta)
            retained_blocks.append(count_delta)
            del result, before, after
    finally:
        tracemalloc.stop()
    return peaks, retained_bytes, retained_blocks


def measure_memory_pair(
    fixture: JinjaFixture,
    *,
    samples: int = 25,
) -> MemoryPair:
    """Compare warm-render traced memory with metric names distinct from Go."""

    if samples < 1:
        raise ValueError("Jinja memory benchmark sample count must be positive")
    tracemalloc = _tracemalloc
    if tracemalloc is None:
        raise RuntimeError("Jinja memory benchmark requires tracemalloc")
    if tracemalloc.is_tracing():
        raise RuntimeError("Jinja memory benchmark requires tracemalloc to be stopped")
    functions = _function_map(fixture)
    gotpl_template = _gotpl_template(fixture, functions)
    jinja_template = _jinja_template(fixture, functions)
    data = fixture["data"]
    _validate_output(
        fixture,
        gotpl_template.render(data),
        _render_jinja(jinja_template, data),
    )
    gotpl_peak, gotpl_retained, gotpl_blocks = _measure_memory_operation(
        lambda: gotpl_template.render(data), samples=samples
    )
    jinja_peak, jinja_retained, jinja_blocks = _measure_memory_operation(
        lambda: _render_jinja(jinja_template, data), samples=samples
    )
    return MemoryPair(
        samples=samples,
        measurement="tracemalloc-single-render",
        gotpl_peak_traced_bytes_per_render=summarize_measurements(gotpl_peak),
        jinja_peak_traced_bytes_per_render=summarize_measurements(jinja_peak),
        gotpl_retained_traced_bytes_per_render=summarize_measurements(gotpl_retained),
        jinja_retained_traced_bytes_per_render=summarize_measurements(jinja_retained),
        gotpl_retained_traced_blocks_per_render=summarize_measurements(gotpl_blocks),
        jinja_retained_traced_blocks_per_render=summarize_measurements(jinja_blocks),
    )


async def build_jinja_report(
    paths: Sequence[Path] = DEFAULT_FIXTURES,
    *,
    samples: int = 7,
    iterations: int | None = None,
    warmup: int | None = None,
    memory_samples: int = 25,
    concurrency: int = 32,
) -> JinjaReport:
    """Build the complete versioned Python-engine comparison report."""

    if not paths:
        raise ValueError("Jinja report requires at least one fixture")
    if samples < 1 or memory_samples < 0:
        raise ValueError("Jinja report sample counts are out of range")
    fixtures: list[JinjaFixture] = []
    for path in paths:
        fixture = load_jinja_fixture(path)
        if iterations is not None:
            fixture["iterations"] = iterations
            fixture["cold_iterations"] = iterations
            fixture["cache_iterations"] = iterations
        if warmup is not None:
            fixture["warmup"] = warmup
        fixtures.append(fixture)
    results = [
        measure_fixture_samples(fixture, samples=samples) for fixture in fixtures
    ]
    if memory_samples:
        for fixture, result in zip(fixtures, results, strict=True):
            result["memory"] = measure_memory_pair(fixture, samples=memory_samples)
    cache_fixture = next(
        (fixture for fixture in fixtures if fixture.get("function_profile") is None),
        fixtures[0],
    )
    callback_fixture = load_jinja_fixture(JINJA_FIXTURE_DIR / "callbacks.json")
    resolved_iterations = (
        callback_fixture["iterations"] if iterations is None else iterations
    )
    resolved_warmup = callback_fixture["warmup"] if warmup is None else warmup
    return {
        "schema_version": 1,
        "samples": samples,
        "environment": {
            "python": platform.python_version(),
            "gotpl": version("gotpl"),
            "jinja": version("Jinja2"),
            "platform": platform.platform(),
            "machine": platform.machine(),
        },
        "configuration": {
            "jinja_optimized": True,
            "jinja_auto_reload": False,
            "jinja_cache_size": 400,
            "html_policy": "gotpl-contextual-vs-jinja-autoescape",
        },
        "fixtures": results,
        "cache": measure_cache_samples(
            cache_fixture,
            samples=samples,
            iterations=(
                cache_fixture["cache_iterations"] if iterations is None else iterations
            ),
            warmup=(cache_fixture["warmup"] if warmup is None else warmup),
        ),
        "async": await measure_async_samples(
            callback_fixture,
            samples=samples,
            iterations=resolved_iterations,
            warmup=resolved_warmup,
            concurrency=concurrency,
        ),
    }


def main() -> None:
    """Run the complete Jinja comparison from the command line."""

    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", action="append", type=Path, dest="fixtures")
    parser.add_argument("--samples", type=int, default=7)
    parser.add_argument("--iterations", type=int)
    parser.add_argument("--warmup", type=int)
    parser.add_argument("--memory-samples", type=int, default=25)
    parser.add_argument("--concurrency", type=int, default=32)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    report = asyncio.run(
        build_jinja_report(
            DEFAULT_FIXTURES if arguments.fixtures is None else arguments.fixtures,
            samples=arguments.samples,
            iterations=arguments.iterations,
            warmup=arguments.warmup,
            memory_samples=arguments.memory_samples,
            concurrency=arguments.concurrency,
        )
    )
    encoded = json.dumps(report, indent=2, sort_keys=True)
    if arguments.output is None:
        print(encoded)
    else:
        arguments.output.write_text(encoded + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
