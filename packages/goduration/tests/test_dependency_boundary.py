import ast
import tomllib
from pathlib import Path
from typing import cast

import goduration

PACKAGE_ROOT = Path(__file__).parents[1]
SOURCE_ROOT = PACKAGE_ROOT / "src" / "goduration"


def test_goduration_has_no_gotpl_imports() -> None:
    imported_roots: set[str] = set()
    for path in SOURCE_ROOT.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_roots.update(
                    alias.name.partition(".")[0] for alias in node.names
                )
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                imported_roots.add(node.module.partition(".")[0])

    assert "gotpl" not in imported_roots


def test_goduration_declares_no_runtime_dependencies() -> None:
    raw = cast(
        dict[str, object],
        tomllib.loads((PACKAGE_ROOT / "pyproject.toml").read_text(encoding="utf-8")),
    )
    project = cast(dict[str, object], raw["project"])

    assert project["dependencies"] == []


def test_top_level_exports_its_version() -> None:
    assert "__version__" in goduration.__all__
    assert goduration.__version__ == "0.1.0"
