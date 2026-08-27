"""Directory loaders for the miniature pure Python Helm workflow."""

from __future__ import annotations

import importlib
from collections.abc import Mapping
from pathlib import Path
from typing import Protocol, cast

from gotpl.funcs.helm import MissingOptionalDependencyError

from .models import Chart


class _YamlModule(Protocol):
    def safe_load(self, stream: str) -> object: ...


def _yaml() -> _YamlModule:
    try:
        return cast(_YamlModule, importlib.import_module("yaml"))
    except ImportError as error:
        raise MissingOptionalDependencyError(
            'Helm chart loading requires `pip install "gotpl[helm]"`'
        ) from error


def load_values(path: str | Path) -> dict[str, object]:
    """Load a Helm values YAML file as a string-keyed mapping."""

    source = Path(path)
    parsed = _yaml().safe_load(source.read_text(encoding="utf-8"))
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
    metadata_value = _yaml().safe_load(chart_file.read_text(encoding="utf-8"))
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
    defaults = (
        load_values(root / "values.yaml") if (root / "values.yaml").is_file() else {}
    )
    return Chart(
        name=_required_string(metadata, "name"),
        version=_required_string(metadata, "version"),
        api_version=_string(metadata, "apiVersion", "v2"),
        app_version=_string(metadata, "appVersion", ""),
        chart_type=_string(metadata, "type", "application"),
        description=_string(metadata, "description", ""),
        templates=templates,
        values=defaults,
        files=files,
        dependencies=tuple(dependencies),
    )


def _required_string(values: Mapping[object, object], key: str) -> str:
    value = values.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"Chart.yaml field {key!r} is required")
    return value


def _string(values: Mapping[object, object], key: str, default: str) -> str:
    value = values.get(key, default)
    return str(value) if value is not None else default


__all__ = ["load_chart", "load_values"]
