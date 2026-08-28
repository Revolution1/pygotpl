"""Pure Python Helm chart-template engine used by the example CLI."""

from __future__ import annotations

import posixpath
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import cast

from gotpl.exts.helm import HelmTemplateEngine

from .models import Capabilities, Chart, Release


@dataclass(frozen=True, slots=True)
class _Renderable:
    source: str
    values: Mapping[str, object]
    base_path: str
    is_library: bool


@dataclass(frozen=True, slots=True)
class Engine:
    """Render immutable charts with Helm-compatible globals and functions."""

    strict: bool = False
    lint_mode: bool = False
    enable_dns: bool = False
    custom_functions: Mapping[str, Callable[..., object]] | None = None
    lookup: Callable[[str, str, str, str], object] | None = None

    def render(
        self,
        chart: Chart,
        values: Mapping[str, object] | None = None,
        *,
        release: Release | None = None,
        capabilities: Capabilities | None = None,
    ) -> dict[str, str]:
        """Render every non-partial template in a chart dependency tree."""

        renderables: dict[str, _Renderable] = {}
        self._collect(
            chart,
            _merge_values(chart.values, values or {}),
            chart.name,
            True,
            (release or Release()).as_values(),
            (capabilities or Capabilities.default()).as_values(),
            renderables,
        )
        ordered = sorted(
            renderables,
            key=lambda name: (name.count("/"), name),
            reverse=True,
        )
        sources = {name: renderables[name].source for name in ordered}
        template_engine = self._build_template(sources)
        contexts: dict[str, object] = {}
        for name in ordered:
            item = renderables[name]
            if item.is_library or posixpath.basename(name).startswith("_"):
                continue
            context = dict(item.values)
            context["Template"] = {
                "Name": name,
                "BasePath": item.base_path,
            }
            contexts[name] = context
        return {
            name: rendered.replace("<no value>", "")
            for name, rendered in template_engine.render(contexts).items()
        }

    async def render_async(
        self,
        chart: Chart,
        values: Mapping[str, object] | None = None,
        *,
        release: Release | None = None,
        capabilities: Capabilities | None = None,
    ) -> dict[str, str]:
        """Render a chart while awaiting asynchronous template functions."""

        renderables: dict[str, _Renderable] = {}
        self._collect(
            chart,
            _merge_values(chart.values, values or {}),
            chart.name,
            True,
            (release or Release()).as_values(),
            (capabilities or Capabilities.default()).as_values(),
            renderables,
        )
        ordered = sorted(
            renderables,
            key=lambda name: (name.count("/"), name),
            reverse=True,
        )
        sources = {name: renderables[name].source for name in ordered}
        template_engine = self._build_template(sources)
        contexts: dict[str, object] = {}
        for name in ordered:
            item = renderables[name]
            if item.is_library or posixpath.basename(name).startswith("_"):
                continue
            context = dict(item.values)
            context["Template"] = {
                "Name": name,
                "BasePath": item.base_path,
            }
            contexts[name] = context
        rendered = await template_engine.render_async(contexts)
        return {
            name: value.replace("<no value>", "") for name, value in rendered.items()
        }

    def _build_template(self, sources: Mapping[str, str]) -> HelmTemplateEngine:
        return HelmTemplateEngine.from_sources(
            sources,
            strict=self.strict,
            lint_mode=self.lint_mode,
            enable_dns=self.enable_dns,
            custom_functions=self.custom_functions,
            lookup=self.lookup,
        )

    def _collect(
        self,
        chart: Chart,
        values: Mapping[str, object],
        full_path: str,
        is_root: bool,
        release: Mapping[str, object],
        capabilities: Mapping[str, object],
        renderables: dict[str, _Renderable],
    ) -> Mapping[str, object]:
        subcharts: dict[str, object] = {}
        context: dict[str, object] = {
            "Chart": chart.metadata_values(is_root=is_root),
            "Files": chart.files,
            "Release": release,
            "Capabilities": capabilities,
            "Values": values,
            "Subcharts": subcharts,
        }
        for child in chart.dependencies:
            if not _dependency_enabled(child, values):
                continue
            child_input = values.get(child.name, {})
            child_values = _merge_values(
                child.values,
                cast(Mapping[str, object], child_input)
                if isinstance(child_input, Mapping)
                else {},
            )
            global_values = values.get("global")
            if isinstance(global_values, Mapping):
                child_values = _merge_values(
                    child_values,
                    {"global": cast(Mapping[str, object], global_values)},
                )
            child_path = f"{full_path}/charts/{child.name}"
            subcharts[child.name] = self._collect(
                child,
                child_values,
                child_path,
                False,
                release,
                capabilities,
                renderables,
            )
        for relative_name, source in chart.templates.items():
            name = posixpath.join(full_path, relative_name)
            renderables[name] = _Renderable(
                source,
                context,
                posixpath.join(full_path, "templates"),
                chart.chart_type == "library",
            )
        return context


def _merge_values(
    defaults: Mapping[str, object], overrides: Mapping[str, object]
) -> dict[str, object]:
    merged = dict(defaults)
    for key, value in overrides.items():
        current = merged.get(key)
        if isinstance(current, Mapping) and isinstance(value, Mapping):
            merged[key] = _merge_values(
                cast(Mapping[str, object], current),
                cast(Mapping[str, object], value),
            )
        else:
            merged[key] = value
    return merged


def _dependency_enabled(chart: Chart, values: Mapping[str, object]) -> bool:
    enabled = True
    tags = values.get("tags")
    if chart.dependency_tags and isinstance(tags, Mapping):
        tag_values = cast(Mapping[object, object], tags)
        selected: list[object | None] = [
            tag_values.get(tag) for tag in chart.dependency_tags
        ]
        has_true = any(value is True for value in selected)
        has_false = any(value is False for value in selected)
        enabled = has_true or not has_false
    for condition in chart.dependency_condition.split(","):
        found, value = _path_value(values, condition.strip())
        if found and isinstance(value, bool):
            return value
    return enabled


def _path_value(values: Mapping[str, object], path: str) -> tuple[bool, object | None]:
    if not path:
        return False, None
    current: object = values
    for key in path.split("."):
        if not isinstance(current, Mapping) or key not in current:
            return False, None
        current = cast(Mapping[object, object], current)[key]
    return True, current
