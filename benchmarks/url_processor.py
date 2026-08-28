"""Compare branching and table-driven contextual URL processing."""

# pyright: reportPrivateUsage=false

from __future__ import annotations

import argparse
import gc
import json
import statistics
import time
from typing import Protocol, TypedDict

from gotpl.html.escapers import _url_processor


class URLProcessorComparison(TypedDict):
    schema_version: int
    samples: int
    iterations_per_sample: int
    branching_median_ns_per_op: float
    table_median_ns_per_op: float
    branching_to_table_ratio: float


class _URLProcessor(Protocol):
    def __call__(self, value: str, *, normalize: bool) -> str: ...


_CASES = (
    ("alice smith", False),
    ("benchmark & suite", False),
    ("/images/alice@2x.png", True),
    ("guest?q=x", True),
    ("%2 %zሴ", True),
)


def _branching_processor(value: str, *, normalize: bool) -> str:
    data = value.encode("utf-8")
    output: list[str] = []
    normalized_safe = b"!#$&*+,-./:;=?@[]"
    unreserved = b"-._~"
    index = 0
    while index < len(data):
        byte = data[index]
        is_alphanumeric = 97 <= byte <= 122 or 65 <= byte <= 90 or 48 <= byte <= 57
        if (
            is_alphanumeric
            or byte in unreserved
            or (normalize and byte in normalized_safe)
        ):
            output.append(chr(byte))
        elif (
            normalize
            and byte == 37
            and index + 2 < len(data)
            and _is_hex(data[index + 1])
            and _is_hex(data[index + 2])
        ):
            output.append("%")
        else:
            output.append(f"%{byte:02x}")
        index += 1
    return "".join(output)


def _is_hex(byte: int) -> bool:
    return 48 <= byte <= 57 or 97 <= byte <= 102 or 65 <= byte <= 70


def _sample(operation: _URLProcessor, iterations: int) -> float:
    started = time.perf_counter_ns()
    for _ in range(iterations):
        for value, normalize in _CASES:
            operation(value, normalize=normalize)
    return (time.perf_counter_ns() - started) / (iterations * len(_CASES))


def measure_url_processor(
    *,
    samples: int = 7,
    iterations: int = 100_000,
) -> URLProcessorComparison:
    """Measure equivalent branching and table-driven URL processors."""

    if samples < 1 or iterations < 1:
        raise ValueError("benchmark counts must be positive")
    for value, normalize in _CASES:
        expected = _branching_processor(value, normalize=normalize)
        if _url_processor(value, normalize=normalize) != expected:
            raise RuntimeError("URL processor benchmark outputs differ")
    measurements: dict[str, list[float]] = {"branching": [], "table": []}
    gc_was_enabled = gc.isenabled()
    gc.disable()
    try:
        for index in range(samples):
            order = ("branching", "table") if index % 2 == 0 else ("table", "branching")
            for mode in order:
                operation = (
                    _branching_processor if mode == "branching" else _url_processor
                )
                measurements[mode].append(_sample(operation, iterations))
    finally:
        if gc_was_enabled:
            gc.enable()
    branching = statistics.median(measurements["branching"])
    table = statistics.median(measurements["table"])
    return URLProcessorComparison(
        schema_version=1,
        samples=samples,
        iterations_per_sample=iterations,
        branching_median_ns_per_op=branching,
        table_median_ns_per_op=table,
        branching_to_table_ratio=branching / table,
    )


def main() -> None:
    """Run the contextual URL processor comparison."""

    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", type=int, default=7)
    parser.add_argument("--iterations", type=int, default=100_000)
    arguments = parser.parse_args()
    print(
        json.dumps(
            measure_url_processor(
                samples=arguments.samples,
                iterations=arguments.iterations,
            ),
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
