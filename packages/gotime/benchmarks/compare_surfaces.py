"""Measure representative gotime operations against Python datetime."""

from __future__ import annotations

import argparse
import gc
import json
import platform
import statistics
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import TypedDict
from zoneinfo import ZoneInfo

from goduration.go import SECOND as GO_SECOND
from goduration.python import Duration as PythonDuration

from gotime.go import RFC3339_NANO
from gotime.go import UTC as GO_UTC
from gotime.go import Location as GoLocation
from gotime.go import Time as GoTime
from gotime.python import Time as PythonTime


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
    """Return sampled latency for equivalent public-surface operations."""
    if samples < 1 or iterations < 1:
        raise ValueError("samples and iterations must be positive")

    instant = datetime(2024, 7, 9, 13, 4, 5, 123_456, tzinfo=UTC)
    go_value = GoTime.from_components(2024, 7, 9, 13, 4, 5, 123_456_000, GO_UTC)
    python_value = PythonTime(instant)
    go_new_york = GoLocation.load("America/New_York")
    python_new_york = ZoneInfo("America/New_York")
    python_second = PythonDuration.from_seconds(1)
    operations: dict[str, tuple[Callable[[], object], Callable[[], object]]] = {
        "construct": (
            lambda: GoTime.from_components(2024, 7, 9, 13, 4, 5, 123_456_000, GO_UTC),
            lambda: PythonTime(instant),
        ),
        "format": (
            lambda: go_value.format(RFC3339_NANO),
            lambda: instant.isoformat().replace("+00:00", "Z"),
        ),
        "add_second": (
            lambda: go_value + GO_SECOND,
            lambda: python_value + python_second,
        ),
        "zone_conversion": (
            lambda: go_value.in_location(go_new_york),
            lambda: python_value.in_timezone(python_new_york),
        ),
        "datetime_add_second": (
            lambda: go_value + GO_SECOND,
            lambda: instant + timedelta(seconds=1),
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
