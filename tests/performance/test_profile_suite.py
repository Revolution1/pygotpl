from pathlib import Path

import pytest

import benchmarks.profile_suite as profile_suite
from benchmarks.memory import tracemalloc_available
from benchmarks.profile_suite import build_profile_suite

PROJECT_ROOT = Path(__file__).parents[2]


@pytest.mark.skipif(
    not tracemalloc_available(), reason="interpreter does not provide tracemalloc"
)
def test_profile_suite_covers_representative_runtime_boundaries() -> None:
    result = build_profile_suite(
        iterations=3,
        sampling_seconds=0.01,
        sampling_interval=0.001,
        allocation_iterations=1,
        top=5,
    )

    assert result["schema_version"] == 1
    assert result["environment"]["python"]
    assert {workload["id"] for workload in result["workloads"]} == {
        "parser/parse-compile",
        "text/control-render",
        "html/contextual-render",
        "sprig/function-heavy",
        "async/scheduled-callback",
    }
    for workload in result["workloads"]:
        assert workload["deterministic"]["total_seconds"] > 0
        assert workload["deterministic"]["entries"]
        assert workload["sampling"]["samples"] > 0
        assert workload["sampling"]["completed_operations"] >= 3
        assert workload["sampling"]["entries"]
        assert workload["allocation"]["peak_traced_bytes"] > 0
        assert workload["allocation"]["entries"]


def test_profile_suite_rejects_invalid_measurement_configuration() -> None:
    with pytest.raises(ValueError, match="configuration"):
        build_profile_suite(iterations=0)
    with pytest.raises(ValueError, match="configuration"):
        build_profile_suite(sampling_seconds=0)
    with pytest.raises(ValueError, match="configuration"):
        build_profile_suite(sampling_interval=0)
    with pytest.raises(ValueError, match="configuration"):
        build_profile_suite(allocation_iterations=0)
    with pytest.raises(ValueError, match="configuration"):
        build_profile_suite(top=0)


def test_profile_suite_reports_missing_tracemalloc(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(profile_suite, "_tracemalloc", None)

    with pytest.raises(RuntimeError, match="requires tracemalloc"):
        build_profile_suite(
            iterations=1,
            sampling_seconds=0.001,
            sampling_interval=0.001,
            allocation_iterations=1,
            top=1,
        )
