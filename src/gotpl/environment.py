"""Immutable construction environment for reusable templates."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from typing import Self, cast

from gotpl.exts import ContextFunction, Extension
from gotpl.html import HTMLTemplate
from gotpl.pythonic.registry import (
    PythonExtensionCategory,
    PythonExtensionProfile,
    PythonExtensions,
    resolve_python_extensions,  # pyright: ignore[reportPrivateUsage]
)
from gotpl.runtime.engine import TemplateEngine
from gotpl.runtime.gofmt import FormatMode
from gotpl.runtime.policy import ExecutionBudget, SandboxPolicy
from gotpl.runtime.values import MissingKeyMode
from gotpl.template import (
    Template,
    _validated_functions,  # pyright: ignore[reportPrivateUsage]
)


@dataclass(frozen=True, slots=True, init=False)
class Environment:
    """Reusable immutable template-construction configuration.

    An environment does not discover files or retain a mutable template cache.
    Callers provide complete source strings or named source mappings explicitly.
    """

    functions: Mapping[str, Callable[..., object]]
    extensions: tuple[Extension, ...]
    delimiters: tuple[str, str]
    missing_key: MissingKeyMode
    format_mode: FormatMode
    sandbox: SandboxPolicy | None
    budget: ExecutionBudget | None
    python_extensions: PythonExtensions
    _base_functions: Mapping[str, Callable[..., object]]

    def __init__(
        self,
        *,
        functions: Mapping[str, Callable[..., object]] | None = None,
        extensions: Iterable[Extension] = (),
        delimiters: tuple[str, str] = ("{{", "}}"),
        missing_key: MissingKeyMode = "default",
        format_mode: FormatMode = "go",
        sandbox: SandboxPolicy | None = None,
        budget: ExecutionBudget | None = None,
        python_extensions: PythonExtensions
        | PythonExtensionProfile
        | tuple[PythonExtensionCategory, ...]
        | None = None,
    ) -> None:
        base_functions = _validated_functions(functions)
        selected_extensions = tuple(extensions)
        selected_python_extensions = resolve_python_extensions(python_extensions)
        combined_functions = dict(base_functions)
        for extension in selected_extensions:
            collisions = sorted(set(combined_functions) & set(extension.functions))
            if collisions:
                raise ValueError(
                    "runtime extension function collision: " + ", ".join(collisions)
                )
            combined_functions.update(extension.functions)
        python_functions = selected_python_extensions.function_map()
        python_collisions = sorted(set(combined_functions) & set(python_functions))
        if python_collisions:
            raise ValueError(
                "extension function collision: " + ", ".join(python_collisions)
            )
        selected_functions = (
            base_functions
            if not selected_extensions
            else _validated_functions(combined_functions)
        )
        if not all(delimiters):
            raise ValueError("template delimiters must not be empty")
        if missing_key not in {"default", "zero", "error"}:
            raise ValueError(f"invalid missing_key mode {missing_key!r}")
        if format_mode not in {"go", "python"}:
            raise ValueError(f"invalid format_mode {format_mode!r}")
        if sandbox is not None:
            sandbox.validate_functions({**selected_functions, **python_functions})
            sandbox.validate_context_capabilities(
                capability
                for function in selected_functions.values()
                if isinstance(function, ContextFunction)
                for capability in function.capabilities
            )
        object.__setattr__(self, "functions", selected_functions)
        object.__setattr__(self, "extensions", selected_extensions)
        object.__setattr__(self, "_base_functions", base_functions)
        object.__setattr__(self, "delimiters", delimiters)
        object.__setattr__(self, "missing_key", missing_key)
        object.__setattr__(self, "format_mode", format_mode)
        object.__setattr__(self, "sandbox", sandbox)
        object.__setattr__(self, "budget", budget)
        object.__setattr__(self, "python_extensions", selected_python_extensions)

    @classmethod
    def pythonic(
        cls,
        *categories: PythonExtensionCategory | PythonExtensionProfile,
        functions: Mapping[str, Callable[..., object]] | None = None,
        extensions: Iterable[Extension] = (),
        delimiters: tuple[str, str] = ("{{", "}}"),
        missing_key: MissingKeyMode = "default",
        sandbox: SandboxPolicy | None = None,
        budget: ExecutionBudget | None = None,
    ) -> Self:
        """Build an environment with Go-template syntax and Python semantics.

        No category selects the ``common`` Python helpers. Pass ``"all"`` to
        include Python regular expressions, or name individual categories such
        as ``"hashing"`` and ``"compression"``.
        """

        if not categories:
            selection: PythonExtensionProfile | tuple[PythonExtensionCategory, ...] = (
                "common"
            )
        elif len(categories) == 1 and categories[0] in {"common", "all"}:
            selection = cast(PythonExtensionProfile, categories[0])
        elif "common" in categories or "all" in categories:
            raise ValueError(
                'Python extension profiles "common" and "all" cannot be '
                "combined with categories"
            )
        else:
            selection = cast(tuple[PythonExtensionCategory, ...], categories)
        return cls(
            functions=functions,
            extensions=extensions,
            delimiters=delimiters,
            missing_key=missing_key,
            format_mode="python",
            sandbox=sandbox,
            budget=budget,
            python_extensions=selection,
        )

    def from_string(self, source: str, *, name: str = "template") -> Template:
        """Compile one reusable text template from a string."""

        return Template(
            source,
            name=name,
            delimiters=self.delimiters,
            functions=self.functions,
            missing_key=self.missing_key,
            format_mode=self.format_mode,
            sandbox=self.sandbox,
            budget=self.budget,
            extensions=self.python_extensions,
        )

    def from_sources(self, sources: Mapping[str, str]) -> TemplateEngine:
        """Compile a complete named text association."""

        return TemplateEngine.from_sources(
            sources,
            delimiters=self.delimiters,
            functions=self.functions,
            missing_key=self.missing_key,
            format_mode=self.format_mode,
            sandbox=self.sandbox,
            budget=self.budget,
            extensions=self.python_extensions,
        )

    def from_html_string(
        self,
        source: str,
        *,
        name: str = "template",
    ) -> HTMLTemplate:
        """Compile one reusable contextually escaped HTML template."""

        self._validate_html_extensions()
        return HTMLTemplate(
            source,
            name=name,
            delimiters=self.delimiters,
            functions=self.functions,
            missing_key=self.missing_key,
            format_mode=self.format_mode,
            sandbox=self.sandbox,
            budget=self.budget,
            extensions=self.python_extensions,
        )

    def from_html_sources(self, sources: Mapping[str, str]) -> HTMLTemplate:
        """Compile and analyze a complete named HTML association."""

        self._validate_html_extensions()
        return HTMLTemplate.from_sources(
            sources,
            delimiters=self.delimiters,
            functions=self.functions,
            missing_key=self.missing_key,
            format_mode=self.format_mode,
            sandbox=self.sandbox,
            budget=self.budget,
            extensions=self.python_extensions,
        )

    def with_functions(
        self,
        functions: Mapping[str, Callable[..., object]],
        *,
        replace: bool = False,
    ) -> Self:
        """Return an environment with explicitly composed functions.

        Existing names are rejected unless ``replace=True`` so accidental
        compatibility-profile collisions are visible at construction time.
        """

        extension_names = {
            name for extension in self.extensions for name in extension.functions
        }
        extension_collisions = sorted(extension_names & set(functions))
        if extension_collisions:
            raise ValueError(
                "runtime extension functions cannot be replaced: "
                + ", ".join(extension_collisions)
            )
        collisions = sorted(set(self._base_functions) & set(functions))
        if collisions and not replace:
            raise ValueError(
                "template functions already registered: " + ", ".join(collisions)
            )
        return type(self)(
            functions={**self._base_functions, **functions},
            extensions=self.extensions,
            delimiters=self.delimiters,
            missing_key=self.missing_key,
            format_mode=self.format_mode,
            sandbox=self.sandbox,
            budget=self.budget,
            python_extensions=self.python_extensions,
        )

    def with_extensions(self, *extensions: Extension) -> Self:
        """Return an environment with additional runtime extensions."""

        return type(self)(
            functions=self._base_functions,
            extensions=(*self.extensions, *extensions),
            delimiters=self.delimiters,
            missing_key=self.missing_key,
            format_mode=self.format_mode,
            sandbox=self.sandbox,
            budget=self.budget,
            python_extensions=self.python_extensions,
        )

    def _validate_html_extensions(self) -> None:
        denied = [
            type(extension).__name__
            for extension in self.extensions
            if "html" not in extension.template_kinds
        ]
        if denied:
            raise ValueError(
                "runtime extensions do not support HTML templates: " + ", ".join(denied)
            )


__all__ = ["Environment"]
