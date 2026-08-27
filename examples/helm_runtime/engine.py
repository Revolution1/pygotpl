"""Pure Python Helm chart-template engine used by the example CLI."""

from __future__ import annotations

import posixpath
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import cast

from gotpl.errors import TemplateExecutionError
from gotpl.funcs.helm import function_map
from gotpl.runtime import INVALID, FunctionResult
from gotpl.runtime.engine import TemplateEngine

from .models import Capabilities, Chart, Release

_RECURSION_LIMIT = 1000


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
        template_engine = self._build_template_async(sources)
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

    def _build_template(self, sources: Mapping[str, str]) -> TemplateEngine:
        holder: dict[str, TemplateEngine] = {}
        included: dict[str, int] = {}
        dynamic_index = 0

        def include(name: str, data: object) -> object:
            count = included.get(name, 0)
            if count > _RECURSION_LIMIT:
                return FunctionResult.failure(
                    ValueError(
                        "rendering template has a nested reference name: "
                        f"{name}: unable to execute template"
                    ),
                    "",
                )
            included[name] = count + 1
            try:
                return holder["engine"].template.render_template(name, data)
            except TemplateExecutionError as error:
                return FunctionResult.failure(error, "")
            finally:
                included[name] -= 1

        def tpl(source: str, data: object) -> object:
            nonlocal dynamic_index
            dynamic_index += 1
            name = f"__helm_tpl_{dynamic_index}__"
            parent = holder["engine"]
            dynamic = parent.with_source(source, name=name)
            holder["engine"] = dynamic
            try:
                return dynamic.template.render(data).replace("<no value>", "")
            except Exception as error:
                return FunctionResult.failure(error, "")
            finally:
                holder["engine"] = parent

        def required(message: str, value: object) -> object:
            missing = value is None or value is INVALID or value == ""
            if missing and not self.lint_mode:
                return FunctionResult.failure(ValueError(message), value="")
            return "" if missing else value

        def fail(message: str) -> object:
            if self.lint_mode:
                return ""
            return FunctionResult.failure(ValueError(message), value="")

        functions = function_map(
            include=include,
            tpl=tpl,
            required=required,
            fail=fail,
            lookup=self.lookup,
            enable_dns=self.enable_dns,
            custom=self.custom_functions,
        )
        engine = TemplateEngine.from_sources(
            sources,
            functions=functions,
            missing_key="error" if self.strict else "zero",
        )
        holder["engine"] = engine
        return engine

    def _build_template_async(self, sources: Mapping[str, str]) -> TemplateEngine:
        holder: dict[str, TemplateEngine] = {}
        included: dict[str, int] = {}
        dynamic_index = 0

        async def include(name: str, data: object) -> object:
            count = included.get(name, 0)
            if count > _RECURSION_LIMIT:
                return FunctionResult.failure(
                    ValueError(
                        "rendering template has a nested reference name: "
                        f"{name}: unable to execute template"
                    ),
                    "",
                )
            included[name] = count + 1
            try:
                return await holder["engine"].template.render_template_async(name, data)
            except TemplateExecutionError as error:
                return FunctionResult.failure(error, "")
            finally:
                included[name] -= 1

        async def tpl(source: str, data: object) -> object:
            nonlocal dynamic_index
            dynamic_index += 1
            name = f"__helm_tpl_{dynamic_index}__"
            parent = holder["engine"]
            dynamic = parent.with_source(source, name=name)
            holder["engine"] = dynamic
            try:
                rendered = await dynamic.template.render_async(data)
                return rendered.replace("<no value>", "")
            except Exception as error:
                return FunctionResult.failure(error, "")
            finally:
                holder["engine"] = parent

        def required(message: str, value: object) -> object:
            missing = value is None or value is INVALID or value == ""
            if missing and not self.lint_mode:
                return FunctionResult.failure(ValueError(message), value="")
            return "" if missing else value

        def fail(message: str) -> object:
            if self.lint_mode:
                return ""
            return FunctionResult.failure(ValueError(message), value="")

        functions = function_map(
            include=include,
            tpl=tpl,
            required=required,
            fail=fail,
            lookup=self.lookup,
            enable_dns=self.enable_dns,
            custom=self.custom_functions,
        )
        engine = TemplateEngine.from_sources(
            sources,
            functions=functions,
            missing_key="error" if self.strict else "zero",
        )
        holder["engine"] = engine
        return engine

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
