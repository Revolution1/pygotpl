"""Compare the generic synchronous VM with the opt-in linked sidecar."""

# pyright: reportPrivateUsage=false

from __future__ import annotations

import argparse
import gc
import statistics
import time
import tracemalloc
from collections.abc import Callable, Sequence
from functools import partial
from io import StringIO
from pathlib import Path

from gotpl import HTMLTemplate, Template
from gotpl.funcs.sprig import text_func_map
from gotpl.runtime.linked import LinkedProgram, link_program
from gotpl.runtime.sync_vm import render_program, render_program_to

from .compare import BenchmarkFixture, load_benchmark

DEFAULT_FIXTURES = (
    "text_render.json",
    "html_render.json",
    "sprig_render.json",
    "named_large_render.json",
)
FIXTURE_ROOT = Path(__file__).parent / "fixtures"


def _prepare(
    fixture: BenchmarkFixture,
) -> tuple[
    Callable[[], object],
    Callable[[], object],
    LinkedProgram,
    Callable[[], LinkedProgram],
]:
    request = fixture["request"]
    profile = request.get("function_profile")
    functions = text_func_map() if profile == "sprig-v3.3.0" else None
    template_type = HTMLTemplate if request["engine"] == "html" else Template
    template = template_type(
        request["template"],
        name=request["name"],
        functions=functions,
    )
    data = request["data"]
    template_name = request.get("execute_template")
    generic_program = (
        template._namespace[template_name]
        if template_name is not None
        else template._program
    )
    text = template._text if isinstance(template, HTMLTemplate) else template
    generic_string = partial(
        render_program,
        generic_program,
        data,
        functions=template._runtime_functions,
        missing_key=text.missing_key,
        format_mode=text.format_mode,
        _namespace=template._namespace,
        budget=text.budget,
        sandbox=text.sandbox,
    )
    link = partial(
        link_program,
        template._linked_program.program,
        template._runtime_functions,
    )
    linked = link()
    optimized_string = (
        partial(template.render_template, template_name, data)
        if template_name is not None
        else partial(template.render, data)
    )
    if fixture.get("mode", "warm_render") == "cold_render":
        raise ValueError("linked IR A/B does not compare cold template construction")
    if fixture.get("mode") == "writer_render":
        generic_writer = StringIO()
        optimized_writer = StringIO()

        def generic() -> str:
            generic_writer.seek(0)
            generic_writer.truncate(0)
            render_program_to(
                generic_program,
                generic_writer,
                data,
                functions=template._runtime_functions,
                missing_key=text.missing_key,
                format_mode=text.format_mode,
                _namespace=template._namespace,
                budget=text.budget,
                sandbox=text.sandbox,
            )
            return generic_writer.getvalue()

        def optimized() -> str:
            optimized_writer.seek(0)
            optimized_writer.truncate(0)
            if template_name is None:
                template.render_to(optimized_writer, data)
            else:
                template.render_template_to(template_name, optimized_writer, data)
            return optimized_writer.getvalue()

    else:
        generic = generic_string
        optimized = optimized_string
    if generic() != optimized():
        raise RuntimeError(f"linked output differs for {fixture['id']}")
    return generic, optimized, linked, link


def _sample(operation: Callable[[], object], iterations: int) -> float:
    started = time.perf_counter_ns()
    for _ in range(iterations):
        operation()
    return (time.perf_counter_ns() - started) / iterations


def _measure(
    fixture: BenchmarkFixture,
    *,
    samples: int,
    iterations: int,
    warmup: int,
    link_samples: int,
) -> str:
    generic, optimized, linked, link = _prepare(fixture)
    for _ in range(warmup):
        generic()
        optimized()
    generic_samples: list[float] = []
    linked_samples: list[float] = []
    gc_was_enabled = gc.isenabled()
    gc.disable()
    try:
        for index in range(samples):
            order = (
                ((generic, generic_samples), (optimized, linked_samples))
                if index % 2 == 0
                else ((optimized, linked_samples), (generic, generic_samples))
            )
            for operation, values in order:
                values.append(_sample(operation, iterations))
    finally:
        if gc_was_enabled:
            gc.enable()
    generic_median = statistics.median(generic_samples)
    linked_median = statistics.median(linked_samples)
    delta = (linked_median / generic_median - 1.0) * 100.0
    link_timings = [_sample(link, 1) for _ in range(link_samples)]
    tracemalloc.start()
    before, _ = tracemalloc.get_traced_memory()
    retained_link = link()
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    if retained_link.program is not linked.program:
        raise RuntimeError("linking did not preserve the generic program")
    return (
        f"{fixture['id']}: generic={generic_median:.1f} ns/op, "
        f"linked={linked_median:.1f} ns/op, delta={delta:+.2f}%, "
        f"linked_writes={linked.linked_write_count}, "
        f"linked_controls={linked.linked_control_count}, "
        f"template_calls={linked.template_call_count}, "
        f"link={statistics.median(link_timings):.1f} ns, "
        f"link_retained={current - before} B, link_peak={peak - before} B"
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Run paired, alternating samples for representative fixture shapes."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fixtures", nargs="*", type=Path)
    parser.add_argument("--samples", type=int, default=15)
    parser.add_argument("--iterations", type=int, default=2_000)
    parser.add_argument("--warmup", type=int, default=300)
    parser.add_argument("--link-samples", type=int, default=25)
    arguments = parser.parse_args(argv)
    if (
        arguments.samples < 1
        or arguments.iterations < 1
        or arguments.warmup < 0
        or arguments.link_samples < 1
    ):
        parser.error(
            "samples and iterations must be positive; warmup must be nonnegative"
        )
    paths = arguments.fixtures or [FIXTURE_ROOT / name for name in DEFAULT_FIXTURES]
    for path in paths:
        print(
            _measure(
                load_benchmark(path),
                samples=arguments.samples,
                iterations=arguments.iterations,
                warmup=arguments.warmup,
                link_samples=arguments.link_samples,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
