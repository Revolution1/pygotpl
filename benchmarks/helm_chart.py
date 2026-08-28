"""Benchmark rendering a complete local Helm chart directory."""

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
from pathlib import Path
from typing import cast

from examples.helm_cli import _manifests
from examples.helm_runtime import Engine, Release, load_chart, load_values


def _merge(
    left: Mapping[str, object], right: Mapping[str, object]
) -> dict[str, object]:
    merged = dict(left)
    for key, value in right.items():
        current = merged.get(key)
        if isinstance(current, dict) and isinstance(value, dict):
            merged[key] = _merge(
                cast(dict[str, object], current), cast(dict[str, object], value)
            )
        else:
            merged[key] = value
    return merged


def _timing_result(values: list[float], *, iterations: int) -> dict[str, object]:
    return {
        "iterations": iterations,
        "samples_ns_per_op": values,
        "median_ns_per_op": statistics.median(values),
        "min_ns_per_op": min(values),
        "max_ns_per_op": max(values),
    }


def _phase_samples(
    chart_path: Path,
    values: Mapping[str, object],
    release: Release,
    *,
    samples: int,
    iterations: int,
) -> dict[str, object]:
    engine = Engine()

    def run_once() -> tuple[int, int, int]:
        started = time.perf_counter_ns()
        chart = load_chart(chart_path)
        loaded = time.perf_counter_ns()
        rendered = engine.render(chart, values, release=release)
        finished_render = time.perf_counter_ns()
        _manifests(rendered)
        finished = time.perf_counter_ns()
        return loaded - started, finished_render - loaded, finished - finished_render

    run_once()
    phase_values: dict[str, list[float]] = {
        "chart_load": [],
        "chart_render_cold": [],
        "manifest_prepare": [],
        "end_to_end": [],
    }
    for _ in range(samples):
        load_total = 0
        render_total = 0
        manifest_total = 0
        for _ in range(iterations):
            loaded, rendered, prepared = run_once()
            load_total += loaded
            render_total += rendered
            manifest_total += prepared
        phase_values["chart_load"].append(load_total / iterations)
        phase_values["chart_render_cold"].append(render_total / iterations)
        phase_values["manifest_prepare"].append(manifest_total / iterations)
        phase_values["end_to_end"].append(
            (load_total + render_total + manifest_total) / iterations
        )
    return {
        name: _timing_result(measurements, iterations=iterations)
        for name, measurements in phase_values.items()
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
    chart_path: Path,
    *,
    values_paths: Sequence[Path] = (),
    release_name: str = "benchmark",
    namespace: str = "default",
    samples: int = 5,
    iterations: int = 1,
    profile_iterations: int = 1,
    top: int = 15,
) -> dict[str, object]:
    """Measure chart loading, cold rendering, and manifest preparation."""

    values: dict[str, object] = {}
    for path in values_paths:
        values = _merge(values, load_values(path))
    release = Release(name=release_name, namespace=namespace)
    chart = load_chart(chart_path)
    engine = Engine()

    def render_operation() -> object:
        return engine.render(chart, values, release=release)

    rendered = cast(dict[str, str], render_operation())

    manifests = _manifests(rendered)
    digest = hashlib.sha256(
        "\n---\n".join(document for _, document in manifests).encode()
    ).hexdigest()
    return {
        "schema_version": 1,
        "chart": {
            "name": chart.name,
            "version": chart.version,
            "path": str(chart_path),
            "values": [str(path) for path in values_paths],
        },
        "environment": {
            "python": sys.version.split()[0],
            "implementation": platform.python_implementation(),
            "platform": platform.platform(),
            "machine": platform.machine(),
        },
        "output": {
            "rendered_templates": len(rendered),
            "manifests": len(manifests),
            "sha256": digest,
        },
        "timings": _phase_samples(
            chart_path,
            values,
            release,
            samples=samples,
            iterations=iterations,
        ),
        "render_profile": _profile(
            render_operation, iterations=profile_iterations, top=top
        ),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("chart", type=Path)
    parser.add_argument("-f", "--values", action="append", type=Path, default=[])
    parser.add_argument("--release-name", default="benchmark")
    parser.add_argument("--namespace", default="default")
    parser.add_argument("--samples", type=int, default=5)
    parser.add_argument("--iterations", type=int, default=1)
    parser.add_argument("--profile-iterations", type=int, default=1)
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
    ):
        raise ValueError("benchmark counts must be positive")
    result = benchmark(
        arguments.chart,
        values_paths=arguments.values,
        release_name=arguments.release_name,
        namespace=arguments.namespace,
        samples=arguments.samples,
        iterations=arguments.iterations,
        profile_iterations=arguments.profile_iterations,
        top=arguments.top,
    )
    output = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if arguments.output is None:
        print(output, end="")
    else:
        arguments.output.write_text(output, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
