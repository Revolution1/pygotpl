"""Executable ownership and dependency rules for the M7 architecture."""

from __future__ import annotations

import ast
import importlib.util
import tomllib
from collections.abc import Iterable
from pathlib import Path

ROOT = Path(__file__).parents[2]
GOTPL_ROOT = ROOT / "src" / "gotpl"
WORKSPACE_PACKAGES = frozenset({"goduration", "gotime"})

_ALLOWED_GOTPL_IMPORTS: dict[str, frozenset[str]] = {
    "_compat": frozenset({"_compat"}),
    "errors": frozenset(),
    "pythonic": frozenset({"pythonic"}),
    "parse": frozenset({"errors", "parse"}),
    "compile": frozenset({"compile", "parse"}),
    "runtime": frozenset({"_compat", "compile", "errors", "runtime"}),
    "runtime_engine": frozenset({"pythonic", "runtime", "template"}),
    "template": frozenset({"compile", "errors", "parse", "pythonic", "runtime"}),
    "html": frozenset({"compile", "errors", "html", "pythonic", "runtime", "template"}),
    "funcs_sprig": frozenset({"_compat", "funcs_sprig", "runtime"}),
    "funcs_slim_sprig": frozenset({"funcs_slim_sprig", "funcs_sprig"}),
    "funcs_sprout": frozenset({"_compat", "funcs_sprig", "funcs_sprout", "runtime"}),
    "funcs_helm": frozenset({"errors", "funcs_helm", "funcs_sprig"}),
    "funcs": frozenset({"funcs"}),
    "__init__": frozenset({"errors", "html", "pythonic", "runtime", "template"}),
}

_ALLOWED_WORKSPACE_IMPORTS: dict[str, frozenset[str]] = {
    "goduration": frozenset({"goduration"}),
    "gotime": frozenset({"goduration", "gotime"}),
}

_ALLOWED_GOTPL_WORKSPACE_IMPORTS: dict[str, frozenset[str]] = {
    "funcs_sprig": frozenset({"goduration", "gotime"}),
    "funcs_sprout": frozenset({"goduration", "gotime"}),
}


def _module_for(path: Path, source_root: Path) -> str:
    relative = path.relative_to(source_root).with_suffix("")
    parts = relative.parts
    return ".".join(parts[:-1] if parts[-1] == "__init__" else parts)


def _imports(path: Path, source_root: Path) -> Iterable[str]:
    module = _module_for(path, source_root)
    tree = ast.parse(path.read_text(), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            yield from (alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0:
                if node.module is not None:
                    yield node.module
                continue
            package = module.split(".")
            if path.name != "__init__.py":
                package.pop()
            if node.level > 1:
                package = package[: -(node.level - 1)]
            if node.module:
                package.extend(node.module.split("."))
            yield ".".join(package)


def _gotpl_owner(path: Path) -> str:
    relative = path.relative_to(GOTPL_ROOT)
    if relative.parts == ("runtime", "engine.py"):
        return "runtime_engine"
    if (
        relative.parts[0] == "funcs"
        and len(relative.parts) > 1
        and relative.parts[1] != "__init__.py"
    ):
        return f"funcs_{relative.parts[1]}"
    return relative.parts[0] if len(relative.parts) > 1 else relative.stem


def _gotpl_target_owner(module: str) -> str:
    parts = module.split(".")
    if len(parts) > 2 and parts[1] == "funcs":
        return f"funcs_{parts[2]}"
    return parts[1] if len(parts) > 1 else "__init__"


def test_gotpl_internal_imports_follow_owned_layers() -> None:
    violations: list[str] = []
    for path in sorted(GOTPL_ROOT.rglob("*.py")):
        owner = _gotpl_owner(path)
        for imported in _imports(path, ROOT / "src"):
            external_target = imported.split(".", 1)[0]
            if external_target in WORKSPACE_PACKAGES and external_target not in (
                _ALLOWED_GOTPL_WORKSPACE_IMPORTS.get(owner, frozenset())
            ):
                violations.append(
                    f"{path.relative_to(ROOT)}: {owner} -> {external_target}"
                )
            if not imported.startswith("gotpl"):
                continue
            target = _gotpl_target_owner(imported)
            if target not in _ALLOWED_GOTPL_IMPORTS[owner]:
                violations.append(f"{path.relative_to(ROOT)}: {owner} -> {target}")

    assert violations == []


def test_workspace_leaf_imports_follow_the_documented_graph() -> None:
    violations: list[str] = []
    for package, allowed in _ALLOWED_WORKSPACE_IMPORTS.items():
        source_root = ROOT / "packages" / package / "src"
        for path in sorted(source_root.rglob("*.py")):
            for imported in _imports(path, source_root):
                target = imported.split(".", 1)[0]
                if target == "gotpl" or (
                    target in WORKSPACE_PACKAGES and target not in allowed
                ):
                    violations.append(
                        f"{path.relative_to(ROOT)}: {package} -> {target}"
                    )

    assert violations == []


def test_workspace_metadata_graph_matches_import_policy_and_is_acyclic() -> None:
    graph: dict[str, set[str]] = {}
    for package in sorted(WORKSPACE_PACKAGES):
        metadata = tomllib.loads(
            (ROOT / "packages" / package / "pyproject.toml").read_text()
        )
        dependencies = metadata["project"]["dependencies"]
        graph[package] = {
            dependency.split(">", 1)[0].split("=", 1)[0]
            for dependency in dependencies
            if dependency.split(">", 1)[0].split("=", 1)[0] in WORKSPACE_PACKAGES
        }

    expected = {
        package: set(allowed) - {package}
        for package, allowed in _ALLOWED_WORKSPACE_IMPORTS.items()
    }
    assert graph == expected

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(package: str) -> None:
        assert package not in visiting, f"workspace dependency cycle at {package}"
        if package in visited:
            return
        visiting.add(package)
        for dependency in graph[package]:
            visit(dependency)
        visiting.remove(package)
        visited.add(package)

    for package in graph:
        visit(package)


def test_distribution_namespace_and_workspace_layout_are_canonical() -> None:
    metadata = tomllib.loads((ROOT / "pyproject.toml").read_text())

    assert metadata["project"]["name"] == "gotpl"
    assert metadata["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"] == [
        "src/gotpl"
    ]
    assert metadata["tool"]["uv"]["workspace"]["members"] == [
        "packages/goduration",
        "packages/gotime",
    ]
    assert (ROOT / "src" / "gotpl" / "funcs").is_dir()
    assert (ROOT / "src" / "gotpl" / "pythonic").is_dir()
    assert (ROOT / "src" / "gotpl" / "_compat" / "gofmt").is_dir()
    assert (ROOT / "src" / "gotpl" / "_compat" / "goregexp").is_dir()
    assert not (ROOT / "src" / "pygotpl").exists()
    assert not (ROOT / "packages" / "gofmt").exists()
    assert not (ROOT / "packages" / "goregexp").exists()
    assert importlib.util.find_spec("gotpl") is not None
    assert importlib.util.find_spec("pygotpl") is None
    assert importlib.util.find_spec("gofmt") is None
    assert importlib.util.find_spec("goregexp") is None
