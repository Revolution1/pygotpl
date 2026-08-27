"""Immutable multi-source template execution."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Self

from gotpl.pythonic import PythonExtensions
from gotpl.runtime.gofmt import FormatMode
from gotpl.runtime.policy import ExecutionBudget, SandboxPolicy
from gotpl.runtime.values import MissingKeyMode
from gotpl.template import Template


@dataclass(frozen=True, slots=True)
class TemplateEngine:
    """Render associated template sources with independent per-source data."""

    template: Template

    @classmethod
    def from_sources(
        cls,
        sources: Mapping[str, str],
        *,
        delimiters: tuple[str, str] = ("{{", "}}"),
        functions: Mapping[str, Callable[..., object]] | None = None,
        missing_key: MissingKeyMode = "default",
        format_mode: FormatMode = "go",
        sandbox: SandboxPolicy | None = None,
        budget: ExecutionBudget | None = None,
        extensions: PythonExtensions | None = None,
    ) -> Self:
        """Compile named sources into one immutable execution engine."""

        return cls(
            Template.from_sources(
                sources,
                delimiters=delimiters,
                functions=functions,
                missing_key=missing_key,
                format_mode=format_mode,
                sandbox=sandbox,
                budget=budget,
                extensions=extensions,
            )
        )

    def with_source(self, source: str, *, name: str = "template") -> Self:
        """Return an engine with one added or replaced dynamic source."""

        return type(self)(self.template.with_source(source, name=name))

    def render(self, contexts: Mapping[str, object]) -> dict[str, str]:
        """Render each named source using its corresponding context."""

        return {
            name: self.template.render_template(name, context)
            for name, context in contexts.items()
        }

    async def render_async(self, contexts: Mapping[str, object]) -> dict[str, str]:
        """Render named sources and await functions in source order."""

        output: dict[str, str] = {}
        for name, context in contexts.items():
            output[name] = await self.template.render_template_async(name, context)
        return output


__all__ = ["TemplateEngine"]
