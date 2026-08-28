"""Directory loaders for the miniature pure Python Helm workflow."""

from __future__ import annotations

import shutil
import tarfile
import tempfile
from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path
from typing import cast

from gotpl.funcs.helm import MissingOptionalDependencyError
from gotpl.funcs.helm.functions import load_yaml

from .models import Chart


def _load_yaml(stream: str) -> object:
    try:
        return load_yaml(stream)
    except MissingOptionalDependencyError as error:
        raise MissingOptionalDependencyError(
            'Helm chart loading requires `pip install "gotpl[helm]"`'
        ) from error


def load_values(path: str | Path) -> dict[str, object]:
    """Load a Helm values YAML file as a string-keyed mapping."""

    source = Path(path)
    parsed = _load_yaml(source.read_text(encoding="utf-8"))
    if parsed is None:
        return {}
    if not isinstance(parsed, dict):
        raise ValueError(f"values file {source} must contain a YAML mapping")
    mapping = cast(Mapping[object, object], parsed)
    return {str(key): value for key, value in mapping.items()}


def load_chart(path: str | Path) -> Chart:
    """Load an unpacked Helm chart directory without invoking Helm or Go."""

    root = Path(path)
    if not root.is_dir():
        raise ValueError(f"chart path {root} must be a directory")
    chart_file = root / "Chart.yaml"
    if not chart_file.is_file():
        raise ValueError(f"chart directory {root} does not contain Chart.yaml")
    metadata_value = _load_yaml(chart_file.read_text(encoding="utf-8"))
    if not isinstance(metadata_value, dict):
        raise ValueError("Chart.yaml must contain a YAML mapping")
    metadata = cast(Mapping[object, object], metadata_value)
    templates = (
        {
            file.relative_to(root).as_posix(): file.read_text(encoding="utf-8")
            for file in sorted((root / "templates").rglob("*"))
            if file.is_file()
        }
        if (root / "templates").is_dir()
        else {}
    )
    excluded = {"Chart.yaml", "Chart.lock", "values.yaml", "values.schema.json"}
    files: dict[str, bytes] = {}
    for file in sorted(root.rglob("*")):
        if not file.is_file():
            continue
        relative = file.relative_to(root).as_posix()
        if (
            relative in excluded
            or relative.startswith("templates/")
            or relative.startswith("charts/")
        ):
            continue
        files[relative] = file.read_bytes()
    dependencies: list[Chart] = []
    charts_dir = root / "charts"
    if charts_dir.is_dir():
        for child in sorted(charts_dir.iterdir()):
            if child.is_dir() and (child / "Chart.yaml").is_file():
                dependencies.append(load_chart(child))
            elif child.is_file() and child.name.endswith((".tgz", ".tar.gz")):
                dependencies.append(_load_chart_archive(child))
    defaults = (
        load_values(root / "values.yaml") if (root / "values.yaml").is_file() else {}
    )
    chart = Chart(
        name=_required_string(metadata, "name"),
        version=_required_string(metadata, "version"),
        api_version=_string(metadata, "apiVersion", "v2"),
        app_version=_string(metadata, "appVersion", ""),
        chart_type=_string(metadata, "type", "application"),
        description=_string(metadata, "description", ""),
        annotations=_string_mapping(metadata, "annotations"),
        templates=templates,
        values=defaults,
        files=files,
        dependencies=tuple(dependencies),
    )
    return replace(
        chart,
        dependencies=_configure_dependencies(metadata, chart.dependencies),
    )


def _required_string(values: Mapping[object, object], key: str) -> str:
    value = values.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"Chart.yaml field {key!r} is required")
    return value


def _string(values: Mapping[object, object], key: str, default: str) -> str:
    value = values.get(key, default)
    return str(value) if value is not None else default


def _string_mapping(values: Mapping[object, object], key: str) -> dict[str, str]:
    value = values.get(key, {})
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ValueError(f"Chart.yaml field {key!r} must contain a mapping")
    mapping = cast(Mapping[object, object], value)
    return {str(item_key): str(item_value) for item_key, item_value in mapping.items()}


def _configure_dependencies(
    metadata: Mapping[object, object], loaded: tuple[Chart, ...]
) -> tuple[Chart, ...]:
    raw = metadata.get("dependencies")
    if raw is None:
        return loaded
    if not isinstance(raw, list):
        raise ValueError("Chart.yaml field 'dependencies' must contain a list")
    configured: list[Chart] = []
    declared_names: set[str] = set()
    for item in cast(list[object], raw):
        if not isinstance(item, Mapping):
            raise ValueError("Chart.yaml dependencies must contain mappings")
        spec = cast(Mapping[object, object], item)
        dependency_name = spec.get("name")
        if not isinstance(dependency_name, str) or not dependency_name:
            raise ValueError("Chart.yaml dependency field 'name' is required")
        declared_names.add(dependency_name)
        child = next((value for value in loaded if value.name == dependency_name), None)
        if child is None:
            raise ValueError(f"chart dependency {dependency_name!r} is missing")
        alias = spec.get("alias")
        if alias is not None and (not isinstance(alias, str) or not alias):
            raise ValueError(
                f"Chart.yaml dependency {dependency_name!r} has an invalid alias"
            )
        tags_value = spec.get("tags", [])
        if not isinstance(tags_value, list):
            raise ValueError(
                f"Chart.yaml dependency {dependency_name!r} tags must be strings"
            )
        tags = cast(list[object], tags_value)
        if not all(isinstance(tag, str) for tag in tags):
            raise ValueError(
                f"Chart.yaml dependency {dependency_name!r} tags must be strings"
            )
        import_values = spec.get("import-values", [])
        if not isinstance(import_values, list):
            raise ValueError(
                f"Chart.yaml dependency {dependency_name!r} import-values "
                "must be a list"
            )
        configured.append(
            replace(
                child,
                name=alias or child.name,
                dependency_condition=_string(spec, "condition", ""),
                dependency_tags=tuple(cast(list[str], tags)),
                dependency_import_values=tuple(cast(list[object], import_values)),
            )
        )
    configured.extend(child for child in loaded if child.name not in declared_names)
    return tuple(configured)


def _load_chart_archive(path: Path) -> Chart:
    with tempfile.TemporaryDirectory(prefix="gotpl-helm-") as temporary:
        destination = Path(temporary)
        roots: set[str] = set()
        with tarfile.open(path, mode="r:*") as archive:
            members = archive.getmembers()
            for member in members:
                parts = Path(member.name).parts
                if not parts or member.name.startswith("/") or ".." in parts:
                    raise ValueError(
                        f"unsafe path in chart archive {path}: {member.name}"
                    )
                if len(parts) == 2 and parts[1] == "Chart.yaml":
                    roots.add(parts[0])
                if member.isdir():
                    continue
                if not member.isfile():
                    raise ValueError(
                        f"unsupported entry in chart archive {path}: {member.name}"
                    )
                source = archive.extractfile(member)
                if source is None:
                    raise ValueError(
                        f"cannot read entry in chart archive {path}: {member.name}"
                    )
                target = destination.joinpath(*parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                with target.open("wb") as output:
                    shutil.copyfileobj(source, output)
        if len(roots) != 1:
            raise ValueError(
                f"chart archive {path} must contain one top-level Chart.yaml"
            )
        return load_chart(destination / roots.pop())


__all__ = ["load_chart", "load_values"]
