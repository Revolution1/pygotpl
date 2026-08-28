from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import cast

from benchmarks.helm_chart import benchmark

FIXTURE = Path(__file__).parents[1] / "fixtures" / "helm" / "basic"


def test_complete_chart_benchmark_preserves_phase_boundaries() -> None:
    result = benchmark(
        FIXTURE,
        samples=1,
        iterations=1,
        profile_iterations=1,
        top=3,
    )

    assert result["schema_version"] == 1
    chart = cast(Mapping[str, object], result["chart"])
    output = cast(Mapping[str, object], result["output"])
    timings = cast(Mapping[str, object], result["timings"])
    assert chart["name"] == "basic"
    assert chart["version"] == "1.2.3"
    assert output["rendered_templates"] == 1
    assert output["manifests"] == 1
    assert set(timings) == {
        "chart_load",
        "chart_render_cold",
        "manifest_prepare",
        "end_to_end",
    }
    assert len(cast(list[object], result["render_profile"])) == 3
