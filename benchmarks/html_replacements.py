"""Measure the contextual HTML replacement hot path."""

# pyright: reportPrivateUsage=false

from __future__ import annotations

import argparse
import gc
import json
import statistics
import time
from typing import TypedDict

from gotpl.html.escapers import _HTML_REPLACEMENTS, _replace


class ReplacementComparison(TypedDict):
    schema_version: int
    samples: int
    iterations_per_sample: int
    generator_median_ns_per_op: float
    chained_median_ns_per_op: float
    generator_to_chained_ratio: float


def _generator_replace(value: str) -> str:
    return "".join(_HTML_REPLACEMENTS.get(character, character) for character in value)


def measure_html_replacements(
    *,
    samples: int = 7,
    iterations: int = 100_000,
) -> ReplacementComparison:
    """Compare the former generator with ordered C-level replacements."""

    if samples < 1 or iterations < 1:
        raise ValueError("benchmark counts must be positive")
    value = "Alice <Admin> & Co. + quoted" * 2
    expected = _generator_replace(value)
    if _replace(value, _HTML_REPLACEMENTS) != expected:
        raise RuntimeError("replacement benchmark outputs differ")
    measurements: dict[str, list[float]] = {"generator": [], "chained": []}
    gc_was_enabled = gc.isenabled()
    gc.disable()
    try:
        for _ in range(samples):
            for mode in ("generator", "chained"):
                started = time.perf_counter_ns()
                if mode == "generator":
                    for _ in range(iterations):
                        _generator_replace(value)
                else:
                    for _ in range(iterations):
                        _replace(value, _HTML_REPLACEMENTS)
                elapsed = time.perf_counter_ns() - started
                measurements[mode].append(elapsed / iterations)
    finally:
        if gc_was_enabled:
            gc.enable()

    generator = statistics.median(measurements["generator"])
    chained = statistics.median(measurements["chained"])
    return ReplacementComparison(
        schema_version=1,
        samples=samples,
        iterations_per_sample=iterations,
        generator_median_ns_per_op=generator,
        chained_median_ns_per_op=chained,
        generator_to_chained_ratio=generator / chained,
    )


def main() -> None:
    """Run the replacement benchmark from the command line."""

    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", type=int, default=7)
    parser.add_argument("--iterations", type=int, default=100_000)
    arguments = parser.parse_args()
    print(
        json.dumps(
            measure_html_replacements(
                samples=arguments.samples,
                iterations=arguments.iterations,
            ),
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
