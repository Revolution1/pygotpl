"""Compare cached and repeated signature dispatch for a real HTML escaper."""

# pyright: reportPrivateUsage=false

from __future__ import annotations

import argparse
import gc
import json
import statistics
import time
from typing import TypedDict

from gotpl.html.template import _internal_escapers
from gotpl.runtime.callables import (
    call_spec,
    invoke_prepared_template_function,
    invoke_template_function,
)


class DispatchComparison(TypedDict):
    schema_version: int
    samples: int
    iterations_per_sample: int
    generic_median_ns_per_op: float
    prepared_median_ns_per_op: float
    generic_to_prepared_ratio: float


def measure_call_dispatch(
    *,
    samples: int = 7,
    iterations: int = 300_000,
) -> DispatchComparison:
    """Measure signature lookup against construction-time metadata reuse."""

    if samples < 1 or iterations < 1:
        raise ValueError("benchmark counts must be positive")
    function = _internal_escapers("go")["_html_template_htmlescaper"]
    spec = call_spec(function)
    arguments: list[object] = ["<&"]
    measurements: dict[str, list[float]] = {"generic": [], "prepared": []}
    gc_was_enabled = gc.isenabled()
    gc.disable()
    try:
        for _ in range(samples):
            for mode in ("generic", "prepared"):
                started = time.perf_counter_ns()
                if mode == "generic":
                    for _ in range(iterations):
                        invoke_template_function("escape", function, arguments)
                else:
                    for _ in range(iterations):
                        invoke_prepared_template_function(
                            "escape",
                            function,
                            arguments,
                            spec,
                        )
                elapsed = time.perf_counter_ns() - started
                measurements[mode].append(elapsed / iterations)
    finally:
        if gc_was_enabled:
            gc.enable()

    generic = statistics.median(measurements["generic"])
    prepared = statistics.median(measurements["prepared"])
    return DispatchComparison(
        schema_version=1,
        samples=samples,
        iterations_per_sample=iterations,
        generic_median_ns_per_op=generic,
        prepared_median_ns_per_op=prepared,
        generic_to_prepared_ratio=generic / prepared,
    )


def main() -> None:
    """Run the callable-dispatch benchmark from the command line."""

    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", type=int, default=7)
    parser.add_argument("--iterations", type=int, default=300_000)
    arguments = parser.parse_args()
    print(
        json.dumps(
            measure_call_dispatch(
                samples=arguments.samples,
                iterations=arguments.iterations,
            ),
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
