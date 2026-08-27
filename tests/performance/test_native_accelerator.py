from pathlib import Path

import pytest

from benchmarks.native_accelerator import (
    evaluate_retention_gate,
    prepare_runtime_pair,
)

PROJECT_ROOT = Path(__file__).parents[2]


@pytest.mark.parametrize("fixture_name", ["text_render.json", "html_render.json"])
def test_runtime_pair_preserves_output(fixture_name: str) -> None:
    fixture = PROJECT_ROOT / "benchmarks" / "fixtures" / fixture_name
    baseline, candidate, expected = prepare_runtime_pair(fixture, runtime=None)

    assert baseline() == expected
    assert candidate() == expected


def test_retention_gate_requires_two_25_percent_improvements() -> None:
    assert evaluate_retention_gate([0.25, 0.31]) is True
    assert evaluate_retention_gate([0.24, 0.80]) is False
    assert evaluate_retention_gate([0.30]) is False


def test_runtime_pair_rejects_output_mismatch() -> None:
    fixture = PROJECT_ROOT / "benchmarks" / "fixtures" / "text_render.json"

    def wrong_runtime(program: object, data: object = None, **options: object) -> str:
        return "wrong"

    with pytest.raises(RuntimeError, match="output differs"):
        prepare_runtime_pair(fixture, runtime=wrong_runtime)
