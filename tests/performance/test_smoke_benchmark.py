from pathlib import Path

import pytest

import benchmarks.compare as benchmark_compare
import benchmarks.history as benchmark_history
import benchmarks.linked_ir as linked_ir_benchmark
import benchmarks.memory as benchmark_memory
from benchmarks.async_runtime import (
    measure_async_runtime,
    measure_async_runtime_samples,
)
from benchmarks.backend_feasibility import measure_dispatch_upper_bound
from benchmarks.call_dispatch import measure_call_dispatch
from benchmarks.compare import (
    compare_samples,
    load_benchmark,
    measure_python,
    summarize_measurements,
)
from benchmarks.html_replacements import measure_html_replacements
from benchmarks.memory import measure_python_memory, tracemalloc_available
from benchmarks.parser_baseline import (
    ParserComparison,
    compare_parser_samples,
    measure_python_parser,
)
from benchmarks.printf_cache import measure_printf_cache
from benchmarks.sync_guard import measure_sync_guard
from benchmarks.url_processor import measure_url_processor

PROJECT_ROOT = Path(__file__).parents[2]
FIXTURE = PROJECT_ROOT / "benchmarks" / "fixtures" / "literal.json"
ALL_FIXTURES = sorted((PROJECT_ROOT / "benchmarks" / "fixtures").glob("*.json"))


def test_shared_benchmark_fixture_ids_are_unique_and_loadable() -> None:
    fixtures = [load_benchmark(path) for path in ALL_FIXTURES]
    identifiers = [fixture["id"] for fixture in fixtures]

    assert len(fixtures) == 10
    assert len(set(identifiers)) == len(identifiers)


def test_python_smoke_benchmark_produces_machine_readable_result() -> None:
    fixture = load_benchmark(FIXTURE)
    result = measure_python(fixture)
    assert result["runtime"] == "python"
    assert result["case_id"] == "text/literal"
    assert result["mode"] == "warm_render"
    assert result["iterations"] == 20000
    assert isinstance(result["ns_per_op"], float)
    assert result["ns_per_op"] > 0
    assert result["allocations_per_op"] is None
    assert result["bytes_per_op"] is None
    assert len(result["output_sha256"]) == 64


def test_sprig_heavy_smoke_benchmark_uses_versioned_profile() -> None:
    fixture = load_benchmark(
        PROJECT_ROOT / "benchmarks" / "fixtures" / "sprig_render.json"
    )
    fixture["warmup"] = 0
    fixture["iterations"] = 1

    result = measure_python(fixture)

    assert result["case_id"] == "sprig/function-heavy"
    assert result["iterations"] == 1
    assert result["ns_per_op"] > 0
    assert len(result["output_sha256"]) == 64


def test_sprig_duration_benchmark_exercises_extracted_adapter() -> None:
    fixture = load_benchmark(
        PROJECT_ROOT / "benchmarks" / "fixtures" / "sprig_duration_render.json"
    )
    fixture["warmup"] = 0
    fixture["iterations"] = 1

    result = measure_python(fixture)

    assert result["case_id"] == "sprig/duration-heavy"
    assert result["ns_per_op"] > 0
    assert len(result["output_sha256"]) == 64


def test_html_smoke_benchmark_uses_contextual_engine() -> None:
    fixture = load_benchmark(
        PROJECT_ROOT / "benchmarks" / "fixtures" / "html_render.json"
    )
    fixture["warmup"] = 0
    fixture["iterations"] = 1

    result = measure_python(fixture)

    assert result["case_id"] == "html/contextual-render"
    assert result["iterations"] == 1
    assert result["ns_per_op"] > 0


def test_linked_ir_benchmark_checks_paired_execution(
    capsys: pytest.CaptureFixture[str],
) -> None:
    fixture = PROJECT_ROOT / "benchmarks" / "fixtures" / "text_render.json"

    assert (
        linked_ir_benchmark.main(
            [str(fixture), "--samples", "1", "--iterations", "1", "--warmup", "0"]
        )
        == 0
    )
    output = capsys.readouterr().out
    assert "text/control-render" in output
    assert "generic=" in output
    assert "linked=" in output


@pytest.mark.parametrize(
    "filename, expected_mode",
    [
        ("text_cold.json", "cold_render"),
        ("text_writer.json", "writer_render"),
        ("named_render.json", "named_render"),
        ("named_large_render.json", "named_render"),
    ],
)
def test_phase_specific_benchmarks_use_the_declared_public_path(
    filename: str,
    expected_mode: str,
) -> None:
    fixture = load_benchmark(PROJECT_ROOT / "benchmarks" / "fixtures" / filename)
    fixture["warmup"] = 0
    fixture["iterations"] = 1

    result = measure_python(fixture)

    assert result["mode"] == expected_mode
    assert result["iterations"] == 1
    assert result["ns_per_op"] > 0
    assert len(result["output_sha256"]) == 64


def test_benchmark_distribution_preserves_samples_and_variance() -> None:
    result = summarize_measurements([10.0, 12.0, 11.0])

    assert result["values"] == [10.0, 12.0, 11.0]
    assert result["median"] == 11.0
    assert result["minimum"] == 10.0
    assert result["maximum"] == 12.0
    assert result["relative_standard_deviation"] > 0


def test_sampled_comparison_preserves_go_allocation_distributions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = load_benchmark(FIXTURE)
    python = measure_python(fixture)
    go = python.copy()
    go["runtime"] = "go"
    go["allocations_per_op"] = 2.0
    go["bytes_per_op"] = 128.0
    comparison: benchmark_compare.ComparisonResult = {
        "schema_version": 1,
        "case_id": fixture["id"],
        "python": python,
        "go": go,
        "python_to_go_ratio": 2.0,
    }

    def fake_compare(_path: Path) -> benchmark_compare.ComparisonResult:
        return comparison

    monkeypatch.setattr(benchmark_compare, "compare", fake_compare)

    result = compare_samples(FIXTURE, samples=2)

    assert result["go_allocations_per_op"]["values"] == [2.0, 2.0]
    assert result["go_bytes_per_op"]["values"] == [128.0, 128.0]


def test_single_benchmark_sample_has_zero_variance() -> None:
    assert summarize_measurements([10.0])["relative_standard_deviation"] == 0.0

    with pytest.raises(ValueError, match="at least one"):
        summarize_measurements([])
    with pytest.raises(ValueError, match="sample count"):
        compare_samples(FIXTURE, samples=0)


def test_comparison_rejects_mismatched_rendered_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = load_benchmark(FIXTURE)
    python_result = measure_python(fixture)
    go_result = python_result.copy()
    go_result["runtime"] = "go"
    go_result["output_sha256"] = "0" * 64

    def fake_python(
        _fixture: benchmark_compare.BenchmarkFixture,
    ) -> benchmark_compare.WarmBenchmarkResult:
        return python_result

    def fake_go(_path: Path) -> benchmark_compare.WarmBenchmarkResult:
        return go_result

    monkeypatch.setattr(benchmark_compare, "measure_python", fake_python)
    monkeypatch.setattr(benchmark_compare, "measure_go", fake_go)

    with pytest.raises(RuntimeError, match="outputs differ"):
        benchmark_compare.compare(FIXTURE)


def test_python_parser_benchmark_reports_each_m1_phase() -> None:
    fixture = load_benchmark(PROJECT_ROOT / "benchmarks" / "fixtures" / "parser.json")
    fixture["warmup"] = 0
    fixture["iterations"] = 1

    results = measure_python_parser(fixture)

    assert [result["mode"] for result in results] == [
        "parse",
        "compile",
        "parse_compile",
    ]
    assert all(result["ns_per_op"] > 0 for result in results)


def test_sampled_parser_comparison_preserves_variance_and_go_allocations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = load_benchmark(PROJECT_ROOT / "benchmarks" / "fixtures" / "parser.json")
    phase = measure_python_parser(fixture)[0]
    go = phase.copy()
    go["runtime"] = "go"
    go["allocations_per_op"] = 5.0
    go["bytes_per_op"] = 256.0
    comparison: ParserComparison = {
        "schema_version": 1,
        "case_id": fixture["id"],
        "python_parse": phase,
        "python_compile": phase,
        "python_parse_compile": phase,
        "go_parse": go,
        "python_parse_compile_to_go_parse_ratio": 2.0,
    }

    def fake_compare(_path: Path) -> ParserComparison:
        return comparison

    monkeypatch.setattr("benchmarks.parser_baseline.compare_parser", fake_compare)

    result = compare_parser_samples(
        PROJECT_ROOT / "benchmarks" / "fixtures" / "parser.json", samples=2
    )

    assert result["samples"] == 2
    assert result["python_parse_ns_per_op"]["values"] == [
        phase["ns_per_op"],
        phase["ns_per_op"],
    ]
    assert result["go_allocations_per_op"]["median"] == 5.0
    assert result["go_bytes_per_op"]["median"] == 256.0


@pytest.mark.asyncio
async def test_async_benchmark_reports_latency_and_throughput() -> None:
    result = await measure_async_runtime(iterations=2, warmup=0)

    assert result["schema_version"] == 1
    for name in (
        "sync_function",
        "async_vm_sync_function",
        "async_vm_immediate_coroutine",
        "async_vm_scheduled_coroutine",
        "async_vm_concurrent_coroutines",
    ):
        measurement = result[name]
        assert measurement["iterations"] == 2
        assert measurement["ns_per_op"] > 0
        assert measurement["operations_per_second"] > 0
    assert result["async_no_await_to_sync_ratio"] > 0


@pytest.mark.asyncio
async def test_sampled_async_benchmark_preserves_raw_distributions() -> None:
    result = await measure_async_runtime_samples(
        samples=2,
        iterations=2,
        warmup=0,
        concurrency=2,
    )

    assert result["samples"] == 2
    assert len(result["sync_function_ns_per_op"]["values"]) == 2
    assert len(result["async_vm_sync_function_ns_per_op"]["values"]) == 2
    assert len(result["async_vm_immediate_coroutine_ns_per_op"]["values"]) == 2
    assert len(result["async_vm_scheduled_coroutine_ns_per_op"]["values"]) == 2
    assert len(result["async_vm_concurrent_coroutines_ns_per_op"]["values"]) == 2
    assert len(result["async_no_await_to_sync_ratio"]["values"]) == 2


def test_sync_guard_benchmark_restores_the_runtime_boundary() -> None:
    result = measure_sync_guard(samples=1, iterations=2)

    assert result["schema_version"] == 1
    assert result["samples"] == 1
    assert result["iterations_per_sample"] == 2
    assert result["checked_median_ns_per_op"] > 0
    assert result["bypassed_median_ns_per_op"] > 0
    assert result["checked_to_bypassed_ratio"] > 0


def test_prepared_callable_dispatch_benchmark_reports_both_paths() -> None:
    result = measure_call_dispatch(samples=1, iterations=2)

    assert result["schema_version"] == 1
    assert result["samples"] == 1
    assert result["iterations_per_sample"] == 2
    assert result["generic_median_ns_per_op"] > 0
    assert result["prepared_median_ns_per_op"] > 0
    assert result["generic_to_prepared_ratio"] > 0


def test_html_replacement_benchmark_checks_equivalent_outputs() -> None:
    result = measure_html_replacements(samples=1, iterations=2)

    assert result["schema_version"] == 1
    assert result["samples"] == 1
    assert result["iterations_per_sample"] == 2
    assert result["generator_median_ns_per_op"] > 0
    assert result["chained_median_ns_per_op"] > 0
    assert result["generator_to_chained_ratio"] > 0


def test_printf_cache_benchmark_checks_equivalent_parses() -> None:
    result = measure_printf_cache(samples=1, iterations=2)

    assert result["schema_version"] == 1
    assert result["samples"] == 1
    assert result["iterations_per_sample"] == 2
    assert result["uncached_median_ns_per_op"] > 0
    assert result["cached_median_ns_per_op"] > 0
    assert result["uncached_to_cached_ratio"] > 0


def test_url_processor_benchmark_checks_equivalent_outputs() -> None:
    result = measure_url_processor(samples=1, iterations=2)

    assert result["schema_version"] == 1
    assert result["samples"] == 1
    assert result["iterations_per_sample"] == 2
    assert result["branching_median_ns_per_op"] > 0
    assert result["table_median_ns_per_op"] > 0
    assert result["branching_to_table_ratio"] > 0


@pytest.mark.skipif(
    not tracemalloc_available(), reason="interpreter does not provide tracemalloc"
)
def test_python_memory_benchmark_labels_tracemalloc_metrics() -> None:
    fixture = load_benchmark(FIXTURE)
    fixture["warmup"] = 0
    fixture["iterations"] = 1

    result = measure_python_memory(fixture, samples=2)

    assert result["schema_version"] == 1
    assert result["runtime"] == "python"
    assert result["case_id"] == "text/literal"
    assert result["mode"] == "warm_render"
    assert result["samples"] == 2
    assert result["measurement"] == "tracemalloc-single-render"
    assert len(result["output_sha256"]) == 64
    assert len(result["peak_traced_bytes_per_render"]["values"]) == 2
    assert result["peak_traced_bytes_per_render"]["median"] > 0
    assert len(result["retained_traced_bytes_per_render"]["values"]) == 2
    assert len(result["retained_traced_blocks_per_render"]["values"]) == 2


def test_python_memory_benchmark_reports_unavailable_tracemalloc(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = load_benchmark(FIXTURE)
    monkeypatch.setattr(benchmark_memory, "_tracemalloc", None)

    with pytest.raises(RuntimeError, match="requires tracemalloc"):
        measure_python_memory(fixture, samples=1)


def test_backend_feasibility_benchmark_reports_dispatch_upper_bound() -> None:
    fixture = load_benchmark(FIXTURE)

    result = measure_dispatch_upper_bound(fixture, iterations=2, warmup=0)

    assert result["schema_version"] == 1
    assert result["case_id"] == "text/literal"
    assert result["iterations"] == 2
    assert result["measurement"] == "cprofile-dispatch-upper-bound"
    assert result["total_seconds"] > 0
    assert result["dispatcher_self_seconds"] > 0
    assert 0 < result["dispatcher_self_fraction"] < 1
    assert result["maximum_dispatch_only_speedup"] > 1
    assert len(result["output_sha256"]) == 64


def test_history_bundle_preserves_revision_and_sample_results(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = load_benchmark(FIXTURE)
    measured = measure_python(fixture)
    distribution = summarize_measurements([measured["ns_per_op"]])
    sampled: benchmark_compare.SampledComparison = {
        "schema_version": 1,
        "case_id": fixture["id"],
        "samples": 1,
        "python_ns_per_op": distribution,
        "go_ns_per_op": distribution,
        "python_to_go_ratio": summarize_measurements([1.0]),
        "go_allocations_per_op": summarize_measurements([2.0]),
        "go_bytes_per_op": summarize_measurements([128.0]),
        "output_sha256": measured["output_sha256"],
        "environment": {
            "python": "test",
            "go": "test",
            "platform": "test",
            "machine": "test",
        },
    }

    def fake_compare(
        _path: Path, *, samples: int = 7
    ) -> benchmark_compare.SampledComparison:
        assert samples == 1
        return sampled

    monkeypatch.setattr(benchmark_history, "compare_samples", fake_compare)
    monkeypatch.setattr(benchmark_history, "_revision", lambda: "revision")

    result = benchmark_history.build_history([FIXTURE], samples=1)

    assert result["schema_version"] == 1
    assert result["revision"] == "revision"
    assert result["samples"] == 1
    assert result["comparisons"] == [sampled]
    assert result["generated_at"].endswith("Z")
