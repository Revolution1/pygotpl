from collections.abc import Callable
from pathlib import Path

import pytest

import benchmarks.jinja_compare as jinja_compare
from benchmarks.jinja_compare import (
    JINJA_FIXTURE_DIR,
    build_jinja_report,
    load_jinja_fixture,
    measure_async_samples,
    measure_cache_samples,
    measure_fixture_samples,
    measure_memory_pair,
)
from benchmarks.memory import tracemalloc_available

FIXTURES = sorted(JINJA_FIXTURE_DIR.glob("*.json"))


def test_jinja_fixtures_are_versioned_unique_and_loadable() -> None:
    fixtures = [load_jinja_fixture(path) for path in FIXTURES]

    assert len(fixtures) == 3
    assert len({fixture["id"] for fixture in fixtures}) == len(fixtures)
    assert {fixture["engine"] for fixture in fixtures} == {"html", "text"}
    assert all(fixture["expected_output"] for fixture in fixtures)


def test_jinja_fixture_loader_rejects_unknown_keys(tmp_path: Path) -> None:
    path = tmp_path / "invalid.json"
    path.write_text(
        '{"schema_version": 1, "id": "bad", "unexpected": true}',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="fixture"):
        load_jinja_fixture(path)


@pytest.mark.parametrize("path", FIXTURES, ids=lambda path: path.stem)
def test_jinja_fixture_comparison_validates_output_and_both_phases(path: Path) -> None:
    fixture = load_jinja_fixture(path)
    fixture["warmup"] = 0
    fixture["iterations"] = 1
    fixture["cold_iterations"] = 1
    fixture["cache_iterations"] = 1

    result = measure_fixture_samples(fixture, samples=1)

    assert result["case_id"] == fixture["id"]
    assert len(result["output_sha256"]) == 64
    for phase in (result["warm_render"], result["cold_render"]):
        assert phase["gotpl_ns_per_op"]["median"] > 0
        assert phase["jinja_ns_per_op"]["median"] > 0
        assert phase["gotpl_to_jinja_ratio"]["median"] > 0


def test_jinja_cache_comparison_records_enabled_and_disabled_loading() -> None:
    fixture = load_jinja_fixture(JINJA_FIXTURE_DIR / "text_control.json")

    result = measure_cache_samples(
        fixture,
        samples=1,
        iterations=1,
        warmup=0,
    )

    assert result["cache_size"] == 400
    assert result["auto_reload"] is False
    assert result["enabled_ns_per_op"]["median"] > 0
    assert result["disabled_ns_per_op"]["median"] > 0


def test_jinja_warm_and_cold_iterations_remain_distinct(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = load_jinja_fixture(JINJA_FIXTURE_DIR / "text_control.json")
    fixture["warmup"] = 0
    fixture["iterations"] = 7
    fixture["cold_iterations"] = 3

    def fake_time(
        _operation: Callable[[], object], *, iterations: int, warmup: int
    ) -> float:
        return float(iterations + warmup)

    monkeypatch.setattr(jinja_compare, "_time_sync", fake_time)

    result = measure_fixture_samples(fixture, samples=1)

    assert result["warm_render"]["gotpl_ns_per_op"]["median"] == 7
    assert result["cold_render"]["gotpl_ns_per_op"]["median"] == 3


@pytest.mark.asyncio
async def test_jinja_async_comparison_covers_sync_and_coroutine_boundaries() -> None:
    fixture = load_jinja_fixture(JINJA_FIXTURE_DIR / "callbacks.json")

    result = await measure_async_samples(
        fixture,
        samples=1,
        iterations=2,
        warmup=0,
        concurrency=2,
    )

    assert result["concurrency"] == 2
    for mode in (
        "sync_function",
        "async_sync_function",
        "immediate_coroutine",
        "scheduled_coroutine",
        "concurrent_coroutines",
    ):
        comparison = result[mode]
        assert comparison["gotpl_ns_per_op"]["median"] > 0
        assert comparison["jinja_ns_per_op"]["median"] > 0
        assert comparison["gotpl_to_jinja_ratio"]["median"] > 0


@pytest.mark.skipif(
    not tracemalloc_available(), reason="interpreter does not provide tracemalloc"
)
def test_jinja_memory_comparison_uses_distinct_traced_metrics() -> None:
    fixture = load_jinja_fixture(JINJA_FIXTURE_DIR / "html_autoescape.json")

    result = measure_memory_pair(fixture, samples=1)

    assert result["measurement"] == "tracemalloc-single-render"
    assert result["gotpl_peak_traced_bytes_per_render"]["median"] > 0
    assert result["jinja_peak_traced_bytes_per_render"]["median"] > 0
    assert len(result["gotpl_retained_traced_bytes_per_render"]["values"]) == 1
    assert len(result["jinja_retained_traced_bytes_per_render"]["values"]) == 1


@pytest.mark.asyncio
async def test_jinja_report_records_versions_configuration_and_raw_samples() -> None:
    report = await build_jinja_report(
        [JINJA_FIXTURE_DIR / "text_control.json"],
        samples=1,
        iterations=1,
        warmup=0,
        memory_samples=0,
        concurrency=1,
    )

    assert report["schema_version"] == 1
    assert report["environment"]["python"]
    assert report["environment"]["jinja"]
    assert report["configuration"] == {
        "jinja_optimized": True,
        "jinja_auto_reload": False,
        "jinja_cache_size": 400,
        "html_policy": "gotpl-contextual-vs-jinja-autoescape",
    }
    assert len(report["fixtures"]) == 1
    assert report["cache"]["enabled_ns_per_op"]["values"]
    assert report["async"]["scheduled_coroutine"]["jinja_ns_per_op"]["values"]
    assert "memory" not in report["fixtures"][0]
