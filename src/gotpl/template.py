"""Public text-template API."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from types import MappingProxyType
from typing import Self, TextIO
from unicodedata import category

from gotpl.compile import Program, compile_template
from gotpl.errors import SandboxViolationError, TemplateExecutionError
from gotpl.parse import parse_template
from gotpl.pythonic import PythonExtensions
from gotpl.runtime import (
    AsyncTextWriter,
    ExecutionBudget,
    FormatMode,
    MissingKeyMode,
    SandboxPolicy,
    render_linked_program,
    render_linked_program_to,
    render_program,
    render_program_async,
    render_program_async_to,
    render_program_to,
)
from gotpl.runtime.callables import (
    CallSpec,
    PreparedFunctionRegistry,
    prepare_template_function,
)
from gotpl.runtime.context import ContextFunction, RenderSession
from gotpl.runtime.linked import LinkedProgram, link_program
from gotpl.runtime.sync_vm import (
    _execution_function_registry,  # pyright: ignore[reportPrivateUsage]
)

_MISSING_KEY_MODES = frozenset({"default", "zero", "error"})
_FORMAT_MODES = frozenset({"go", "python"})


@dataclass(frozen=True, slots=True)
class Template:
    """A parsed and compiled reusable text template."""

    source: str
    name: str
    delimiters: tuple[str, str]
    functions: Mapping[str, Callable[..., object]]
    missing_key: MissingKeyMode
    format_mode: FormatMode
    sandbox: SandboxPolicy | None
    budget: ExecutionBudget | None
    extensions: PythonExtensions
    _program: Program
    _namespace: Mapping[str, Program]
    _runtime_functions: PreparedFunctionRegistry
    _linked_program: LinkedProgram
    _use_linked: bool

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
        if missing_key not in _MISSING_KEY_MODES:
            raise ValueError(f"invalid missing_key mode {missing_key!r}")
        if not all(delimiters):
            raise ValueError("template delimiters must not be empty")
        if format_mode not in _FORMAT_MODES:
            raise ValueError(f"invalid format_mode {format_mode!r}")
        if sandbox is not None and len(source) > sandbox.max_template_chars:
            raise SandboxViolationError(
                "template source exceeds sandbox character limit: "
                f"limit {sandbox.max_template_chars}, requested {len(source)}"
            )
        selected_extensions = extensions or PythonExtensions()
        extension_functions = selected_extensions.function_map()
        collisions = sorted(set(functions or ()) & set(extension_functions))
        if collisions:
            raise ValueError("extension function collision: " + ", ".join(collisions))
        registry = (
            functions
            if isinstance(functions, PreparedFunctionRegistry)
            and not extension_functions
            else _validated_functions({**(functions or {}), **extension_functions})
        )
        if sandbox is not None:
            sandbox.validate_functions(registry)
            sandbox.validate_context_capabilities(
                capability
                for function in registry.values()
                if isinstance(function, ContextFunction)
                for capability in function.capabilities
            )
        object.__setattr__(self, "source", source)
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "delimiters", delimiters)
        object.__setattr__(self, "functions", registry)
        object.__setattr__(
            self,
            "_runtime_functions",
            _execution_function_registry(format_mode, registry, sandbox=sandbox),
        )
        object.__setattr__(self, "missing_key", missing_key)
        object.__setattr__(self, "format_mode", format_mode)
        object.__setattr__(self, "sandbox", sandbox)
        object.__setattr__(
            self, "budget", budget or (sandbox.default_budget if sandbox else None)
        )
        object.__setattr__(self, "extensions", selected_extensions)
        program = compile_template(
            parse_template(
                source,
                name=name,
                left_delimiter=delimiters[0],
                right_delimiter=delimiters[1],
                functions=registry,
            ),
            source=source,
        )
        namespace = {definition.name: definition for definition in program.definitions}
        namespace[program.name] = program
        object.__setattr__(self, "_program", program)
        object.__setattr__(self, "_namespace", MappingProxyType(namespace))
        object.__setattr__(
            self,
            "_linked_program",
            _link_association(program, namespace, self._runtime_functions),
        )
        object.__setattr__(
            self, "_use_linked", _should_use_linked(self._linked_program)
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
        """Parse multiple named sources into one immutable template namespace."""

        items = tuple(sources.items())
        if not items:
            raise ValueError("Template.from_sources requires at least one source")
        first_name, first_source = items[0]
        template = cls(
            first_source,
            name=first_name,
            delimiters=delimiters,
            functions=functions,
            missing_key=missing_key,
            format_mode=format_mode,
            sandbox=sandbox,
            budget=budget,
            extensions=extensions,
        )
        namespace = dict(template._namespace)
        for source_name, source in items[1:]:
            if sandbox is not None and len(source) > sandbox.max_template_chars:
                raise SandboxViolationError(
                    "template source exceeds sandbox character limit: "
                    f"limit {sandbox.max_template_chars}, requested {len(source)}"
                )
            program = compile_template(
                parse_template(
                    source,
                    name=source_name,
                    left_delimiter=delimiters[0],
                    right_delimiter=delimiters[1],
                    functions=template.functions,
                ),
                source=source,
            )
            namespace[program.name] = program
            for definition in program.definitions:
                current = namespace.get(definition.name)
                if definition.instructions or current is None:
                    namespace[definition.name] = definition
        object.__setattr__(template, "_namespace", MappingProxyType(namespace))
        object.__setattr__(
            template,
            "_linked_program",
            _link_association(
                template._program,
                namespace,
                template._runtime_functions,
            ),
        )
        object.__setattr__(
            template, "_use_linked", _should_use_linked(template._linked_program)
        )
        return template

    def render(self, data: object = None) -> str:
        """Render the template synchronously."""

        session = self._new_render_session()
        if not self._use_linked:
            return render_program(
                self._program,
                data,
                functions=self._runtime_functions,
                missing_key=self.missing_key,
                format_mode=self.format_mode,
                _namespace=self._namespace,
                budget=self.budget,
                sandbox=self.sandbox,
                _session=session,
                _budget_state=None if session is None else session.budget_state,
            )
        return render_linked_program(
            self._linked_program,
            data,
            functions=self._runtime_functions,
            missing_key=self.missing_key,
            format_mode=self.format_mode,
            budget=self.budget,
            sandbox=self.sandbox,
            _session=session,
            _budget_state=None if session is None else session.budget_state,
        )

    def render_to(self, writer: TextIO, data: object = None) -> None:
        """Render the template and write its text to a file-like object."""

        session = self._new_render_session()
        if not self._use_linked:
            render_program_to(
                self._program,
                writer,
                data,
                functions=self._runtime_functions,
                missing_key=self.missing_key,
                format_mode=self.format_mode,
                _namespace=self._namespace,
                budget=self.budget,
                sandbox=self.sandbox,
                _session=session,
                _budget_state=None if session is None else session.budget_state,
            )
            return
        render_linked_program_to(
            self._linked_program,
            writer,
            data,
            functions=self._runtime_functions,
            missing_key=self.missing_key,
            format_mode=self.format_mode,
            budget=self.budget,
            sandbox=self.sandbox,
            _session=session,
            _budget_state=None if session is None else session.budget_state,
        )

    async def render_async(self, data: object = None) -> str:
        """Render the template, awaiting function results when necessary."""

        session = self._new_render_session()
        return await render_program_async(
            self._program,
            data,
            functions=self._runtime_functions,
            missing_key=self.missing_key,
            format_mode=self.format_mode,
            _namespace=self._namespace,
            budget=self.budget,
            sandbox=self.sandbox,
            _session=session,
            _budget_state=None if session is None else session.budget_state,
        )

    async def render_async_to(
        self,
        writer: AsyncTextWriter,
        data: object = None,
    ) -> None:
        """Render asynchronously to a synchronous or asynchronous writer."""

        session = self._new_render_session()
        await render_program_async_to(
            self._program,
            writer,
            data,
            functions=self._runtime_functions,
            missing_key=self.missing_key,
            format_mode=self.format_mode,
            _namespace=self._namespace,
            budget=self.budget,
            sandbox=self.sandbox,
            _session=session,
            _budget_state=None if session is None else session.budget_state,
        )

    def render_template(self, name: str, data: object = None) -> str:
        """Render one associated named template synchronously."""

        program = self._associated_program(name)
        session = self._new_render_session()
        if not self._use_linked:
            return render_program(
                program,
                data,
                functions=self._runtime_functions,
                missing_key=self.missing_key,
                format_mode=self.format_mode,
                _namespace=self._namespace,
                budget=self.budget,
                sandbox=self.sandbox,
                _session=session,
                _budget_state=None if session is None else session.budget_state,
            )
        return render_linked_program(
            self._linked_program,
            data,
            template_name=name,
            functions=self._runtime_functions,
            missing_key=self.missing_key,
            format_mode=self.format_mode,
            budget=self.budget,
            sandbox=self.sandbox,
            _session=session,
            _budget_state=None if session is None else session.budget_state,
        )

    def with_functions(
        self,
        functions: Mapping[str, Callable[..., object]],
    ) -> Self:
        """Return a template with added or replaced registered functions.

        Existing compiled programs and associated templates are reused. Newly
        added names are available to sources compiled later through
        :meth:`with_source` or :meth:`render_source`.
        """

        extension_functions = self.extensions.function_map()
        collisions = sorted(set(functions) & set(extension_functions))
        if collisions:
            raise ValueError("extension function collision: " + ", ".join(collisions))
        registry = _validated_functions({**self.functions, **functions})
        if self.sandbox is not None:
            self.sandbox.validate_functions(registry)
            self.sandbox.validate_context_capabilities(
                capability
                for function in registry.values()
                if isinstance(function, ContextFunction)
                for capability in function.capabilities
            )

        template = object.__new__(type(self))
        object.__setattr__(template, "source", self.source)
        object.__setattr__(template, "name", self.name)
        object.__setattr__(template, "delimiters", self.delimiters)
        object.__setattr__(template, "functions", registry)
        object.__setattr__(template, "missing_key", self.missing_key)
        object.__setattr__(template, "format_mode", self.format_mode)
        object.__setattr__(template, "sandbox", self.sandbox)
        object.__setattr__(template, "budget", self.budget)
        object.__setattr__(template, "extensions", self.extensions)
        object.__setattr__(template, "_program", self._program)
        object.__setattr__(template, "_namespace", self._namespace)
        object.__setattr__(
            template,
            "_runtime_functions",
            _execution_function_registry(
                self.format_mode,
                registry,
                sandbox=self.sandbox,
            ),
        )
        object.__setattr__(
            template,
            "_linked_program",
            _link_association(
                self._program,
                self._namespace,
                template._runtime_functions,
            ),
        )
        object.__setattr__(
            template, "_use_linked", _should_use_linked(template._linked_program)
        )
        return template

    def with_source(self, source: str, *, name: str = "template") -> Self:
        """Return a template whose new source inherits this template namespace."""

        if self.sandbox is not None and len(source) > self.sandbox.max_template_chars:
            raise SandboxViolationError(
                "template source exceeds sandbox character limit: "
                f"limit {self.sandbox.max_template_chars}, requested {len(source)}"
            )
        program = compile_template(
            parse_template(
                source,
                name=name,
                left_delimiter=self.delimiters[0],
                right_delimiter=self.delimiters[1],
                functions=self.functions,
            ),
            source=source,
        )
        namespace = dict(self._namespace)
        namespace[program.name] = program
        for definition in program.definitions:
            current = namespace.get(definition.name)
            if definition.instructions or current is None:
                namespace[definition.name] = definition

        template = object.__new__(type(self))
        object.__setattr__(template, "source", source)
        object.__setattr__(template, "name", name)
        object.__setattr__(template, "delimiters", self.delimiters)
        object.__setattr__(template, "functions", self.functions)
        object.__setattr__(template, "missing_key", self.missing_key)
        object.__setattr__(template, "format_mode", self.format_mode)
        object.__setattr__(template, "sandbox", self.sandbox)
        object.__setattr__(template, "budget", self.budget)
        object.__setattr__(template, "extensions", self.extensions)
        object.__setattr__(template, "_program", program)
        object.__setattr__(template, "_namespace", MappingProxyType(namespace))
        object.__setattr__(template, "_runtime_functions", self._runtime_functions)
        object.__setattr__(
            template,
            "_linked_program",
            _link_association(program, namespace, self._runtime_functions),
        )
        object.__setattr__(
            template, "_use_linked", _should_use_linked(template._linked_program)
        )
        return template

    def render_source(
        self,
        source: str,
        data: object = None,
        *,
        name: str = "template",
    ) -> str:
        """Render a new source with this template's associated definitions."""

        return self.with_source(source, name=name).render(data)

    def render_template_to(
        self,
        name: str,
        writer: TextIO,
        data: object = None,
    ) -> None:
        """Render one associated named template to a text writer."""

        program = self._associated_program(name)
        session = self._new_render_session()
        if not self._use_linked:
            render_program_to(
                program,
                writer,
                data,
                functions=self._runtime_functions,
                missing_key=self.missing_key,
                format_mode=self.format_mode,
                _namespace=self._namespace,
                budget=self.budget,
                sandbox=self.sandbox,
                _session=session,
                _budget_state=None if session is None else session.budget_state,
            )
            return
        render_linked_program_to(
            self._linked_program,
            writer,
            data,
            template_name=name,
            functions=self._runtime_functions,
            missing_key=self.missing_key,
            format_mode=self.format_mode,
            budget=self.budget,
            sandbox=self.sandbox,
            _session=session,
            _budget_state=None if session is None else session.budget_state,
        )

    async def render_template_async(
        self,
        name: str,
        data: object = None,
    ) -> str:
        """Render one associated named template asynchronously."""

        program = self._associated_program(name)
        session = self._new_render_session()
        return await render_program_async(
            program,
            data,
            functions=self._runtime_functions,
            missing_key=self.missing_key,
            format_mode=self.format_mode,
            _namespace=self._namespace,
            budget=self.budget,
            sandbox=self.sandbox,
            _session=session,
            _budget_state=None if session is None else session.budget_state,
        )

    async def render_source_async(
        self,
        source: str,
        data: object = None,
        *,
        name: str = "template",
    ) -> str:
        """Render a new source asynchronously with inherited definitions."""

        return await self.with_source(source, name=name).render_async(data)

    async def render_template_async_to(
        self,
        name: str,
        writer: AsyncTextWriter,
        data: object = None,
    ) -> None:
        """Render one associated named template to an asynchronous writer."""

        program = self._associated_program(name)
        session = self._new_render_session()
        await render_program_async_to(
            program,
            writer,
            data,
            functions=self._runtime_functions,
            missing_key=self.missing_key,
            format_mode=self.format_mode,
            _namespace=self._namespace,
            budget=self.budget,
            sandbox=self.sandbox,
            _session=session,
            _budget_state=None if session is None else session.budget_state,
        )

    def _new_render_session(self) -> RenderSession | None:
        if not self._runtime_functions.has_context_functions:
            return None
        return RenderSession.create(self, self.budget)

    def _render_template_in_session(
        self,
        name: str,
        data: object,
        session: RenderSession,
    ) -> str:
        program = self._associated_program(name)
        with session.nested():
            return render_program(
                program,
                data,
                functions=self._runtime_functions,
                missing_key=self.missing_key,
                format_mode=self.format_mode,
                _namespace=self._namespace,
                _depth=session.depth,
                budget=self.budget,
                sandbox=self.sandbox,
                _session=session,
                _budget_state=session.budget_state,
                _account_output=False,
            )

    async def _render_template_async_in_session(
        self,
        name: str,
        data: object,
        session: RenderSession,
    ) -> str:
        program = self._associated_program(name)
        with session.nested():
            return await render_program_async(
                program,
                data,
                functions=self._runtime_functions,
                missing_key=self.missing_key,
                format_mode=self.format_mode,
                _namespace=self._namespace,
                _depth=session.depth,
                budget=self.budget,
                sandbox=self.sandbox,
                _session=session,
                _budget_state=session.budget_state,
                _account_output=False,
            )

    def _render_source_in_session(
        self,
        source: str,
        data: object,
        *,
        name: str,
        session: RenderSession,
    ) -> str:
        cache_key = (id(self), name, source)
        cached = session.dynamic_cache.get(cache_key)
        derived = (
            cached
            if isinstance(cached, Template)
            else self.with_source(source, name=name)
        )
        if cached is None and len(session.dynamic_cache) < 128:
            session.dynamic_cache[cache_key] = derived
        with session.nested(derived):
            return render_program(
                derived._program,
                data,
                functions=derived._runtime_functions,
                missing_key=derived.missing_key,
                format_mode=derived.format_mode,
                _namespace=derived._namespace,
                _depth=session.depth,
                budget=derived.budget,
                sandbox=derived.sandbox,
                _session=session,
                _budget_state=session.budget_state,
                _account_output=False,
            )

    async def _render_source_async_in_session(
        self,
        source: str,
        data: object,
        *,
        name: str,
        session: RenderSession,
    ) -> str:
        cache_key = (id(self), name, source)
        cached = session.dynamic_cache.get(cache_key)
        derived = (
            cached
            if isinstance(cached, Template)
            else self.with_source(source, name=name)
        )
        if cached is None and len(session.dynamic_cache) < 128:
            session.dynamic_cache[cache_key] = derived
        with session.nested(derived):
            return await render_program_async(
                derived._program,
                data,
                functions=derived._runtime_functions,
                missing_key=derived.missing_key,
                format_mode=derived.format_mode,
                _namespace=derived._namespace,
                _depth=session.depth,
                budget=derived.budget,
                sandbox=derived.sandbox,
                _session=session,
                _budget_state=session.budget_state,
                _account_output=False,
            )

    def _associated_program(self, name: str) -> Program:
        program = self._namespace.get(name)
        if program is not None:
            return program
        error = TemplateExecutionError(f"template {name!r} is not defined")
        error.attach_location(
            self.source,
            0,
            source_name=self.name,
            template_name=name,
        )
        raise error


def render(
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
    """Parse, compile, and synchronously render a text template."""

    return Template(
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


def render_to(
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
    """Parse, compile, and render a text template to a file-like object."""

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
    ).render_to(writer, data)


async def render_async(
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
    """Parse, compile, and asynchronously render a text template."""

    return await Template(
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


async def render_async_to(
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
    """Parse, compile, and asynchronously render to a text writer."""

    await Template(
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


def _validated_functions(
    functions: Mapping[str, Callable[..., object]] | None,
) -> Mapping[str, Callable[..., object]]:
    registry = dict(functions or {})
    call_specs: dict[str, CallSpec | None] = {}
    for name, function in registry.items():
        if not _valid_function_name(name):
            raise ValueError(f"invalid template function name {name!r}")
        if not callable(function):
            raise TypeError(f"template function {name!r} must be callable")
        call_specs[name] = prepare_template_function(name, function)
    return PreparedFunctionRegistry(registry, call_specs)


def _link_association(
    program: Program,
    namespace: Mapping[str, Program],
    functions: PreparedFunctionRegistry,
) -> LinkedProgram:
    association = replace(
        program,
        definitions=tuple(
            item for name, item in namespace.items() if name != program.name
        ),
    )
    return link_program(association, functions)


def _should_use_linked(linked: LinkedProgram) -> bool:
    return (
        linked.linked_write_count + linked.linked_control_count
        > linked.template_call_count
    )


def _valid_function_name(name: str) -> bool:
    if not name:
        return False
    for index, character in enumerate(name):
        character_category = category(character)
        if character == "_":
            continue
        if character_category.startswith("L"):
            continue
        if index > 0 and character_category == "Nd":
            continue
        return False
    return True
