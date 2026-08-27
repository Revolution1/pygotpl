from __future__ import annotations

from collections.abc import Mapping
from typing import cast

import pytest

from benchmarks import helm_runtime
from benchmarks.helm_runtime import DEFAULT_FIXTURE, benchmark


def test_helm_runtime_benchmark_smoke_preserves_fixture_and_phase_boundaries() -> None:
    result = benchmark(
        DEFAULT_FIXTURE,
        samples=1,
        iterations=1,
        memory_samples=1 if helm_runtime.tracemalloc_available() else 0,
        profile_iterations=1,
        top=3,
    )

    assert result["schema_version"] == 1
    assert result["fixture"] == "helm-runtime-v1"
    assert result["reference"] == "helm-v4.2.3"
    timings = cast(Mapping[str, object], result["timings"])
    memory = cast(Mapping[str, object], result["memory"])
    output_sha256 = cast(Mapping[str, object], result["output_sha256"])
    assert set(timings) == {
        "core_compile",
        "core_warm_batch",
        "helm_static_cold",
        "helm_tpl_cold",
    }
    assert set(memory) == (
        set(timings) if helm_runtime.tracemalloc_available() else set()
    )
    assert output_sha256 == {
        "core": "8141b62bf4b9ab6228b5c0d5504e1916e356b83af0fda66369ec3c4e9c29c71b",
        "helm": "4047ac72b968129630af803352e25ec31d9758200746e2f2c7ceff9974664069",
    }


def test_helm_runtime_benchmark_reports_unavailable_tracemalloc(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("benchmarks.helm_runtime._tracemalloc", None)

    with pytest.raises(RuntimeError, match="requires tracemalloc"):
        benchmark(
            DEFAULT_FIXTURE,
            samples=1,
            iterations=1,
            memory_samples=1,
            profile_iterations=1,
            top=1,
        )


def test_helm_runtime_benchmark_can_skip_memory_sampling() -> None:
    result = benchmark(
        DEFAULT_FIXTURE,
        samples=1,
        iterations=1,
        memory_samples=0,
        profile_iterations=1,
        top=1,
    )

    assert result["memory"] == {}
