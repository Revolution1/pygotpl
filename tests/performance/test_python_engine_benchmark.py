from collections.abc import Callable
from pathlib import Path

import pytest

import benchmarks.python_engine_compare as python_engine_compare
from benchmarks.memory import tracemalloc_available
from benchmarks.python_engine_compare import (
    PYTHON_ENGINE_FIXTURE_DIR,
    build_python_engine_report,
    load_python_engine_fixture,
    measure_engine_fixture_samples,
    measure_engine_memory,
)

FIXTURES = sorted(PYTHON_ENGINE_FIXTURE_DIR.glob("*.json"))


def test_supplementary_engine_fixtures_are_unique_and_loadable() -> None:
    fixtures = [load_python_engine_fixture(path) for path in FIXTURES]

    assert len(fixtures) == 2
    assert len({fixture["id"] for fixture in fixtures}) == 2
    assert {fixture["engine"] for fixture in fixtures} == {"html", "text"}


def test_supplementary_fixture_loader_rejects_invalid_shape(tmp_path: Path) -> None:
    path = tmp_path / "invalid.json"
    path.write_text("[]", encoding="utf-8")

    with pytest.raises(ValueError, match="fixture"):
        load_python_engine_fixture(path)


@pytest.mark.parametrize("path", FIXTURES, ids=lambda path: path.stem)
def test_mako_and_chameleon_comparison_covers_warm_and_cold_paths(
    path: Path,
) -> None:
    fixture = load_python_engine_fixture(path)
    fixture["warmup"] = 0
    fixture["iterations"] = 1
    fixture["cold_iterations"] = 1

    result = measure_engine_fixture_samples(fixture, samples=1)

    assert result["case_id"] == fixture["id"]
    assert set(result["output_sha256"]) == {"gotpl", "mako", "chameleon"}
    for phase in (result["warm_render"], result["cold_render"]):
        assert phase["gotpl_ns_per_op"]["median"] > 0
        assert phase["mako_ns_per_op"]["median"] > 0
        assert phase["chameleon_ns_per_op"]["median"] > 0
        assert phase["gotpl_to_mako_ratio"]["median"] > 0
        assert phase["gotpl_to_chameleon_ratio"]["median"] > 0


@pytest.mark.skipif(
    not tracemalloc_available(), reason="interpreter does not provide tracemalloc"
)
def test_mako_and_chameleon_memory_uses_explicit_traced_metrics() -> None:
    fixture = load_python_engine_fixture(PYTHON_ENGINE_FIXTURE_DIR / "html_escape.json")

    result = measure_engine_memory(fixture, samples=1)

    assert result["measurement"] == "tracemalloc-single-render"
    assert result["gotpl_peak_traced_bytes_per_render"]["median"] > 0
    assert result["mako_peak_traced_bytes_per_render"]["median"] > 0
    assert result["chameleon_peak_traced_bytes_per_render"]["median"] > 0


def test_supplementary_warm_and_cold_iterations_remain_distinct(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = load_python_engine_fixture(
        PYTHON_ENGINE_FIXTURE_DIR / "text_interpolation.json"
    )
    fixture["warmup"] = 0
    fixture["iterations"] = 7
    fixture["cold_iterations"] = 3

    def fake_time(
        _operation: Callable[[], object], *, iterations: int, warmup: int
    ) -> float:
        return float(iterations + warmup)

    monkeypatch.setattr(python_engine_compare, "_time_operation", fake_time)

    result = measure_engine_fixture_samples(fixture, samples=1)

    assert result["warm_render"]["gotpl_ns_per_op"]["median"] == 7
    assert result["cold_render"]["gotpl_ns_per_op"]["median"] == 3


def test_supplementary_report_discloses_capability_differences() -> None:
    report = build_python_engine_report(
        [PYTHON_ENGINE_FIXTURE_DIR / "text_interpolation.json"],
        samples=1,
        iterations=1,
        warmup=0,
        memory_samples=0,
    )

    assert report["schema_version"] == 1
    assert report["environment"]["mako"] == "1.4.1"
    assert report["environment"]["chameleon"] == "4.6.0"
    assert report["capabilities"]["mako_async"] == "unsupported"
    assert report["capabilities"]["chameleon_async"] == "unsupported"
    assert report["capabilities"]["html_comparison"] == "context-appropriate escaping"
    assert len(report["fixtures"]) == 1
    assert "memory" not in report["fixtures"][0]
