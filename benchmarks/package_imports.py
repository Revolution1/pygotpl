"""Measure cold import latency and traced peak memory in fresh interpreters."""

from __future__ import annotations

import argparse
import json
import platform
import statistics
import subprocess
import tempfile
from pathlib import Path
from typing import TypedDict


class ImportSample(TypedDict):
    nanoseconds: int
    peak_traced_bytes: int


_PROBE = """
import importlib
import json
import time
import tracemalloc
tracemalloc.start()
started = time.perf_counter_ns()
importlib.import_module({module!r})
elapsed = time.perf_counter_ns() - started
_current, peak = tracemalloc.get_traced_memory()
print(json.dumps({{"nanoseconds": elapsed, "peak_traced_bytes": peak}}))
"""


def measure_import(python: Path, module: str, *, samples: int) -> dict[str, object]:
    """Measure one module in a fresh target interpreter for every sample."""
    values: list[ImportSample] = []
    for _ in range(samples):
        completed = subprocess.run(
            [str(python), "-c", _PROBE.format(module=module)],
            cwd=tempfile.gettempdir(),
            check=True,
            capture_output=True,
            text=True,
        )
        values.append(json.loads(completed.stdout))
    latency = [sample["nanoseconds"] for sample in values]
    memory = [sample["peak_traced_bytes"] for sample in values]
    return {
        "latency_ns": {
            "values": latency,
            "median": statistics.median(latency),
            "minimum": min(latency),
            "maximum": max(latency),
        },
        "peak_traced_bytes": {
            "values": memory,
            "median": statistics.median(memory),
            "minimum": min(memory),
            "maximum": max(memory),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--samples", type=int, default=15)
    parser.add_argument(
        "modules",
        nargs="*",
        default=["goduration", "gotime", "gotpl"],
    )
    arguments = parser.parse_args()
    if arguments.samples < 1:
        parser.error("--samples must be positive")
    python = arguments.python.absolute()
    result = {
        "schema_version": 1,
        "measurement": "fresh-process-import",
        "samples": arguments.samples,
        "driver": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "machine": platform.machine(),
        },
        "target_python": str(python),
        "modules": {
            module: measure_import(python, module, samples=arguments.samples)
            for module in arguments.modules
        },
    }
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
