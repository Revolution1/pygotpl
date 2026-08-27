"""Estimate the generous upper bound from eliminating VM dispatch self time."""

from __future__ import annotations

import argparse
import cProfile
import gc
import json
import platform
from collections.abc import Callable
from pathlib import Path
from types import CodeType
from typing import TypedDict

from benchmarks.compare import (
    DEFAULT_FIXTURE,
    BenchmarkFixture,
    load_benchmark,
    prepare_python_operation,
)


class DispatchUpperBound(TypedDict):
    schema_version: int
    case_id: str
    mode: str
    iterations: int
    measurement: str
    total_seconds: float
    dispatcher_self_seconds: float
    dispatcher_self_fraction: float
    maximum_dispatch_only_speedup: float
    output_sha256: str
    environment: dict[str, str]


def _run(operation: Callable[[], object], iterations: int) -> None:
    for _ in range(iterations):
        operation()


def measure_dispatch_upper_bound(
    fixture: BenchmarkFixture,
    *,
    iterations: int = 5_000,
    warmup: int = 500,
) -> DispatchUpperBound:
    """Profile a real render and assume all dispatcher self time disappears."""

    if iterations < 1 or warmup < 0:
        raise ValueError("profile iteration counts are out of range")
    operation, output_sha256 = prepare_python_operation(fixture)
    _run(operation, warmup)

    profiler = cProfile.Profile()
    gc_was_enabled = gc.isenabled()
    gc.disable()
    try:
        profiler.enable()
        _run(operation, iterations)
        profiler.disable()
    finally:
        if gc_was_enabled:
            gc.enable()

    entries = profiler.getstats()
    total_seconds = sum(entry.inlinetime for entry in entries)
    dispatcher_self_seconds = sum(
        entry.inlinetime
        for entry in entries
        if isinstance(entry.code, CodeType)
        and entry.code.co_name == "_render_program_to"
        and entry.code.co_filename.endswith("/runtime/sync_vm.py")
    )
    if total_seconds <= 0 or dispatcher_self_seconds <= 0:
        raise RuntimeError("synchronous VM dispatcher was not present in the profile")
    fraction = dispatcher_self_seconds / total_seconds
    if fraction >= 1:
        raise RuntimeError("invalid dispatcher profile fraction")

    return DispatchUpperBound(
        schema_version=1,
        case_id=fixture["id"],
        mode=fixture.get("mode", "warm_render"),
        iterations=iterations,
        measurement="cprofile-dispatch-upper-bound",
        total_seconds=total_seconds,
        dispatcher_self_seconds=dispatcher_self_seconds,
        dispatcher_self_fraction=fraction,
        maximum_dispatch_only_speedup=1 / (1 - fraction),
        output_sha256=output_sha256,
        environment={
            "python": platform.python_version(),
            "platform": platform.platform(),
            "machine": platform.machine(),
        },
    )


def main() -> None:
    """Run the dispatcher upper-bound profile from the command line."""

    parser = argparse.ArgumentParser()
    parser.add_argument("fixture", nargs="?", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--iterations", type=int, default=5_000)
    parser.add_argument("--warmup", type=int, default=500)
    arguments = parser.parse_args()
    result = measure_dispatch_upper_bound(
        load_benchmark(arguments.fixture),
        iterations=arguments.iterations,
        warmup=arguments.warmup,
    )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
