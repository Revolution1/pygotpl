"""Measure synchronous and asynchronous rendering overhead."""

from __future__ import annotations

import argparse
import asyncio
import gc
import json
import platform
import time
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import TypedDict

from benchmarks.compare import Distribution, summarize_measurements
from gotpl import Template


class AsyncBenchmarkResult(TypedDict):
    mode: str
    iterations: int
    ns_per_op: float
    operations_per_second: float


class AsyncComparison(TypedDict):
    schema_version: int
    sync_function: AsyncBenchmarkResult
    async_vm_sync_function: AsyncBenchmarkResult
    async_vm_immediate_coroutine: AsyncBenchmarkResult
    async_vm_scheduled_coroutine: AsyncBenchmarkResult
    async_vm_concurrent_coroutines: AsyncBenchmarkResult
    async_no_await_to_sync_ratio: float


class SampledAsyncComparison(TypedDict):
    schema_version: int
    samples: int
    iterations: int
    concurrency: int
    sync_function_ns_per_op: Distribution
    async_vm_sync_function_ns_per_op: Distribution
    async_vm_immediate_coroutine_ns_per_op: Distribution
    async_vm_scheduled_coroutine_ns_per_op: Distribution
    async_vm_concurrent_coroutines_ns_per_op: Distribution
    async_no_await_to_sync_ratio: Distribution
    environment: dict[str, str]


def _timed_result(mode: str, iterations: int, elapsed: int) -> AsyncBenchmarkResult:
    ns_per_op = elapsed / iterations
    return AsyncBenchmarkResult(
        mode=mode,
        iterations=iterations,
        ns_per_op=ns_per_op,
        operations_per_second=1_000_000_000 / ns_per_op,
    )


def _measure_sync(
    operation: Callable[[], object], iterations: int
) -> AsyncBenchmarkResult:
    started = time.perf_counter_ns()
    for _ in range(iterations):
        operation()
    return _timed_result("sync_function", iterations, time.perf_counter_ns() - started)


async def _measure_async(
    mode: str,
    operation: Callable[[], Awaitable[object]],
    iterations: int,
) -> AsyncBenchmarkResult:
    started = time.perf_counter_ns()
    for _ in range(iterations):
        await operation()
    return _timed_result(mode, iterations, time.perf_counter_ns() - started)


async def _measure_async_concurrent(
    operation: Callable[[], Awaitable[object]],
    iterations: int,
    concurrency: int,
) -> AsyncBenchmarkResult:
    started = time.perf_counter_ns()
    completed = 0
    while completed < iterations:
        width = min(concurrency, iterations - completed)
        await asyncio.gather(*(operation() for _ in range(width)))
        completed += width
    return _timed_result(
        "async_vm_concurrent_coroutines",
        iterations,
        time.perf_counter_ns() - started,
    )


async def measure_async_runtime(
    *,
    iterations: int = 20_000,
    warmup: int = 1_000,
    concurrency: int = 32,
) -> AsyncComparison:
    """Measure the sync path and three async function-boundary scenarios."""

    if iterations < 1 or warmup < 0 or concurrency < 1:
        raise ValueError(
            "benchmark counts require iterations and concurrency >= 1 and warmup >= 0"
        )

    def sync_identity(value: object) -> object:
        return value

    async def immediate_identity(value: object) -> object:
        return value

    async def scheduled_identity(value: object) -> object:
        await asyncio.sleep(0)
        return value

    source = "{{identity .}}"
    sync_template = Template(source, functions={"identity": sync_identity})
    immediate_template = Template(source, functions={"identity": immediate_identity})
    scheduled_template = Template(source, functions={"identity": scheduled_identity})
    for _ in range(warmup):
        sync_template.render("value")
        await sync_template.render_async("value")
        await immediate_template.render_async("value")
        await scheduled_template.render_async("value")

    gc_was_enabled = gc.isenabled()
    gc.disable()
    try:
        sync_result = _measure_sync(lambda: sync_template.render("value"), iterations)
        async_sync_result = await _measure_async(
            "async_vm_sync_function",
            lambda: sync_template.render_async("value"),
            iterations,
        )
        immediate_result = await _measure_async(
            "async_vm_immediate_coroutine",
            lambda: immediate_template.render_async("value"),
            iterations,
        )
        scheduled_result = await _measure_async(
            "async_vm_scheduled_coroutine",
            lambda: scheduled_template.render_async("value"),
            iterations,
        )
        concurrent_result = await _measure_async_concurrent(
            lambda: scheduled_template.render_async("value"),
            iterations,
            concurrency,
        )
    finally:
        if gc_was_enabled:
            gc.enable()

    return AsyncComparison(
        schema_version=1,
        sync_function=sync_result,
        async_vm_sync_function=async_sync_result,
        async_vm_immediate_coroutine=immediate_result,
        async_vm_scheduled_coroutine=scheduled_result,
        async_vm_concurrent_coroutines=concurrent_result,
        async_no_await_to_sync_ratio=(
            async_sync_result["ns_per_op"] / sync_result["ns_per_op"]
        ),
    )


async def measure_async_runtime_samples(
    *,
    samples: int = 7,
    iterations: int = 20_000,
    warmup: int = 1_000,
    concurrency: int = 32,
) -> SampledAsyncComparison:
    """Run independent async-runtime measurements and preserve distributions."""

    if samples < 1:
        raise ValueError("async benchmark sample count must be positive")
    runs = [
        await measure_async_runtime(
            iterations=iterations,
            warmup=warmup,
            concurrency=concurrency,
        )
        for _ in range(samples)
    ]
    return SampledAsyncComparison(
        schema_version=1,
        samples=samples,
        iterations=iterations,
        concurrency=concurrency,
        sync_function_ns_per_op=summarize_measurements(
            [run["sync_function"]["ns_per_op"] for run in runs]
        ),
        async_vm_sync_function_ns_per_op=summarize_measurements(
            [run["async_vm_sync_function"]["ns_per_op"] for run in runs]
        ),
        async_vm_immediate_coroutine_ns_per_op=summarize_measurements(
            [run["async_vm_immediate_coroutine"]["ns_per_op"] for run in runs]
        ),
        async_vm_scheduled_coroutine_ns_per_op=summarize_measurements(
            [run["async_vm_scheduled_coroutine"]["ns_per_op"] for run in runs]
        ),
        async_vm_concurrent_coroutines_ns_per_op=summarize_measurements(
            [run["async_vm_concurrent_coroutines"]["ns_per_op"] for run in runs]
        ),
        async_no_await_to_sync_ratio=summarize_measurements(
            [run["async_no_await_to_sync_ratio"] for run in runs]
        ),
        environment={
            "python": platform.python_version(),
            "platform": platform.platform(),
            "machine": platform.machine(),
        },
    )


def main() -> None:
    """Run the async runtime benchmark from the command line."""

    parser = argparse.ArgumentParser()
    parser.add_argument("--iterations", type=int, default=20_000)
    parser.add_argument("--warmup", type=int, default=1_000)
    parser.add_argument("--concurrency", type=int, default=32)
    parser.add_argument("--samples", type=int, default=1)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    result = asyncio.run(
        measure_async_runtime(
            iterations=arguments.iterations,
            warmup=arguments.warmup,
            concurrency=arguments.concurrency,
        )
        if arguments.samples == 1
        else measure_async_runtime_samples(
            samples=arguments.samples,
            iterations=arguments.iterations,
            warmup=arguments.warmup,
            concurrency=arguments.concurrency,
        )
    )
    encoded = json.dumps(result, indent=2, sort_keys=True)
    if arguments.output is None:
        print(encoded)
    else:
        arguments.output.write_text(encoded + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
