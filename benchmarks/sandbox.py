"""Measure opt-in sandbox and execution-budget overhead."""

from __future__ import annotations

import argparse
import json
import platform
import statistics
import time
from collections.abc import Callable, Sequence

from gotpl import ExecutionBudget, SandboxPolicy, Template

SOURCE = "{{range .}}{{.name}};{{end}}"
DATA = [{"name": f"item-{index}"} for index in range(20)]


def _measure(operation: Callable[[], object], iterations: int) -> float:
    started = time.perf_counter_ns()
    for _ in range(iterations):
        operation()
    return (time.perf_counter_ns() - started) / iterations


def build_report(*, iterations: int, samples: int) -> dict[str, object]:
    """Return default, budgeted, and strict warm-render measurements."""

    default = Template(SOURCE)
    budgeted = Template(
        SOURCE,
        budget=ExecutionBudget(
            max_output_chars=10_000,
            max_iterations=1_000,
            max_template_depth=20,
            max_function_calls=1_000,
        ),
    )
    strict = Template(SOURCE, sandbox=SandboxPolicy.strict())
    expected = default.render(DATA)
    assert budgeted.render(DATA) == expected
    assert strict.render(DATA) == expected

    operations = {
        "default": lambda: default.render(DATA),
        "budgeted": lambda: budgeted.render(DATA),
        "strict": lambda: strict.render(DATA),
    }
    measurements = {
        name: [_measure(operation, iterations) for _ in range(samples)]
        for name, operation in operations.items()
    }
    medians = {name: statistics.median(values) for name, values in measurements.items()}
    return {
        "schema_version": 1,
        "environment": {
            "python": platform.python_version(),
            "implementation": platform.python_implementation(),
            "platform": platform.platform(),
        },
        "iterations": iterations,
        "samples": samples,
        "warm_render_ns_per_op": {
            name: {"median": medians[name], "samples": values}
            for name, values in measurements.items()
        },
        "ratios": {
            "budgeted_to_default": medians["budgeted"] / medians["default"],
            "strict_to_default": medians["strict"] / medians["default"],
        },
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--iterations", type=int, default=5_000)
    parser.add_argument("--samples", type=int, default=7)
    arguments = parser.parse_args(argv)
    print(
        json.dumps(
            build_report(iterations=arguments.iterations, samples=arguments.samples),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
