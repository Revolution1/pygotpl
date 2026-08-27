"""Measure Python render memory without conflating it with Go allocations."""

from __future__ import annotations

import argparse
import gc
import json
import platform
from importlib import import_module
from pathlib import Path
from typing import Any, TypedDict

from benchmarks.compare import (
    DEFAULT_FIXTURE,
    BenchmarkFixture,
    Distribution,
    load_benchmark,
    prepare_python_operation,
    summarize_measurements,
)

try:
    _tracemalloc: Any | None = import_module("tracemalloc")
except ModuleNotFoundError:
    _tracemalloc = None


class PythonMemoryResult(TypedDict):
    schema_version: int
    runtime: str
    case_id: str
    mode: str
    samples: int
    measurement: str
    peak_traced_bytes_per_render: Distribution
    retained_traced_bytes_per_render: Distribution
    retained_traced_blocks_per_render: Distribution
    output_sha256: str
    environment: dict[str, str]


def _retained_delta(
    before: Any,
    after: Any,
) -> tuple[float, float]:
    statistics = after.compare_to(before, "traceback")
    return (
        float(max(0, sum(item.size_diff for item in statistics))),
        float(max(0, sum(item.count_diff for item in statistics))),
    )


def tracemalloc_available() -> bool:
    """Return whether this interpreter provides a working tracemalloc module."""

    return _tracemalloc is not None


def measure_python_memory(
    fixture: BenchmarkFixture,
    *,
    samples: int = 25,
) -> PythonMemoryResult:
    """Measure single-render traced peaks and retained snapshot deltas."""

    if samples < 1:
        raise ValueError("memory benchmark sample count must be positive")
    tracemalloc = _tracemalloc
    if tracemalloc is None:
        raise RuntimeError("memory benchmark requires tracemalloc on this interpreter")
    if tracemalloc.is_tracing():
        raise RuntimeError("memory benchmark requires tracemalloc to be stopped")

    operation, output_sha256 = prepare_python_operation(fixture)
    for _ in range(fixture["warmup"]):
        operation()

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

    return PythonMemoryResult(
        schema_version=1,
        runtime="python",
        case_id=fixture["id"],
        mode=fixture.get("mode", "warm_render"),
        samples=samples,
        measurement="tracemalloc-single-render",
        peak_traced_bytes_per_render=summarize_measurements(peaks),
        retained_traced_bytes_per_render=summarize_measurements(retained_bytes),
        retained_traced_blocks_per_render=summarize_measurements(retained_blocks),
        output_sha256=output_sha256,
        environment={
            "python": platform.python_version(),
            "platform": platform.platform(),
            "machine": platform.machine(),
        },
    )


def main() -> None:
    """Run a Python memory benchmark from the command line."""

    parser = argparse.ArgumentParser()
    parser.add_argument("fixture", nargs="?", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--samples", type=int, default=25)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    result = measure_python_memory(
        load_benchmark(arguments.fixture),
        samples=arguments.samples,
    )
    encoded = json.dumps(result, indent=2, sort_keys=True)
    if arguments.output is None:
        print(encoded)
    else:
        arguments.output.write_text(encoded + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
