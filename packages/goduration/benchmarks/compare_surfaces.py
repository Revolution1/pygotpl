"""Compare the explicit Go and Python duration surfaces."""

from __future__ import annotations

import argparse
import gc
import json
import platform
import statistics
import time
from collections.abc import Callable
from typing import TypedDict

from goduration.go import MICROSECOND as GO_MICROSECOND
from goduration.go import Duration as GoDuration
from goduration.python import MICROSECOND as PYTHON_MICROSECOND
from goduration.python import Duration as PythonDuration


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
    if samples < 1 or iterations < 1:
        raise ValueError("samples and iterations must be positive")

    go_value = GoDuration.parse("1h2m3s4ms5us6ns")
    python_value = PythonDuration.parse("1h2m3s4ms5us6ns")
    operations: dict[str, tuple[Callable[[], object], Callable[[], object]]] = {
        "parse": (
            lambda: GoDuration.parse("1h2m3s4ms5us6ns"),
            lambda: PythonDuration.parse("1h2m3s4ms5us6ns"),
        ),
        "format": (lambda: str(go_value), lambda: str(python_value)),
        "multiply": (lambda: go_value * 2, lambda: python_value * 2),
        "round": (
            lambda: go_value.round(GO_MICROSECOND),
            lambda: python_value.round(PYTHON_MICROSECOND),
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
