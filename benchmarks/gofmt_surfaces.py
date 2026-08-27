"""Measure the explicit Go and Python gofmt surfaces."""

from __future__ import annotations

import argparse
import gc
import json
import platform
import statistics
import time
from collections.abc import Callable
from typing import TypedDict

from gotpl._compat.gofmt.go import sprintf as go_sprintf
from gotpl._compat.gofmt.python import sprintf as python_sprintf


class Distribution(TypedDict):
    values: list[float]
    median: float
    minimum: float
    maximum: float


class SurfaceResult(TypedDict):
    go_ns_per_op: Distribution
    python_ns_per_op: Distribution
    python_to_go_ratio: float


def _measure(
    operation: Callable[[], object], *, samples: int, iterations: int
) -> Distribution:
    values: list[float] = []
    operation()
    for _ in range(samples):
        enabled = gc.isenabled()
        gc.disable()
        try:
            started = time.perf_counter_ns()
            for _ in range(iterations):
                operation()
            values.append((time.perf_counter_ns() - started) / iterations)
        finally:
            if enabled:
                gc.enable()
    return Distribution(
        values=values,
        median=statistics.median(values),
        minimum=min(values),
        maximum=max(values),
    )


def compare_surfaces(
    *, samples: int = 7, iterations: int = 100_000
) -> dict[str, object]:
    """Return sampled latency for representative public operations."""
    if samples < 1 or iterations < 1:
        raise ValueError("samples and iterations must be positive")

    operations: dict[str, tuple[Callable[[], object], Callable[[], object]]] = {
        "integer": (
            lambda: go_sprintf("%#08x", 31),
            lambda: python_sprintf("%#08x", 31),
        ),
        "string": (
            lambda: go_sprintf("%+q", "café"),
            lambda: python_sprintf("%+q", "café"),
        ),
        "default_mapping": (
            lambda: go_sprintf("%v", {"b": 2, "a": 1}),
            lambda: python_sprintf("%v", {"b": 2, "a": 1}),
        ),
        "dynamic_operands": (
            lambda: go_sprintf("%[3]*.[2]*[1]f", 3.14159, 2, 8),
            lambda: python_sprintf("%[3]*.[2]*[1]f", 3.14159, 2, 8),
        ),
    }
    results: dict[str, SurfaceResult] = {}
    for name, (go_operation, python_operation) in operations.items():
        go_result = _measure(go_operation, samples=samples, iterations=iterations)
        python_result = _measure(
            python_operation, samples=samples, iterations=iterations
        )
        results[name] = SurfaceResult(
            go_ns_per_op=go_result,
            python_ns_per_op=python_result,
            python_to_go_ratio=python_result["median"] / go_result["median"],
        )
    return {
        "schema_version": 1,
        "samples": samples,
        "iterations": iterations,
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "machine": platform.machine(),
        },
        "operations": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", type=int, default=7)
    parser.add_argument("--iterations", type=int, default=100_000)
    arguments = parser.parse_args()
    print(
        json.dumps(
            compare_surfaces(
                samples=arguments.samples,
                iterations=arguments.iterations,
            ),
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
