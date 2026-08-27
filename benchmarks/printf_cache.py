"""Measure hot-cache reuse for Go printf directive parsing."""

# pyright: reportPrivateUsage=false

from __future__ import annotations

import argparse
import gc
import json
import statistics
import time
from typing import TypedDict

from gotpl._compat.gofmt._core import _parse_directive


class PrintfCacheComparison(TypedDict):
    schema_version: int
    samples: int
    iterations_per_sample: int
    uncached_median_ns_per_op: float
    cached_median_ns_per_op: float
    uncached_to_cached_ratio: float


def measure_printf_cache(
    *,
    samples: int = 7,
    iterations: int = 500_000,
) -> PrintfCacheComparison:
    """Compare repeated parsing with a bounded hot-cache lookup."""

    if samples < 1 or iterations < 1:
        raise ValueError("benchmark counts must be positive")
    format_string = "user=%04d quoted=%q"
    position = format_string.index("%") + 1
    uncached_parse = _parse_directive.__wrapped__
    expected = uncached_parse(format_string, position)
    _parse_directive.cache_clear()
    if _parse_directive(format_string, position) != expected:
        raise RuntimeError("printf cache benchmark outputs differ")

    measurements: dict[str, list[float]] = {"uncached": [], "cached": []}
    gc_was_enabled = gc.isenabled()
    gc.disable()
    try:
        for _ in range(samples):
            for mode in ("uncached", "cached"):
                started = time.perf_counter_ns()
                if mode == "uncached":
                    for _ in range(iterations):
                        uncached_parse(format_string, position)
                else:
                    for _ in range(iterations):
                        _parse_directive(format_string, position)
                elapsed = time.perf_counter_ns() - started
                measurements[mode].append(elapsed / iterations)
    finally:
        if gc_was_enabled:
            gc.enable()

    uncached = statistics.median(measurements["uncached"])
    cached = statistics.median(measurements["cached"])
    return PrintfCacheComparison(
        schema_version=1,
        samples=samples,
        iterations_per_sample=iterations,
        uncached_median_ns_per_op=uncached,
        cached_median_ns_per_op=cached,
        uncached_to_cached_ratio=uncached / cached,
    )


def main() -> None:
    """Run the printf cache benchmark from the command line."""

    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", type=int, default=7)
    parser.add_argument("--iterations", type=int, default=500_000)
    arguments = parser.parse_args()
    print(
        json.dumps(
            measure_printf_cache(
                samples=arguments.samples,
                iterations=arguments.iterations,
            ),
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
