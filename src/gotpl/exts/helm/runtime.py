"""Reusable Helm extension built on gotpl's generic render context."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Literal, Self

from gotpl.environment import Environment
from gotpl.errors import TemplateExecutionError
from gotpl.funcs.helm.functions import function_map
from gotpl.runtime import INVALID, FunctionResult
from gotpl.runtime.context import (
    AsyncRenderContext,
    ContextFunction,
    RenderContext,
    RenderSession,
)
from gotpl.runtime.engine import TemplateEngine

_RECURSION_LIMIT = 1000


def _empty_included() -> dict[str, int]:
    return {}


@dataclass(slots=True)
class _HelmRenderState:
    included: dict[str, int] = field(default_factory=_empty_included)


@dataclass(frozen=True, slots=True, init=False)
class HelmExtension:
    """Opt-in Helm function profile for a generic :class:`Environment`."""

    lint_mode: bool
    functions: Mapping[str, Callable[..., object]]
    template_kinds: frozenset[Literal["text", "html"]]
    _state_key: object

    def __init__(
        self,
        *,
        lint_mode: bool = False,
        enable_dns: bool = False,
        custom_functions: Mapping[str, Callable[..., object]] | None = None,
        lookup: Callable[[str, str, str, str], object] | None = None,
    ) -> None:
        object.__setattr__(self, "lint_mode", lint_mode)
        object.__setattr__(self, "template_kinds", frozenset({"text"}))
        object.__setattr__(self, "_state_key", object())
        functions = function_map(
            include=ContextFunction(
                sync=self._include,
                async_=self._include_async,
                capabilities=frozenset({"render-associated"}),
            ),
            tpl=ContextFunction(
                sync=self._tpl,
                async_=self._tpl_async,
                capabilities=frozenset({"render-dynamic-source"}),
            ),
            required=self._required,
            fail=self._fail,
            lookup=lookup,
            enable_dns=enable_dns,
            custom=custom_functions,
        )
        object.__setattr__(self, "functions", MappingProxyType(functions))

    def _state(self, context: RenderContext | AsyncRenderContext) -> _HelmRenderState:
        return context.state(self._state_key, _HelmRenderState)

    def _include(self, context: RenderContext, name: str, data: object) -> object:
        state = self._state(context)
        count = state.included.get(name, 0)
        if count > _RECURSION_LIMIT:
            return _recursion_failure(name)
        state.included[name] = count + 1
        try:
            return context.render_template(name, data)
        except TemplateExecutionError as error:
            return FunctionResult.failure(error, "")
        finally:
            state.included[name] -= 1

    async def _include_async(
        self,
        context: AsyncRenderContext,
        name: str,
        data: object,
    ) -> object:
        state = self._state(context)
        count = state.included.get(name, 0)
        if count > _RECURSION_LIMIT:
            return _recursion_failure(name)
        state.included[name] = count + 1
        try:
            return await context.render_template(name, data)
        except TemplateExecutionError as error:
            return FunctionResult.failure(error, "")
        finally:
            state.included[name] -= 1

    def _tpl(self, context: RenderContext, source: str, data: object) -> object:
        try:
            return context.render_source(source, data, name="__helm_tpl__").replace(
                "<no value>", ""
            )
        except Exception as error:
            return FunctionResult.failure(error, "")

    async def _tpl_async(
        self,
        context: AsyncRenderContext,
        source: str,
        data: object,
    ) -> object:
        try:
            rendered = await context.render_source(source, data, name="__helm_tpl__")
            return rendered.replace("<no value>", "")
        except Exception as error:
            return FunctionResult.failure(error, "")

    def _required(self, message: str, value: object) -> object:
        missing = value is None or value is INVALID or value == ""
        if missing and not self.lint_mode:
            return FunctionResult.failure(ValueError(message), value="")
        return "" if missing else value

    def _fail(self, message: str) -> object:
        if self.lint_mode:
            return ""
        return FunctionResult.failure(ValueError(message), value="")


class HelmTemplateEngine:
    """Source-compatible facade over :class:`Environment` and `HelmExtension`."""

    __slots__ = ("_engine",)

    def __init__(
        self,
        sources: Mapping[str, str],
        *,
        strict: bool = False,
        lint_mode: bool = False,
        enable_dns: bool = False,
        custom_functions: Mapping[str, Callable[..., object]] | None = None,
        lookup: Callable[[str, str, str, str], object] | None = None,
    ) -> None:
        extension = HelmExtension(
            lint_mode=lint_mode,
            enable_dns=enable_dns,
            custom_functions=custom_functions,
            lookup=lookup,
        )
        self._engine: TemplateEngine = Environment(
            extensions=(extension,),
            missing_key="error" if strict else "zero",
        ).from_sources(sources)

    @classmethod
    def from_sources(
        cls,
        sources: Mapping[str, str],
        *,
        strict: bool = False,
        lint_mode: bool = False,
        enable_dns: bool = False,
        custom_functions: Mapping[str, Callable[..., object]] | None = None,
        lookup: Callable[[str, str, str, str], object] | None = None,
    ) -> Self:
        """Compile associated sources with the reusable Helm extension."""

        return cls(
            sources,
            strict=strict,
            lint_mode=lint_mode,
            enable_dns=enable_dns,
            custom_functions=custom_functions,
            lookup=lookup,
        )

    def render(self, contexts: Mapping[str, object]) -> dict[str, str]:
        """Render selected sources with independent contexts."""

        template = self._engine.template
        session = RenderSession.create(template, template.budget)
        return {
            name: template._render_template_in_session(  # pyright: ignore[reportPrivateUsage]
                name, data, session
            ).replace("<no value>", "")
            for name, data in contexts.items()
        }

    async def render_async(self, contexts: Mapping[str, object]) -> dict[str, str]:
        """Render selected sources asynchronously."""

        template = self._engine.template
        session = RenderSession.create(template, template.budget)
        rendered: dict[str, str] = {}
        for name, data in contexts.items():
            rendered[name] = await template._render_template_async_in_session(  # pyright: ignore[reportPrivateUsage]
                name, data, session
            )
        return {
            name: value.replace("<no value>", "") for name, value in rendered.items()
        }

    def render_template(self, name: str, data: object = None) -> str:
        """Render one named source with Helm runtime bindings."""

        return self.render({name: data})[name]

    async def render_template_async(self, name: str, data: object = None) -> str:
        """Render one named source asynchronously with Helm bindings."""

        return (await self.render_async({name: data}))[name]


def _recursion_failure(name: str) -> FunctionResult:
    return FunctionResult.failure(
        ValueError(
            "rendering template has a nested reference name: "
            f"{name}: unable to execute template"
        ),
        "",
    )


__all__ = ["HelmExtension", "HelmTemplateEngine"]
