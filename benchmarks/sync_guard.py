"""Isolate the synchronous cost of rejecting async function results."""

# pyright: reportPrivateUsage=false

from __future__ import annotations

import argparse
import gc
import json
import statistics
import time
from typing import TypedDict

from gotpl import Template
from gotpl.runtime import sync_vm


class GuardComparison(TypedDict):
    schema_version: int
    samples: int
    iterations_per_sample: int
    checked_median_ns_per_op: float
    bypassed_median_ns_per_op: float
    checked_to_bypassed_ratio: float


def measure_sync_guard(
    *,
    samples: int = 7,
    iterations: int = 10_000,
) -> GuardComparison:
    """Compare the real sync guard with a diagnostic identity function."""

    if samples < 1 or iterations < 1:
        raise ValueError("benchmark counts must be positive")

    def identity(value: object) -> object:
        return value

    def format_value(value: object) -> str:
        return f"<{value}>"

    template = Template("{{format .}}", functions={"format": format_value})
    original = sync_vm.reject_awaitable
    measurements: dict[str, list[float]] = {"checked": [], "bypassed": []}
    gc_was_enabled = gc.isenabled()
    gc.disable()
    try:
        for _ in range(samples):
            for mode, guard in (("checked", original), ("bypassed", identity)):
                sync_vm.reject_awaitable = guard
                started = time.perf_counter_ns()
                for _ in range(iterations):
                    template.render("value")
                elapsed = time.perf_counter_ns() - started
                measurements[mode].append(elapsed / iterations)
    finally:
        sync_vm.reject_awaitable = original
        if gc_was_enabled:
            gc.enable()

    checked = statistics.median(measurements["checked"])
    bypassed = statistics.median(measurements["bypassed"])
    return GuardComparison(
        schema_version=1,
        samples=samples,
        iterations_per_sample=iterations,
        checked_median_ns_per_op=checked,
        bypassed_median_ns_per_op=bypassed,
        checked_to_bypassed_ratio=checked / bypassed,
    )


def main() -> None:
    """Run the synchronous awaitable-guard comparison."""

    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", type=int, default=7)
    parser.add_argument("--iterations", type=int, default=10_000)
    arguments = parser.parse_args()
    print(
        json.dumps(
            measure_sync_guard(
                samples=arguments.samples,
                iterations=arguments.iterations,
            ),
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
