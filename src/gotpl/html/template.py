"""Public contextual HTML template API."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import replace
from functools import partial
from types import MappingProxyType
from typing import Self, TextIO, cast

from gotpl.compile import Program
from gotpl.errors import TemplateExecutionError
from gotpl.pythonic import PythonExtensions
from gotpl.runtime import (
    INVALID,
    UNTYPED_NIL,
    AsyncTextWriter,
    ExecutionBudget,
    FormatMode,
    MissingKeyMode,
    SandboxPolicy,
    render_program,
    render_program_async,
    render_program_async_to,
    render_program_to,
)
from gotpl.runtime.callables import PreparedFunctionRegistry
from gotpl.runtime.gofmt import sprintf
from gotpl.runtime.sync_vm import (
    _execution_function_registry,  # pyright: ignore[reportPrivateUsage]
)
from gotpl.template import Template

from .analyzer import analyze_program_with_text_roots
from .escapers import (
    attr_escaper,
    comment_escaper,
    css_escaper,
    css_value_filter,
    html_escaper,
    html_name_filter,
    js_regexp_escaper,
    js_string_escaper,
    js_template_escaper,
    js_value_escaper,
    nospace_escaper,
    rcdata_escaper,
    srcset_escaper,
    url_escaper,
    url_filter,
    url_normalizer,
)


class HTMLTemplate:
    """A reusable template with Go-compatible contextual HTML escaping."""

    functions: PreparedFunctionRegistry

    __slots__ = (
        "_namespace",
        "_program",
        "_runtime_functions",
        "_text",
        "_text_roots",
        "functions",
    )

    def __init__(
        self,
        source: str,
        *,
        name: str = "template",
        delimiters: tuple[str, str] = ("{{", "}}"),
        functions: Mapping[str, Callable[..., object]] | None = None,
        missing_key: MissingKeyMode = "default",
        format_mode: FormatMode = "go",
        sandbox: SandboxPolicy | None = None,
        budget: ExecutionBudget | None = None,
        extensions: PythonExtensions | None = None,
    ) -> None:
        self._initialize(
            Template(
                source,
                name=name,
                delimiters=delimiters,
                functions=functions,
                missing_key=missing_key,
                format_mode=format_mode,
                sandbox=sandbox,
                budget=budget,
                extensions=extensions,
            )
        )

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
        """Analyze multiple named sources as one immutable HTML association."""

        return cls._from_text(
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

    @classmethod
    def _from_text(cls, text: Template) -> Self:
        template = cls.__new__(cls)
        template._initialize(text)
        return template

    def _initialize(self, text: Template) -> None:
        self._text = text
        root = text._program  # pyright: ignore[reportPrivateUsage]
        namespace = text._namespace  # pyright: ignore[reportPrivateUsage]
        association = replace(
            root,
            definitions=tuple(
                program for name, program in namespace.items() if name != root.name
            ),
        )
        self._program, self._text_roots = analyze_program_with_text_roots(association)
        self._namespace = MappingProxyType(
            {
                **{item.name: item for item in self._program.definitions},
                self._program.name: self._program,
            }
        )
        internal = PreparedFunctionRegistry(_internal_escapers(text.format_mode))
        registry = {**self._text.functions, **internal}
        text_functions = cast(PreparedFunctionRegistry, self._text.functions)
        call_specs = {**text_functions.call_specs, **internal.call_specs}
        self.functions = PreparedFunctionRegistry(registry, call_specs)
        self._runtime_functions = _execution_function_registry(
            text.format_mode,
            self.functions,
            sandbox=text.sandbox,
        )

    def with_source(self, source: str, *, name: str = "template") -> Self:
        """Return a reanalyzed association with one added or replaced source."""

        return type(self)._from_text(self._text.with_source(source, name=name))

    def with_functions(
        self,
        functions: Mapping[str, Callable[..., object]],
    ) -> Self:
        """Return a reanalyzed template with an extended function registry."""

        return type(self)._from_text(self._text.with_functions(functions))

    def render_source(
        self,
        source: str,
        data: object = None,
        *,
        name: str = "template",
    ) -> str:
        """Analyze and render a new source against inherited definitions."""

        return self.with_source(source, name=name).render(data)

    async def render_source_async(
        self,
        source: str,
        data: object = None,
        *,
        name: str = "template",
    ) -> str:
        """Analyze and asynchronously render a source with inherited definitions."""

        return await self.with_source(source, name=name).render_async(data)

    def render(self, data: object = None) -> str:
        """Render the HTML template synchronously."""

        return render_program(
            self._program,
            data,
            functions=self._runtime_functions,
            missing_key=self._text.missing_key,
            format_mode=self._text.format_mode,
            _namespace=self._namespace,
            budget=self._text.budget,
            sandbox=self._text.sandbox,
        )

    def render_to(self, writer: TextIO, data: object = None) -> None:
        """Render synchronously to a text writer."""

        render_program_to(
            self._program,
            writer,
            data,
            functions=self._runtime_functions,
            missing_key=self._text.missing_key,
            format_mode=self._text.format_mode,
            _namespace=self._namespace,
            budget=self._text.budget,
            sandbox=self._text.sandbox,
        )

    async def render_async(self, data: object = None) -> str:
        """Render the HTML template while awaiting function results."""

        return await render_program_async(
            self._program,
            data,
            functions=self._runtime_functions,
            missing_key=self._text.missing_key,
            format_mode=self._text.format_mode,
            _namespace=self._namespace,
            budget=self._text.budget,
            sandbox=self._text.sandbox,
        )

    async def render_async_to(
        self, writer: AsyncTextWriter, data: object = None
    ) -> None:
        """Render asynchronously to a synchronous or asynchronous writer."""

        await render_program_async_to(
            self._program,
            writer,
            data,
            functions=self._runtime_functions,
            missing_key=self._text.missing_key,
            format_mode=self._text.format_mode,
            _namespace=self._namespace,
            budget=self._text.budget,
            sandbox=self._text.sandbox,
        )

    def render_template(self, name: str, data: object = None) -> str:
        """Render one associated named HTML template synchronously."""

        program = self._associated_program(name)
        return render_program(
            program,
            data,
            functions=self._runtime_functions,
            missing_key=self._text.missing_key,
            format_mode=self._text.format_mode,
            _namespace=self._namespace,
            budget=self._text.budget,
            sandbox=self._text.sandbox,
        )

    def render_template_to(
        self,
        name: str,
        writer: TextIO,
        data: object = None,
    ) -> None:
        """Render one associated named HTML template to a text writer."""

        program = self._associated_program(name)
        render_program_to(
            program,
            writer,
            data,
            functions=self._runtime_functions,
            missing_key=self._text.missing_key,
            format_mode=self._text.format_mode,
            _namespace=self._namespace,
            budget=self._text.budget,
            sandbox=self._text.sandbox,
        )

    async def render_template_async(
        self,
        name: str,
        data: object = None,
    ) -> str:
        """Render one associated named HTML template asynchronously."""

        program = self._associated_program(name)
        return await render_program_async(
            program,
            data,
            functions=self._runtime_functions,
            missing_key=self._text.missing_key,
            format_mode=self._text.format_mode,
            _namespace=self._namespace,
            budget=self._text.budget,
            sandbox=self._text.sandbox,
        )

    async def render_template_async_to(
        self,
        name: str,
        writer: AsyncTextWriter,
        data: object = None,
    ) -> None:
        """Render one associated named HTML template to an asynchronous writer."""

        program = self._associated_program(name)
        await render_program_async_to(
            program,
            writer,
            data,
            functions=self._runtime_functions,
            missing_key=self._text.missing_key,
            format_mode=self._text.format_mode,
            _namespace=self._namespace,
            budget=self._text.budget,
            sandbox=self._text.sandbox,
        )

    def _associated_program(self, name: str) -> Program:
        program = self._namespace.get(name)
        if program is None:
            error = TemplateExecutionError(f"template {name!r} is not defined")
            error.attach_location(
                self._text.source,
                0,
                source_name=self._text.name,
                template_name=name,
            )
            raise error
        if name not in self._text_roots:
            error = TemplateExecutionError(
                f"template {name!r} ends in a non-text context"
            )
            error.attach_location(
                self._text.source,
                len(self._text.source),
                source_name=self._text.name,
                template_name=name,
            )
            raise error
        return program


def _internal_escapers(
    format_mode: FormatMode,
) -> dict[str, Callable[..., object]]:
    return {
        "_html_template_eval_args": partial(_eval_args, format_mode=format_mode),
        "_html_template_htmlescaper": partial(html_escaper, format_mode=format_mode),
        "_html_template_htmlnamefilter": partial(
            html_name_filter, format_mode=format_mode
        ),
        "_html_template_rcdataescaper": partial(
            rcdata_escaper, format_mode=format_mode
        ),
        "_html_template_attrescaper": partial(attr_escaper, format_mode=format_mode),
        "_html_template_nospaceescaper": partial(
            nospace_escaper, format_mode=format_mode
        ),
        "_html_template_commentescaper": comment_escaper,
        "_html_template_cssvaluefilter": partial(
            css_value_filter, format_mode=format_mode
        ),
        "_html_template_cssescaper": partial(css_escaper, format_mode=format_mode),
        "_html_template_srcsetescaper": partial(
            srcset_escaper, format_mode=format_mode
        ),
        "_html_template_jsvalescaper": js_value_escaper,
        "_html_template_jsstrescaper": partial(
            js_string_escaper, format_mode=format_mode
        ),
        "_html_template_jstmpllitescaper": partial(
            js_template_escaper, format_mode=format_mode
        ),
        "_html_template_jsregexpescaper": partial(
            js_regexp_escaper, format_mode=format_mode
        ),
        "_html_template_urlfilter": partial(url_filter, format_mode=format_mode),
        "_html_template_urlnormalizer": partial(
            url_normalizer, format_mode=format_mode
        ),
        "_html_template_urlescaper": partial(url_escaper, format_mode=format_mode),
    }


def _eval_args(*values: object, format_mode: FormatMode) -> str:
    output: list[str] = []
    previous: object = INVALID
    for value in values:
        if (
            previous is not INVALID
            and not isinstance(previous, str)
            and not isinstance(value, str)
        ):
            output.append(" ")
        output.append(
            "<nil>"
            if value is UNTYPED_NIL
            else "<no value>"
            if value is INVALID
            else sprintf("%v", value, format_mode=format_mode)
        )
        previous = value
    return "".join(output)


def render_html(
    source: str,
    data: object = None,
    *,
    name: str = "template",
    delimiters: tuple[str, str] = ("{{", "}}"),
    functions: Mapping[str, Callable[..., object]] | None = None,
    missing_key: MissingKeyMode = "default",
    format_mode: FormatMode = "go",
    sandbox: SandboxPolicy | None = None,
    budget: ExecutionBudget | None = None,
    extensions: PythonExtensions | None = None,
) -> str:
    """Parse, analyze, compile, and synchronously render an HTML template."""

    return HTMLTemplate(
        source,
        name=name,
        delimiters=delimiters,
        functions=functions,
        missing_key=missing_key,
        format_mode=format_mode,
        sandbox=sandbox,
        budget=budget,
        extensions=extensions,
    ).render(data)


def render_html_to(
    source: str,
    writer: TextIO,
    data: object = None,
    *,
    name: str = "template",
    delimiters: tuple[str, str] = ("{{", "}}"),
    functions: Mapping[str, Callable[..., object]] | None = None,
    missing_key: MissingKeyMode = "default",
    format_mode: FormatMode = "go",
    sandbox: SandboxPolicy | None = None,
    budget: ExecutionBudget | None = None,
    extensions: PythonExtensions | None = None,
) -> None:
    """Render an HTML template to a text writer."""

    HTMLTemplate(
        source,
        name=name,
        delimiters=delimiters,
        functions=functions,
        missing_key=missing_key,
        format_mode=format_mode,
        sandbox=sandbox,
        budget=budget,
        extensions=extensions,
    ).render_to(writer, data)


async def render_html_async(
    source: str,
    data: object = None,
    *,
    name: str = "template",
    delimiters: tuple[str, str] = ("{{", "}}"),
    functions: Mapping[str, Callable[..., object]] | None = None,
    missing_key: MissingKeyMode = "default",
    format_mode: FormatMode = "go",
    sandbox: SandboxPolicy | None = None,
    budget: ExecutionBudget | None = None,
    extensions: PythonExtensions | None = None,
) -> str:
    """Parse, analyze, compile, and asynchronously render an HTML template."""

    return await HTMLTemplate(
        source,
        name=name,
        delimiters=delimiters,
        functions=functions,
        missing_key=missing_key,
        format_mode=format_mode,
        sandbox=sandbox,
        budget=budget,
        extensions=extensions,
    ).render_async(data)


async def render_html_async_to(
    source: str,
    writer: AsyncTextWriter,
    data: object = None,
    *,
    name: str = "template",
    delimiters: tuple[str, str] = ("{{", "}}"),
    functions: Mapping[str, Callable[..., object]] | None = None,
    missing_key: MissingKeyMode = "default",
    format_mode: FormatMode = "go",
    sandbox: SandboxPolicy | None = None,
    budget: ExecutionBudget | None = None,
    extensions: PythonExtensions | None = None,
) -> None:
    """Render an HTML template to a synchronous or asynchronous writer."""

    await HTMLTemplate(
        source,
        name=name,
        delimiters=delimiters,
        functions=functions,
        missing_key=missing_key,
        format_mode=format_mode,
        sandbox=sandbox,
        budget=budget,
        extensions=extensions,
    ).render_async_to(writer, data)
