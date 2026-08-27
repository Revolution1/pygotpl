from typing import cast

from benchmarks.sandbox import build_report


def test_sandbox_benchmark_validates_all_rendering_modes() -> None:
    report = build_report(iterations=1, samples=1)

    assert report["schema_version"] == 1
    timings = cast(dict[str, object], report["warm_render_ns_per_op"])
    assert set(timings) == {"default", "budgeted", "strict"}
    ratios = cast(dict[str, float], report["ratios"])
    assert ratios["budgeted_to_default"] > 0
    assert ratios["strict_to_default"] > 0
