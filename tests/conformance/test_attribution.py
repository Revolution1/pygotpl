from __future__ import annotations

import json
import tomllib
from pathlib import Path
from typing import cast

import pytest

from .support import FIXTURE_ROOT

PINNED_LICENSE_FAMILIES = {
    "go": ("go1.27.0", "Copyright 2009 The Go Authors."),
    "sprig": ("v3.3.0", "Copyright (C) 2013-2020 Masterminds"),
}
NOTICE_PATH = Path(__file__).parents[2] / "THIRD_PARTY_NOTICES.md"
ROOT = Path(__file__).parents[2]
FIXTURES = sorted(FIXTURE_ROOT.rglob("*.json"))


@pytest.mark.parametrize("fixture_path", FIXTURES, ids=lambda path: path.stem)
def test_fixture_reference_has_registered_attribution(fixture_path: Path) -> None:
    fixture = cast(
        dict[str, object], json.loads(fixture_path.read_text(encoding="utf-8"))
    )
    reference = cast(dict[str, object], fixture["reference"])
    project = reference["project"]
    revision = reference["revision"]

    assert isinstance(project, str)
    assert project in PINNED_LICENSE_FAMILIES
    expected_revision, notice = PINNED_LICENSE_FAMILIES[project]
    assert revision == expected_revision
    assert notice in NOTICE_PATH.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    ("project_root", "expected_license_files"),
    [
        (ROOT, ["LICENSE", "THIRD_PARTY_NOTICES.md"]),
        (ROOT / "packages" / "goduration", ["LICENSE"]),
        (ROOT / "packages" / "gotime", ["LICENSE"]),
    ],
    ids=("gotpl", "goduration", "gotime"),
)
def test_distribution_uses_the_approved_apache_license(
    project_root: Path,
    expected_license_files: list[str],
) -> None:
    metadata = tomllib.loads(
        (project_root / "pyproject.toml").read_text(encoding="utf-8")
    )
    license_text = (project_root / "LICENSE").read_text(encoding="utf-8")

    assert metadata["project"]["license"] == "Apache-2.0"
    assert metadata["project"]["license-files"] == expected_license_files
    assert license_text == (ROOT / "LICENSE").read_text(encoding="utf-8")
    nonempty_lines = [line.strip() for line in license_text.splitlines() if line]
    assert nonempty_lines[0] == "Apache License"
    assert nonempty_lines[1] == "Version 2.0, January 2004"
    assert "3. Grant of Patent License." in license_text
    assert license_text.rstrip().endswith("limitations under the License.")
