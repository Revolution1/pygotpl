"""Enforce independent statement and branch coverage thresholds."""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import cast


class CoverageThresholdError(RuntimeError):
    """Report that an independently measured coverage metric is too low."""


def _positive_integer(totals: Mapping[str, object], name: str) -> int:
    value = totals.get(name)
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ValueError("invalid coverage JSON totals")
    return value


def _nonnegative_integer(totals: Mapping[str, object], name: str) -> int:
    value = totals.get(name)
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError("invalid coverage JSON totals")
    return value


def validate_coverage(
    report: Mapping[str, object],
    *,
    statement_minimum: float = 98.0,
    branch_minimum: float = 95.0,
) -> tuple[float, float]:
    """Validate and return exact statement and branch percentages."""

    raw_totals = report.get("totals")
    if not isinstance(raw_totals, Mapping):
        raise ValueError("invalid coverage JSON totals")
    totals = cast(Mapping[str, object], raw_totals)
    statements = _positive_integer(totals, "num_statements")
    branches = _positive_integer(totals, "num_branches")
    covered_lines = _nonnegative_integer(totals, "covered_lines")
    covered_branches = _nonnegative_integer(totals, "covered_branches")
    if covered_lines > statements or covered_branches > branches:
        raise ValueError("invalid coverage JSON totals")

    statement_percent = covered_lines * 100.0 / statements
    branch_percent = covered_branches * 100.0 / branches
    if statement_percent < statement_minimum:
        raise CoverageThresholdError(
            f"statement coverage {statement_percent:.4f}% is below "
            f"{statement_minimum:.4f}%"
        )
    if branch_percent < branch_minimum:
        raise CoverageThresholdError(
            f"branch coverage {branch_percent:.4f}% is below {branch_minimum:.4f}%"
        )
    return statement_percent, branch_percent


def main(argv: Sequence[str] | None = None) -> int:
    """Validate a Coverage.py JSON report from the command line."""

    parser = argparse.ArgumentParser()
    parser.add_argument("report", type=Path)
    parser.add_argument("--statement-minimum", type=float, default=98.0)
    parser.add_argument("--branch-minimum", type=float, default=95.0)
    arguments = parser.parse_args(argv)
    report = cast(
        Mapping[str, object], json.loads(arguments.report.read_text(encoding="utf-8"))
    )
    statements, branches = validate_coverage(
        report,
        statement_minimum=arguments.statement_minimum,
        branch_minimum=arguments.branch_minimum,
    )
    print(f"statement coverage: {statements:.4f}%")
    print(f"branch coverage: {branches:.4f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
