from __future__ import annotations

import pytest

from scripts.check_coverage import CoverageThresholdError, validate_coverage


def _report(
    *,
    covered_lines: int = 981,
    statements: int = 1000,
    covered_branches: int = 951,
    branches: int = 1000,
) -> dict[str, object]:
    return {
        "totals": {
            "covered_lines": covered_lines,
            "num_statements": statements,
            "covered_branches": covered_branches,
            "num_branches": branches,
        }
    }


def test_coverage_gate_accepts_each_metric_at_its_own_threshold() -> None:
    assert validate_coverage(_report()) == pytest.approx((98.1, 95.1))


@pytest.mark.parametrize(
    ("report", "message"),
    [
        (_report(covered_lines=979), "statement coverage 97.9000% is below 98.0000%"),
        (_report(covered_branches=949), "branch coverage 94.9000% is below 95.0000%"),
    ],
)
def test_coverage_gate_rejects_each_metric_independently(
    report: dict[str, object], message: str
) -> None:
    with pytest.raises(CoverageThresholdError, match=message):
        validate_coverage(report)


@pytest.mark.parametrize(
    "report",
    [
        {},
        {"totals": {}},
        _report(statements=0),
        _report(branches=0),
    ],
)
def test_coverage_gate_rejects_incomplete_reports(report: dict[str, object]) -> None:
    with pytest.raises(ValueError, match="invalid coverage JSON totals"):
        validate_coverage(report)
