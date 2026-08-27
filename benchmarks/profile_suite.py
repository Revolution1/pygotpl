"""Capture deterministic, stack-sampling, and allocation hotspot evidence."""

from __future__ import annotations

import argparse
import asyncio
import cProfile
import gc
import json
import platform
import sys
import threading
import time
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from types import FrameType
from typing import Any, TypedDict

from benchmarks.compare import PROJECT_ROOT, load_benchmark, prepare_python_operation
from gotpl import Template
from gotpl.compile import compile_template
from gotpl.parse import parse_template

try:
    _tracemalloc: Any | None = import_module("tracemalloc")
except ModuleNotFoundError:
    _tracemalloc = None


class DeterministicEntry(TypedDict):
    location: str
    function: str
    calls: int
    self_seconds: float
    cumulative_seconds: float
    self_fraction: float


class DeterministicProfile(TypedDict):
    profiler: str
    iterations: int
    total_seconds: float
    entries: list[DeterministicEntry]


class SamplingEntry(TypedDict):
    location: str
    function: str
    samples: int
    fraction: float


class SamplingProfile(TypedDict):
    profiler: str
    requested_seconds: float
    elapsed_seconds: float
    interval_seconds: float
    samples: int
    completed_operations: int
    entries: list[SamplingEntry]


class AllocationEntry(TypedDict):
    location: str
    size_bytes: int
    blocks: int
    size_bytes_per_operation: float
    blocks_per_operation: float


class AllocationProfile(TypedDict):
    profiler: str
    iterations: int
    peak_traced_bytes: int
    retained_traced_bytes: int
    retained_traced_blocks: int
    entries: list[AllocationEntry]


class WorkloadProfile(TypedDict):
    id: str
    deterministic: DeterministicProfile
    sampling: SamplingProfile
    allocation: AllocationProfile


class ProfileConfiguration(TypedDict):
    deterministic_iterations: int
    sampling_seconds: float
    sampling_interval: float
    allocation_iterations: int
    top: int


class ProfileSuite(TypedDict):
    schema_version: int
    environment: dict[str, str]
    configuration: ProfileConfiguration
    workloads: list[WorkloadProfile]


@dataclass(slots=True)
class _Workload:
    id: str
    operation: Callable[[], object]
    cleanup: Callable[[], None] | None = None


def _display_location(filename: str, line: int) -> str:
    path = Path(filename)
    try:
        displayed = path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()
    except ValueError:
        displayed = path.name
    return f"{displayed}:{line}"


def _profile_deterministic(
    operation: Callable[[], object],
    *,
    iterations: int,
    top: int,
) -> DeterministicProfile:
    profiler = cProfile.Profile()
    gc_was_enabled = gc.isenabled()
    gc.disable()
    try:
        profiler.enable()
        for _ in range(iterations):
            operation()
        profiler.disable()
    finally:
        if gc_was_enabled:
            gc.enable()
    raw_entries = profiler.getstats()
    total_seconds = sum(entry.inlinetime for entry in raw_entries)
    entries: list[DeterministicEntry] = []
    for entry in sorted(raw_entries, key=lambda item: item.inlinetime, reverse=True):
        code = entry.code
        if isinstance(code, str):
            location = "built-in"
            function = code
        else:
            location = _display_location(code.co_filename, code.co_firstlineno)
            function = code.co_name
        entries.append(
            DeterministicEntry(
                location=location,
                function=function,
                calls=entry.callcount,
                self_seconds=entry.inlinetime,
                cumulative_seconds=entry.totaltime,
                self_fraction=(
                    entry.inlinetime / total_seconds if total_seconds else 0.0
                ),
            )
        )
        if len(entries) == top:
            break
    return DeterministicProfile(
        profiler="cProfile-deterministic",
        iterations=iterations,
        total_seconds=total_seconds,
        entries=entries,
    )


def _sample_frame(frame: FrameType | None) -> tuple[str, str]:
    if frame is None:
        return "unavailable", "unavailable"
    return (
        _display_location(frame.f_code.co_filename, frame.f_code.co_firstlineno),
        frame.f_code.co_name,
    )


def _profile_sampling(
    operation: Callable[[], object],
    *,
    minimum_operations: int,
    seconds: float,
    interval: float,
    top: int,
) -> SamplingProfile:
    target_thread = threading.get_ident()
    stop = threading.Event()
    ready = threading.Event()
    counts: Counter[tuple[str, str]] = Counter()

    def sample() -> None:
        ready.set()
        while not stop.is_set():
            counts[_sample_frame(sys._current_frames().get(target_thread))] += 1
            stop.wait(interval)

    sampler = threading.Thread(target=sample, name="gotpl-profile-sampler")
    sampler.start()
    ready.wait()
    started = time.perf_counter()
    deadline = started + seconds
    completed = 0
    try:
        while completed < minimum_operations or time.perf_counter() < deadline:
            operation()
            completed += 1
    finally:
        stop.set()
        sampler.join()
    elapsed = time.perf_counter() - started
    sample_count = sum(counts.values())
    entries = [
        SamplingEntry(
            location=location,
            function=function,
            samples=count,
            fraction=count / sample_count,
        )
        for (location, function), count in counts.most_common(top)
    ]
    return SamplingProfile(
        profiler="stdlib-thread-stack-sampler",
        requested_seconds=seconds,
        elapsed_seconds=elapsed,
        interval_seconds=interval,
        samples=sample_count,
        completed_operations=completed,
        entries=entries,
    )


def _allocation_location(traceback: Any) -> str:
    frame = traceback[0]
    return _display_location(frame.filename, frame.lineno)


def _profile_allocation(
    operation: Callable[[], object],
    *,
    iterations: int,
    top: int,
) -> AllocationProfile:
    tracemalloc = _tracemalloc
    if tracemalloc is None:
        raise RuntimeError("profile suite requires tracemalloc")
    if tracemalloc.is_tracing():
        raise RuntimeError("profile suite requires tracemalloc to be stopped")
    gc.collect()
    tracemalloc.start()
    try:
        operation()
        gc.collect()
        before = tracemalloc.take_snapshot()
        baseline, _ = tracemalloc.get_traced_memory()
        tracemalloc.reset_peak()
        result: object = None
        for _ in range(iterations):
            result = operation()
        _, peak = tracemalloc.get_traced_memory()
        after = tracemalloc.take_snapshot()
        statistics = after.compare_to(before, "lineno")
        positive = [item for item in statistics if item.size_diff > 0]
        retained_bytes = sum(item.size_diff for item in positive)
        retained_blocks = sum(max(0, item.count_diff) for item in positive)
        entries = [
            AllocationEntry(
                location=_allocation_location(item.traceback),
                size_bytes=item.size_diff,
                blocks=max(0, item.count_diff),
                size_bytes_per_operation=item.size_diff / iterations,
                blocks_per_operation=max(0, item.count_diff) / iterations,
            )
            for item in positive[:top]
        ]
        del result, before, after
    finally:
        tracemalloc.stop()
    return AllocationProfile(
        profiler="tracemalloc-line-diff",
        iterations=iterations,
        peak_traced_bytes=max(0, peak - baseline),
        retained_traced_bytes=retained_bytes,
        retained_traced_blocks=retained_blocks,
        entries=entries,
    )


def _build_workloads() -> list[_Workload]:
    fixture_dir = PROJECT_ROOT / "benchmarks" / "fixtures"
    parser_fixture = load_benchmark(fixture_dir / "parser.json")
    parser_source = parser_fixture["request"]["template"]
    workloads = [
        _Workload(
            "parser/parse-compile",
            lambda: compile_template(parse_template(parser_source)),
        )
    ]
    for filename in ("text_render.json", "html_render.json", "sprig_render.json"):
        fixture = load_benchmark(fixture_dir / filename)
        operation, _ = prepare_python_operation(fixture)
        workloads.append(_Workload(fixture["id"], operation))

    async def scheduled_identity(value: object) -> object:
        await asyncio.sleep(0)
        return value

    template = Template(
        "{{identity .}}",
        functions={"identity": scheduled_identity},
    )
    loop = asyncio.new_event_loop()

    def render_async() -> str:
        return loop.run_until_complete(template.render_async("value"))

    workloads.append(
        _Workload(
            "async/scheduled-callback",
            render_async,
            loop.close,
        )
    )
    return workloads


def build_profile_suite(
    *,
    iterations: int = 20_000,
    sampling_seconds: float = 0.5,
    sampling_interval: float = 0.001,
    allocation_iterations: int = 25,
    top: int = 20,
) -> ProfileSuite:
    """Profile every representative workload with three independent methods."""

    if (
        iterations < 1
        or sampling_seconds <= 0
        or sampling_interval <= 0
        or allocation_iterations < 1
        or top < 1
    ):
        raise ValueError("invalid profile suite configuration")
    if _tracemalloc is None:
        raise RuntimeError("profile suite requires tracemalloc")
    workloads = _build_workloads()
    results: list[WorkloadProfile] = []
    try:
        for workload in workloads:
            workload.operation()
            results.append(
                WorkloadProfile(
                    id=workload.id,
                    deterministic=_profile_deterministic(
                        workload.operation,
                        iterations=iterations,
                        top=top,
                    ),
                    sampling=_profile_sampling(
                        workload.operation,
                        minimum_operations=iterations,
                        seconds=sampling_seconds,
                        interval=sampling_interval,
                        top=top,
                    ),
                    allocation=_profile_allocation(
                        workload.operation,
                        iterations=allocation_iterations,
                        top=top,
                    ),
                )
            )
    finally:
        for workload in workloads:
            if workload.cleanup is not None:
                workload.cleanup()
    return ProfileSuite(
        schema_version=1,
        environment={
            "python": platform.python_version(),
            "platform": platform.platform(),
            "machine": platform.machine(),
        },
        configuration=ProfileConfiguration(
            deterministic_iterations=iterations,
            sampling_seconds=sampling_seconds,
            sampling_interval=sampling_interval,
            allocation_iterations=allocation_iterations,
            top=top,
        ),
        workloads=results,
    )


def main() -> None:
    """Run the comprehensive profiler suite from the command line."""

    parser = argparse.ArgumentParser()
    parser.add_argument("--iterations", type=int, default=20_000)
    parser.add_argument("--sampling-seconds", type=float, default=0.5)
    parser.add_argument("--sampling-interval", type=float, default=0.001)
    parser.add_argument("--allocation-iterations", type=int, default=25)
    parser.add_argument("--top", type=int, default=20)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    report = build_profile_suite(
        iterations=arguments.iterations,
        sampling_seconds=arguments.sampling_seconds,
        sampling_interval=arguments.sampling_interval,
        allocation_iterations=arguments.allocation_iterations,
        top=arguments.top,
    )
    encoded = json.dumps(report, indent=2, sort_keys=True)
    if arguments.output is None:
        print(encoded)
    else:
        arguments.output.write_text(encoded + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
