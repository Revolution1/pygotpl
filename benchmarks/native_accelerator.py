"""Build and measure a semantics-sharing Cython sync-VM prototype."""

from __future__ import annotations

import argparse
import gc
import importlib.util
import json
import platform
import sysconfig
import tempfile
import time
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import Protocol, TypedDict, cast

from benchmarks.compare import (
    PROJECT_ROOT,
    BenchmarkFixture,
    Distribution,
    load_benchmark,
    summarize_measurements,
)
from gotpl import HTMLTemplate, Template
from gotpl.runtime.sync_vm import render_program as pure_render_program

_REQUIRED_IMPROVEMENT = 0.25
_REQUIRED_WORKLOADS = 2


class RuntimeFunction(Protocol):
    def __call__(
        self,
        program: object,
        data: object = None,
        **options: object,
    ) -> str: ...


class WorkloadResult(TypedDict):
    id: str
    samples: int
    iterations: int
    pure_python_ns_per_op: Distribution
    cython_ns_per_op: Distribution
    improvement: Distribution


class NativePrototypeResult(TypedDict):
    schema_version: int
    prototype: str
    environment: dict[str, str]
    workloads: list[WorkloadResult]
    retention_gate: dict[str, int | float | bool]


def evaluate_retention_gate(improvements: list[float]) -> bool:
    """Return whether two workloads meet the adopted 25% retention gate."""

    return (
        len(improvements) >= _REQUIRED_WORKLOADS
        and sum(value >= _REQUIRED_IMPROVEMENT for value in improvements)
        >= _REQUIRED_WORKLOADS
    )


def _template_for_fixture(fixture: BenchmarkFixture) -> HTMLTemplate | Template:
    request = fixture["request"]
    template_type = HTMLTemplate if request["engine"] == "html" else Template
    return template_type(request["template"], name=request["name"])


def prepare_runtime_pair(
    path: Path,
    *,
    runtime: RuntimeFunction | None,
) -> tuple[Callable[[], str], Callable[[], str], str]:
    """Prepare equivalent direct calls into pure and compiled sync runtimes."""

    fixture = load_benchmark(path)
    request = fixture["request"]
    template = _template_for_fixture(fixture)
    candidate_runtime = pure_render_program if runtime is None else runtime
    text_template = template._text if isinstance(template, HTMLTemplate) else template
    options: dict[str, object] = {
        "functions": template._runtime_functions,
        "missing_key": text_template.missing_key,
        "format_mode": text_template.format_mode,
        "_namespace": template._namespace,
    }

    def baseline() -> str:
        return pure_render_program(template._program, request["data"], **options)

    def candidate() -> str:
        return candidate_runtime(template._program, request["data"], **options)

    expected = baseline()
    if candidate() != expected:
        raise RuntimeError(f"candidate output differs for {fixture['id']}")
    return baseline, candidate, expected


def _measure(operation: Callable[[], str], iterations: int) -> float:
    gc_was_enabled = gc.isenabled()
    gc.disable()
    try:
        started = time.perf_counter_ns()
        for _ in range(iterations):
            operation()
        elapsed = time.perf_counter_ns() - started
    finally:
        if gc_was_enabled:
            gc.enable()
    return elapsed / iterations


def _load_extension(path: Path) -> ModuleType:
    name = "gotpl.runtime._sync_vm_cython"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load Cython prototype: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_cython_prototype(build_root: Path) -> tuple[ModuleType, str]:
    """Compile the existing sync VM under a private module name."""

    from Cython import __version__ as cython_version
    from Cython.Build import cythonize
    from setuptools import Extension, setup

    build_lib = build_root / "lib"
    build_temp = build_root / "temp"
    generated = build_root / "generated"
    source = PROJECT_ROOT / "src" / "gotpl" / "runtime" / "sync_vm.py"
    extension = Extension("gotpl.runtime._sync_vm_cython", [str(source)])
    modules = cythonize(
        [extension],
        build_dir=str(generated),
        compiler_directives={"language_level": 3},
        quiet=True,
    )
    setup(
        name="gotpl-native-prototype",
        ext_modules=modules,
        script_args=[
            "--quiet",
            "build_ext",
            "--build-lib",
            str(build_lib),
            "--build-temp",
            str(build_temp),
        ],
    )
    suffix = cast(str, sysconfig.get_config_var("EXT_SUFFIX"))
    extension_path = build_lib / "gotpl" / "runtime" / f"_sync_vm_cython{suffix}"
    if not extension_path.is_file():
        raise RuntimeError("Cython prototype build produced no extension")
    return _load_extension(extension_path), cython_version


def _measure_workload(
    path: Path,
    runtime: RuntimeFunction,
    *,
    samples: int,
    iterations: int | None,
) -> WorkloadResult:
    fixture = load_benchmark(path)
    count = fixture["iterations"] if iterations is None else iterations
    baseline, candidate, _ = prepare_runtime_pair(path, runtime=runtime)
    for _ in range(fixture["warmup"]):
        baseline()
        candidate()
    pure_values: list[float] = []
    cython_values: list[float] = []
    improvements: list[float] = []
    for sample in range(samples):
        first, second = (
            (baseline, candidate) if sample % 2 == 0 else (candidate, baseline)
        )
        first_value = _measure(first, count)
        second_value = _measure(second, count)
        pure = first_value if first is baseline else second_value
        cython = second_value if first is baseline else first_value
        pure_values.append(pure)
        cython_values.append(cython)
        improvements.append(1.0 - cython / pure)
    return WorkloadResult(
        id=fixture["id"],
        samples=samples,
        iterations=count,
        pure_python_ns_per_op=summarize_measurements(pure_values),
        cython_ns_per_op=summarize_measurements(cython_values),
        improvement=summarize_measurements(improvements),
    )


def run_prototype(
    *,
    samples: int = 7,
    iterations: int | None = None,
    build_root: Path | None = None,
) -> NativePrototypeResult:
    """Build, validate, and sample the Cython prototype."""

    if samples < 1 or (iterations is not None and iterations < 1):
        raise ValueError("invalid native prototype measurement configuration")
    temporary: tempfile.TemporaryDirectory[str] | None = None
    if build_root is None:
        temporary = tempfile.TemporaryDirectory(prefix="gotpl-cython-")
        build_root = Path(temporary.name)
    try:
        module, cython_version = build_cython_prototype(build_root)
        runtime = cast(RuntimeFunction, module.render_program)
        fixture_dir = PROJECT_ROOT / "benchmarks" / "fixtures"
        workloads = [
            _measure_workload(
                fixture_dir / filename,
                runtime,
                samples=samples,
                iterations=iterations,
            )
            for filename in ("text_render.json", "html_render.json")
        ]
    finally:
        if temporary is not None:
            temporary.cleanup()
    median_improvements = [item["improvement"]["median"] for item in workloads]
    return NativePrototypeResult(
        schema_version=1,
        prototype="cython-compiled-sync-vm",
        environment={
            "python": platform.python_version(),
            "cython": cython_version,
            "platform": platform.platform(),
            "machine": platform.machine(),
        },
        workloads=workloads,
        retention_gate={
            "required_improvement": _REQUIRED_IMPROVEMENT,
            "required_workloads": _REQUIRED_WORKLOADS,
            "passed": evaluate_retention_gate(median_improvements),
        },
    )


def main() -> None:
    """Run the optional native prototype from the command line."""

    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", type=int, default=7)
    parser.add_argument("--iterations", type=int)
    parser.add_argument("--build-root", type=Path)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    report = run_prototype(
        samples=arguments.samples,
        iterations=arguments.iterations,
        build_root=arguments.build_root,
    )
    encoded = json.dumps(report, indent=2, sort_keys=True)
    if arguments.output is None:
        print(encoded)
    else:
        arguments.output.write_text(encoded + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
