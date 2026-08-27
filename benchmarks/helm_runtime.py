"""Profile the core multi-source engine and miniature Helm runtime example."""

from __future__ import annotations

import argparse
import cProfile
import hashlib
import json
import platform
import statistics
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from importlib import import_module
from pathlib import Path
from typing import Any, cast

from examples.helm_runtime import Chart, Engine, Release
from gotpl import TemplateEngine

PROJECT_ROOT = Path(__file__).parents[1]
DEFAULT_FIXTURE = PROJECT_ROOT / "benchmarks" / "helm" / "fixtures" / "runtime-v1.json"

try:
    _tracemalloc: Any | None = import_module("tracemalloc")
except ModuleNotFoundError:
    _tracemalloc = None


def tracemalloc_available() -> bool:
    """Return whether this interpreter provides a working tracemalloc module."""

    return _tracemalloc is not None


def _load(path: Path) -> dict[str, object]:
    value: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"invalid Helm benchmark fixture {path}")
    mapping = cast(dict[object, object], value)
    if mapping.get("schema_version") != 1 or not all(
        isinstance(key, str) for key in mapping
    ):
        raise ValueError(f"invalid Helm benchmark fixture {path}")
    return cast(dict[str, object], mapping)


def _string_map(value: object, name: str) -> dict[str, str]:
    if not isinstance(value, dict):
        raise ValueError(f"invalid {name} mapping")
    mapping = cast(dict[object, object], value)
    if not all(
        isinstance(key, str) and isinstance(item, str) for key, item in mapping.items()
    ):
        raise ValueError(f"invalid {name} mapping")
    return cast(dict[str, str], mapping)


def _object_map(value: object, name: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"invalid {name} mapping")
    mapping = cast(dict[object, object], value)
    if not all(isinstance(key, str) for key in mapping):
        raise ValueError(f"invalid {name} mapping")
    return cast(dict[str, object], mapping)


def _chart(fixture: Mapping[str, object], *, dynamic: bool) -> Chart:
    raw = _object_map(fixture["chart"], "chart")
    templates = _string_map(
        raw["templates" if dynamic else "static_templates"], "templates"
    )
    return Chart(
        name=cast(str, raw["name"]),
        version=cast(str, raw["version"]),
        templates=templates,
        files=_string_map(raw["files"], "files"),
    )


def _digest(value: object) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def _samples(
    operation: Callable[[], object], *, iterations: int, count: int
) -> dict[str, object]:
    for _ in range(min(20, iterations)):
        operation()
    values: list[float] = []
    for _ in range(count):
        started = time.perf_counter_ns()
        for _ in range(iterations):
            operation()
        values.append((time.perf_counter_ns() - started) / iterations)
    return {
        "iterations": iterations,
        "samples_ns_per_op": values,
        "median_ns_per_op": statistics.median(values),
        "min_ns_per_op": min(values),
        "max_ns_per_op": max(values),
    }


def _memory(operation: Callable[[], object], *, samples: int) -> dict[str, int]:
    tracemalloc = _tracemalloc
    if tracemalloc is None:
        raise RuntimeError("Helm runtime memory benchmark requires tracemalloc")
    peaks: list[int] = []
    for _ in range(samples):
        tracemalloc.start()
        baseline, _ = tracemalloc.get_traced_memory()
        result = operation()
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        if result is None:
            raise RuntimeError("benchmark operation returned no result")
        peaks.append(peak - baseline)
    return {
        "samples": samples,
        "median_peak_bytes": int(statistics.median(peaks)),
        "min_peak_bytes": min(peaks),
        "max_peak_bytes": max(peaks),
    }


def _profile(
    operation: Callable[[], object], *, iterations: int, top: int
) -> list[dict[str, object]]:
    profiler = cProfile.Profile()
    profiler.enable()
    for _ in range(iterations):
        operation()
    profiler.disable()
    entries = sorted(profiler.getstats(), key=lambda item: item.totaltime, reverse=True)
    output: list[dict[str, object]] = []
    for entry in entries[:top]:
        code = entry.code
        output.append(
            {
                "function": code if isinstance(code, str) else code.co_name,
                "file": "" if isinstance(code, str) else code.co_filename,
                "calls": entry.callcount,
                "self_seconds": entry.inlinetime,
                "cumulative_seconds": entry.totaltime,
            }
        )
    return output


def benchmark(
    fixture_path: Path,
    *,
    samples: int,
    iterations: int,
    memory_samples: int,
    profile_iterations: int,
    top: int,
) -> dict[str, object]:
    fixture = _load(fixture_path)
    values = _object_map(fixture["values"], "values")
    release = Release(name="demo")
    dynamic_chart = _chart(fixture, dynamic=True)
    static_chart = _chart(fixture, dynamic=False)
    helm_engine = Engine()

    def dynamic_operation() -> object:
        return helm_engine.render(dynamic_chart, values, release=release)

    def static_operation() -> object:
        return helm_engine.render(static_chart, values, release=release)

    dynamic_output = dynamic_operation()
    static_output = static_operation()
    if dynamic_output != static_output:
        raise RuntimeError("dynamic and static Helm benchmark outputs differ")

    core_sources = _string_map(fixture["core_sources"], "core_sources")
    raw_contexts = _object_map(fixture["core_contexts"], "core_contexts")
    core_contexts = dict(raw_contexts)
    core_engine = TemplateEngine.from_sources(core_sources)

    def core_operation() -> object:
        return core_engine.render(core_contexts)

    core_output = core_operation()

    def core_compile() -> object:
        return TemplateEngine.from_sources(core_sources)

    operations: dict[str, Callable[[], object]] = {
        "core_compile": core_compile,
        "core_warm_batch": core_operation,
        "helm_static_cold": static_operation,
        "helm_tpl_cold": dynamic_operation,
    }
    timings = {
        name: _samples(operation, iterations=iterations, count=samples)
        for name, operation in operations.items()
    }
    memory = (
        {
            name: _memory(operation, samples=memory_samples)
            for name, operation in operations.items()
        }
        if memory_samples
        else {}
    )
    return {
        "schema_version": 1,
        "fixture": fixture["id"],
        "reference": fixture["reference"],
        "environment": {
            "python": sys.version.split()[0],
            "implementation": platform.python_implementation(),
            "platform": platform.platform(),
            "machine": platform.machine(),
        },
        "output_sha256": {
            "core": _digest(core_output),
            "helm": _digest(dynamic_output),
        },
        "timings": timings,
        "memory": memory,
        "helm_tpl_profile": _profile(
            dynamic_operation, iterations=profile_iterations, top=top
        ),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("fixture", nargs="?", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--samples", type=int, default=7)
    parser.add_argument("--iterations", type=int, default=500)
    parser.add_argument("--memory-samples", type=int, default=25)
    parser.add_argument("--profile-iterations", type=int, default=500)
    parser.add_argument("--top", type=int, default=15)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args(argv)
    if (
        min(
            arguments.samples,
            arguments.iterations,
            arguments.profile_iterations,
            arguments.top,
        )
        < 1
        or arguments.memory_samples < 0
    ):
        raise ValueError("benchmark counts must be positive, except memory may be zero")
    result = benchmark(
        arguments.fixture,
        samples=arguments.samples,
        iterations=arguments.iterations,
        memory_samples=arguments.memory_samples,
        profile_iterations=arguments.profile_iterations,
        top=arguments.top,
    )
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if arguments.output is None:
        print(rendered, end="")
    else:
        arguments.output.write_text(rendered, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
