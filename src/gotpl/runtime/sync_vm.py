"""Synchronous execution of compact template programs."""

from collections.abc import Callable, Iterable, Iterator, Mapping, Sized
from dataclasses import dataclass, field
from functools import lru_cache, partial
from io import StringIO
from typing import Protocol, TextIO, cast
from urllib.parse import quote_plus

from gotpl.compile.instructions import (
    BranchTarget,
    CallTarget,
    CompiledCommand,
    CompiledPipeline,
    Instruction,
    OpCode,
    Operand,
    OperandKind,
    Program,
    RangeNextTarget,
    RangeTarget,
)
from gotpl.errors import TemplateExecutionError

from .awaitables import reject_awaitable
from .callables import (
    CallSpec,
    PreparedFunctionRegistry,
    TemplateCallArityError,
    invoke_prepared_context_function,
    invoke_prepared_template_function,
    invoke_template_function,
)
from .context import (
    ContextFunction,
    RenderContext,
    RenderSession,
    require_render_session,
    require_sync_implementation,
)
from .gofmt import FormatMode, sprintf
from .linked import (
    LinkedConstantOperand,
    LinkedDotOperand,
    LinkedFieldOperand,
    LinkedFieldPipeline,
    LinkedFunctionCommand,
    LinkedPipeline,
    LinkedProgram,
    LinkedValueCommand,
    LinkedVariableOperand,
    LinkedVariablePipeline,
)
from .policy import ExecutionBudget, ExecutionBudgetState, SandboxPolicy
from .results import unwrap_function_result
from .values import (
    INVALID,
    UNTYPED_NIL,
    GoPointer,
    GoSeq,
    GoSeq2,
    MissingKeyMode,
    TypedMap,
    ValueAdapter,
    is_bound_method,
)
from .values import number_value as _number_value

_UNPREPARED_CALL = object()
_MAX_TEMPLATE_DEPTH = 100_000
_VALUE_ADAPTERS: dict[MissingKeyMode, ValueAdapter] = {
    mode: ValueAdapter(mode) for mode in ("default", "zero", "error")
}


class _TextWriter(Protocol):
    def write(self, value: str, /) -> int: ...


def _empty_call_specs() -> dict[str, CallSpec | None]:
    return {}


@dataclass(slots=True)
class _ExecutionContext:
    root: object
    dot: object
    functions: Mapping[str, Callable[..., object]]
    missing_key: MissingKeyMode
    call_specs: Mapping[str, CallSpec | None] = field(default_factory=_empty_call_specs)
    format_mode: FormatMode = "go"
    logical_builtins: frozenset[str] = frozenset({"and", "or"})
    location: "_ExecutionLocation | None" = None
    budget_state: ExecutionBudgetState | None = None
    sandbox: SandboxPolicy | None = None
    adapter: ValueAdapter = field(init=False)
    scopes: list[dict[str, object]] | None = None
    dot_stack: list[object] | None = None
    ranges: list["_RangeState"] | None = None
    session: RenderSession | None = None

    def __post_init__(self) -> None:
        self.adapter = (
            _VALUE_ADAPTERS[self.missing_key]
            if self.sandbox is None
            else ValueAdapter(self.missing_key, self.sandbox)
        )

    def lookup_variable(self, name: str) -> object:
        if self.scopes is not None:
            for scope in reversed(self.scopes):
                if name in scope:
                    return scope[name]
        if name == "$":
            return self.root
        return INVALID

    def set_variable(self, name: str, value: object, *, assignment: bool) -> None:
        if assignment:
            if self.scopes is not None:
                for scope in reversed(self.scopes):
                    if name in scope:
                        scope[name] = value
                        return
            if name == "$":
                self.root = value
                return
            raise TemplateExecutionError(f"undefined variable {name!r}")
        if self.scopes is None:
            self.scopes = [{}]
        self.scopes[-1][name] = value

    def push_scope(self) -> None:
        """Enter a lexical scope, allocating storage only when needed."""

        if self.scopes is None:
            self.scopes = [{}]
        else:
            self.scopes.append({})

    def pop_scope(self) -> None:
        """Leave the current lexical scope and release empty storage."""

        if self.scopes is None:
            raise TemplateExecutionError("invalid compiled scope exit")
        self.scopes.pop()
        if not self.scopes:
            self.scopes = None


@dataclass(slots=True)
class _RangeState:
    iterator: Iterator[tuple[object, object]]
    original_dot: object
    pipeline: CompiledPipeline


@dataclass(slots=True)
class _ExecutionLocation:
    program: Program | None = None
    position: int = 0

    @property
    def source(self) -> str:
        return "" if self.program is None else self.program.source

    @property
    def source_name(self) -> str:
        program = self.program
        if program is None:
            return "template"
        return program.source_name or program.name or "template"

    @property
    def template_name(self) -> str:
        program = self.program
        if program is None:
            return "template"
        return program.name or self.source_name


def render_program(
    program: Program,
    data: object = None,
    *,
    functions: Mapping[str, Callable[..., object]] | None = None,
    missing_key: MissingKeyMode = "default",
    format_mode: FormatMode = "go",
    _namespace: Mapping[str, Program] | None = None,
    _depth: int = 0,
    _logical_builtins: frozenset[str] | None = None,
    budget: ExecutionBudget | None = None,
    sandbox: SandboxPolicy | None = None,
    _linked_program: LinkedProgram | None = None,
    _linked_namespace: Mapping[str, LinkedProgram] | None = None,
    _linked_root: LinkedProgram | None = None,
    _session: RenderSession | None = None,
    _budget_state: ExecutionBudgetState | None = None,
    _account_output: bool = True,
) -> str:
    """Execute a compiled program synchronously."""

    output = StringIO()
    render_program_to(
        program,
        output,
        data,
        functions=functions,
        missing_key=missing_key,
        format_mode=format_mode,
        _namespace=_namespace,
        _depth=_depth,
        _logical_builtins=_logical_builtins,
        budget=budget,
        sandbox=sandbox,
        _linked_program=_linked_program,
        _linked_namespace=_linked_namespace,
        _linked_root=_linked_root,
        _session=_session,
        _budget_state=_budget_state,
        _account_output=_account_output,
    )
    return output.getvalue()


def render_linked_program(
    linked: LinkedProgram,
    data: object = None,
    *,
    template_name: str | None = None,
    functions: Mapping[str, Callable[..., object]] | None = None,
    missing_key: MissingKeyMode = "default",
    format_mode: FormatMode = "go",
    budget: ExecutionBudget | None = None,
    sandbox: SandboxPolicy | None = None,
    _session: RenderSession | None = None,
    _budget_state: ExecutionBudgetState | None = None,
    _account_output: bool = True,
) -> str:
    """Execute an opt-in linked sidecar through the reference control loop."""

    linked_namespace = linked.namespace
    namespace = linked.program_namespace
    selected = linked
    if template_name is not None:
        selected = (
            linked
            if template_name == linked.program.name
            else linked_namespace.get(template_name)
        )
        if selected is None:
            raise TemplateExecutionError(f"template {template_name!r} is not defined")
    use_sidecar = (
        linked.linked_write_count + linked.linked_control_count
        > linked.template_call_count
    )
    return render_program(
        selected.program,
        data,
        functions=functions,
        missing_key=missing_key,
        format_mode=format_mode,
        _namespace=namespace,
        budget=budget,
        sandbox=sandbox,
        _linked_program=selected if use_sidecar else None,
        _linked_namespace=linked_namespace if use_sidecar else None,
        _linked_root=linked if use_sidecar else None,
        _session=_session,
        _budget_state=_budget_state,
        _account_output=_account_output,
    )


def render_linked_program_to(
    linked: LinkedProgram,
    writer: TextIO,
    data: object = None,
    *,
    template_name: str | None = None,
    functions: Mapping[str, Callable[..., object]] | None = None,
    missing_key: MissingKeyMode = "default",
    format_mode: FormatMode = "go",
    budget: ExecutionBudget | None = None,
    sandbox: SandboxPolicy | None = None,
    _session: RenderSession | None = None,
    _budget_state: ExecutionBudgetState | None = None,
    _account_output: bool = True,
) -> None:
    """Stream an opt-in linked sidecar through the reference control loop."""

    linked_namespace = linked.namespace
    selected = linked
    if template_name is not None:
        selected = (
            linked
            if template_name == linked.program.name
            else linked_namespace.get(template_name)
        )
        if selected is None:
            raise TemplateExecutionError(f"template {template_name!r} is not defined")
    use_sidecar = (
        linked.linked_write_count + linked.linked_control_count
        > linked.template_call_count
    )
    render_program_to(
        selected.program,
        writer,
        data,
        functions=functions,
        missing_key=missing_key,
        format_mode=format_mode,
        _namespace=linked.program_namespace,
        budget=budget,
        sandbox=sandbox,
        _linked_program=selected if use_sidecar else None,
        _linked_namespace=linked_namespace if use_sidecar else None,
        _linked_root=linked if use_sidecar else None,
        _session=_session,
        _budget_state=_budget_state,
        _account_output=_account_output,
    )


def render_program_to(
    program: Program,
    writer: TextIO,
    data: object = None,
    *,
    functions: Mapping[str, Callable[..., object]] | None = None,
    missing_key: MissingKeyMode = "default",
    format_mode: FormatMode = "go",
    _namespace: Mapping[str, Program] | None = None,
    _depth: int = 0,
    _logical_builtins: frozenset[str] | None = None,
    _location: _ExecutionLocation | None = None,
    budget: ExecutionBudget | None = None,
    sandbox: SandboxPolicy | None = None,
    _budget_state: ExecutionBudgetState | None = None,
    _linked_program: LinkedProgram | None = None,
    _linked_namespace: Mapping[str, LinkedProgram] | None = None,
    _linked_root: LinkedProgram | None = None,
    _session: RenderSession | None = None,
    _account_output: bool = True,
) -> None:
    """Execute a compiled program and stream text to a file-like object."""

    location = _ExecutionLocation() if _location is None else _location
    try:
        budget_state = (
            _budget_state
            if _budget_state is not None
            else ExecutionBudgetState(budget)
            if budget is not None
            else None
        )
        budgeted_writer = (
            _BudgetedWriter(writer, budget_state)
            if budget_state is not None and _account_output
            else writer
        )
        _render_program_to(
            program,
            budgeted_writer,
            data,
            functions=functions,
            missing_key=missing_key,
            format_mode=format_mode,
            _namespace=_namespace,
            _depth=_depth,
            _logical_builtins=_logical_builtins,
            _location=location,
            sandbox=sandbox,
            _budget_state=budget_state,
            _linked_program=_linked_program,
            _linked_namespace=_linked_namespace,
            _linked_root=_linked_root,
            _session=_session,
        )
    except TemplateExecutionError as error:
        error.attach_location(
            location.source,
            location.position,
            source_name=location.source_name,
            template_name=location.template_name,
        )
        raise


def _render_program_to(
    program: Program,
    writer: _TextWriter,
    data: object = None,
    *,
    functions: Mapping[str, Callable[..., object]] | None = None,
    missing_key: MissingKeyMode = "default",
    format_mode: FormatMode = "go",
    _namespace: Mapping[str, Program] | None = None,
    _depth: int = 0,
    _logical_builtins: frozenset[str] | None = None,
    _location: _ExecutionLocation,
    sandbox: SandboxPolicy | None,
    _budget_state: ExecutionBudgetState | None,
    _linked_program: LinkedProgram | None,
    _linked_namespace: Mapping[str, LinkedProgram] | None,
    _linked_root: LinkedProgram | None,
    _session: RenderSession | None,
) -> None:
    """Execute without translating the current source location."""

    _location.program = program
    _location.position = 0

    if _depth >= _MAX_TEMPLATE_DEPTH:
        raise TemplateExecutionError(
            f"exceeded maximum template depth ({_MAX_TEMPLATE_DEPTH})"
        )
    namespace = (
        {
            **{definition.name: definition for definition in program.definitions},
            **({program.name: program} if program.name else {}),
        }
        if _namespace is None
        else _namespace
    )
    registry = _execution_function_registry(format_mode, functions, sandbox=sandbox)
    logical_builtins = (
        frozenset(
            name for name in ("and", "or") if functions is None or name not in functions
        )
        if _logical_builtins is None
        else _logical_builtins
    )
    context = _ExecutionContext(
        data,
        data,
        registry,
        missing_key,
        registry.call_specs,
        format_mode,
        logical_builtins,
        _location,
        _budget_state,
        sandbox,
        session=_session,
    )
    current_program = program
    instructions = current_program.instructions
    current_linked = _linked_program
    linked_pipelines = (
        None if current_linked is None else current_linked.write_pipelines
    )
    linked_controls = (
        None if current_linked is None else current_linked.control_pipelines
    )
    pc = 0
    frames: list[tuple[Program, _ExecutionContext, int]] | None = None
    linked_frames: list[LinkedProgram | None] | None = (
        [] if current_linked is not None else None
    )
    while True:
        if pc >= len(instructions):
            if not frames:
                break
            current_program, context, pc = frames.pop()
            instructions = current_program.instructions
            if linked_frames is not None:
                current_linked = linked_frames.pop()
                linked_pipelines = (
                    None if current_linked is None else current_linked.write_pipelines
                )
                linked_controls = (
                    None if current_linked is None else current_linked.control_pipelines
                )
            _location.program = current_program
            _location.position = 0
            continue
        instruction = instructions[pc]
        _location.position = instruction.source_start
        opcode = instruction.opcode
        if opcode is OpCode.WRITE_TEXT:
            if isinstance(instruction.argument, str):
                _write_text(writer, instruction.argument)
            pc += 1
        elif opcode is OpCode.WRITE_DOT:
            _write_text(writer, format_value(context.dot, context.format_mode))
            pc += 1
        elif opcode is OpCode.WRITE_PIPELINE:
            pipeline = _require_pipeline(instruction)
            linked_pipeline = None if linked_pipelines is None else linked_pipelines[pc]
            if linked_pipeline is None:
                value = _evaluate_pipeline(pipeline, context)
            elif isinstance(linked_pipeline, LinkedFieldPipeline):
                value = _evaluate_linked_field_pipeline(linked_pipeline, context)
            elif isinstance(linked_pipeline, LinkedVariablePipeline):
                value = _evaluate_linked_variable_pipeline(linked_pipeline, context)
            else:
                value = _evaluate_linked_pipeline(linked_pipeline, context)
            _write_text(
                writer,
                format_value(value, context.format_mode),
            )
            pc += 1
        elif opcode is OpCode.EVAL_PIPELINE:
            _evaluate_pipeline(_require_pipeline(instruction), context)
            pc += 1
        elif opcode is OpCode.PUSH_SCOPE:
            context.push_scope()
            pc += 1
        elif opcode is OpCode.POP_SCOPE:
            context.pop_scope()
            pc += 1
        elif opcode is OpCode.JUMP_IF_FALSE:
            target = _require_branch(instruction)
            linked_control = None if linked_controls is None else linked_controls[pc]
            value = (
                _evaluate_pipeline(target.pipeline, context)
                if linked_control is None
                else _evaluate_linked_field_pipeline(linked_control, context)
                if isinstance(linked_control, LinkedFieldPipeline)
                else _evaluate_linked_variable_pipeline(linked_control, context)
            )
            pc = pc + 1 if context.adapter.is_true(value) else target.target
        elif opcode is OpCode.ENTER_WITH:
            target = _require_branch(instruction)
            linked_control = None if linked_controls is None else linked_controls[pc]
            value = (
                _evaluate_pipeline(target.pipeline, context)
                if linked_control is None
                else _evaluate_linked_field_pipeline(linked_control, context)
                if isinstance(linked_control, LinkedFieldPipeline)
                else _evaluate_linked_variable_pipeline(linked_control, context)
            )
            if context.adapter.is_true(value):
                if context.dot_stack is None:
                    context.dot_stack = []
                context.dot_stack.append(context.dot)
                context.dot = value
                pc += 1
            else:
                pc = target.target
        elif opcode is OpCode.EXIT_WITH:
            if context.dot_stack is None:
                raise TemplateExecutionError("invalid compiled with exit")
            context.dot = context.dot_stack.pop()
            if not context.dot_stack:
                context.dot_stack = None
            pc += 1
        elif opcode is OpCode.ITERATE:
            target = _require_range(instruction)
            linked_control = None if linked_controls is None else linked_controls[pc]
            value = (
                _evaluate_pipeline(target.pipeline, context, bind=False)
                if linked_control is None
                else _evaluate_linked_field_pipeline(
                    linked_control,
                    context,
                    bind=False,
                )
                if isinstance(linked_control, LinkedFieldPipeline)
                else _evaluate_linked_variable_pipeline(
                    linked_control,
                    context,
                    bind=False,
                )
            )
            iterator = iter(_range_entries(value, len(target.pipeline.bindings)))
            try:
                key, item = _next_range_item(iterator)
            except StopIteration:
                pc = target.empty_target
            else:
                if context.budget_state is not None:
                    context.budget_state.consume_iteration()
                if context.ranges is None:
                    context.ranges = []
                context.ranges.append(
                    _RangeState(iterator, context.dot, target.pipeline)
                )
                _enter_range_item(context, target.pipeline, key, item)
                pc += 1
        elif opcode is OpCode.NEXT_ITERATION:
            target = _require_range_next(instruction)
            if context.ranges is None:
                raise TemplateExecutionError("invalid compiled range continuation")
            state = context.ranges[-1]
            try:
                key, item = _next_range_item(state.iterator)
            except StopIteration:
                context.dot = state.original_dot
                context.ranges.pop()
                if not context.ranges:
                    context.ranges = None
                pc = target.exit_target
            else:
                if context.budget_state is not None:
                    context.budget_state.consume_iteration()
                _enter_range_item(context, state.pipeline, key, item)
                pc = target.body_target
        elif opcode is OpCode.BREAK_RANGE:
            if not isinstance(instruction.argument, int):
                raise _invalid_instruction(instruction)
            if context.ranges is None:
                raise TemplateExecutionError("invalid compiled range break")
            state = context.ranges.pop()
            if not context.ranges:
                context.ranges = None
            context.dot = state.original_dot
            pc = instruction.argument
        elif opcode is OpCode.JUMP:
            if not isinstance(instruction.argument, int):
                raise _invalid_instruction(instruction)
            pc = instruction.argument
        elif opcode is OpCode.CALL_TEMPLATE:
            target = _require_call(instruction)
            callee = namespace.get(target.name)
            if callee is None:
                raise TemplateExecutionError(f"template {target.name!r} is not defined")
            call_dot = (
                None
                if target.pipeline is None
                else _evaluate_pipeline(target.pipeline, context)
            )
            frame_count = 0 if frames is None else len(frames)
            if context.budget_state is not None:
                context.budget_state.check_template_depth(_depth + frame_count + 1)
            if _depth + frame_count >= _MAX_TEMPLATE_DEPTH:
                raise TemplateExecutionError(
                    f"exceeded maximum template depth ({_MAX_TEMPLATE_DEPTH})"
                )
            if frames is None:
                frames = []
            frames.append((current_program, context, pc + 1))
            if linked_frames is not None:
                linked_frames.append(current_linked)
            current_program = callee
            instructions = current_program.instructions
            if linked_frames is not None:
                current_linked = (
                    _linked_root
                    if _linked_root is not None
                    and target.name == _linked_root.program.name
                    else None
                    if _linked_namespace is None
                    else _linked_namespace.get(target.name)
                )
                linked_pipelines = (
                    None if current_linked is None else current_linked.write_pipelines
                )
                linked_controls = (
                    None if current_linked is None else current_linked.control_pipelines
                )
            _location.program = current_program
            _location.position = 0
            context = _ExecutionContext(
                call_dot,
                call_dot,
                registry,
                missing_key,
                registry.call_specs,
                format_mode,
                logical_builtins,
                _location,
                context.budget_state,
                sandbox,
                session=context.session,
            )
            pc = 0
        else:
            raise TemplateExecutionError(
                f"opcode {opcode.name} is not implemented by the synchronous runtime"
            )


def _evaluate_pipeline(
    pipeline: CompiledPipeline,
    context: _ExecutionContext,
    *,
    bind: bool = True,
) -> object:
    if context.location is not None:
        context.location.position = pipeline.source_start
    value: object = INVALID
    commands = pipeline.commands
    if len(commands) == 1:
        value = _evaluate_command(commands[0], context, piped=INVALID)
    else:
        for index, command in enumerate(commands):
            value = _evaluate_command(
                command,
                context,
                piped=value if index else INVALID,
            )
    if bind:
        for binding in pipeline.bindings:
            context.set_variable(binding, value, assignment=pipeline.is_assignment)
    return value


def _evaluate_linked_pipeline(
    pipeline: LinkedPipeline,
    context: _ExecutionContext,
    *,
    bind: bool = True,
) -> object:
    if context.location is not None:
        context.location.position = pipeline.source_start
    value: object = INVALID
    for command in pipeline.commands:
        if isinstance(command, LinkedFunctionCommand):
            arguments = [
                _evaluate_linked_argument(item, context) for item in command.operands
            ]
            if value is not INVALID:
                arguments.append(value)
            value = (
                _invoke_linked_direct_function(
                    command.name,
                    command.function,
                    arguments,
                    context.budget_state,
                )
                if command.direct
                else _invoke_registered_function(
                    command.name,
                    command.function,
                    arguments,
                    command.spec,
                    context,
                )
            )
            continue
        assert isinstance(command, LinkedValueCommand)
        arguments = [_evaluate_linked_operand(command.operands[0], context)]
        arguments.extend(
            _evaluate_linked_argument(item, context) for item in command.operands[1:]
        )
        if value is not INVALID:
            arguments.append(value)
        first_value = arguments[0]
        if is_bound_method(first_value):
            method_name = getattr(first_value, "__name__", "method")
            value = _invoke_registered_function(
                method_name if isinstance(method_name, str) else "method",
                first_value,
                arguments[1:],
                _UNPREPARED_CALL,
                context,
            )
        elif len(arguments) != 1:
            raise TemplateExecutionError("non-callable command has arguments")
        else:
            value = first_value
    if bind:
        for binding in pipeline.bindings:
            context.set_variable(binding, value, assignment=pipeline.is_assignment)
    return value


def _evaluate_linked_operand(
    operand: (
        Operand
        | LinkedConstantOperand
        | LinkedDotOperand
        | LinkedFieldOperand
        | LinkedVariableOperand
    ),
    context: _ExecutionContext,
) -> object:
    if isinstance(operand, LinkedConstantOperand):
        return operand.value
    if isinstance(operand, LinkedDotOperand):
        return context.dot
    if isinstance(operand, LinkedFieldOperand):
        return (
            context.adapter.lookup(context.dot, operand.fields[0])
            if len(operand.fields) == 1
            else _lookup_chain(context.dot, operand.fields, context)
        )
    if isinstance(operand, LinkedVariableOperand):
        value = context.lookup_variable(operand.name)
        if not operand.fields:
            return value
        return (
            context.adapter.lookup(value, operand.fields[0])
            if len(operand.fields) == 1
            else _lookup_chain(value, operand.fields, context)
        )
    return _evaluate_operand(operand, context)


def _evaluate_linked_argument(
    operand: (
        Operand
        | LinkedConstantOperand
        | LinkedDotOperand
        | LinkedFieldOperand
        | LinkedVariableOperand
    ),
    context: _ExecutionContext,
) -> object:
    return _invoke_argument_method(_evaluate_linked_operand(operand, context), context)


def _evaluate_linked_field_pipeline(
    pipeline: LinkedFieldPipeline,
    context: _ExecutionContext,
    *,
    bind: bool = True,
) -> object:
    if context.location is not None:
        context.location.position = pipeline.source_start
    value = (
        context.adapter.lookup(context.dot, pipeline.fields[0])
        if len(pipeline.fields) == 1
        else _lookup_chain(context.dot, pipeline.fields, context)
    )
    return _finish_linked_lookup_pipeline(pipeline, value, context, bind=bind)


def _evaluate_linked_variable_pipeline(
    pipeline: LinkedVariablePipeline,
    context: _ExecutionContext,
    *,
    bind: bool = True,
) -> object:
    if context.location is not None:
        context.location.position = pipeline.source_start
    value = context.lookup_variable(pipeline.name)
    value = (
        context.adapter.lookup(value, pipeline.fields[0])
        if len(pipeline.fields) == 1
        else _lookup_chain(value, pipeline.fields, context)
    )
    return _finish_linked_lookup_pipeline(pipeline, value, context, bind=bind)


def _finish_linked_lookup_pipeline(
    pipeline: LinkedFieldPipeline | LinkedVariablePipeline,
    value: object,
    context: _ExecutionContext,
    *,
    bind: bool,
) -> object:
    if is_bound_method(value):
        method_name = getattr(value, "__name__", "method")
        value = _invoke_registered_function(
            method_name if isinstance(method_name, str) else "method",
            value,
            [],
            _UNPREPARED_CALL,
            context,
        )
    for function in pipeline.functions:
        value = _invoke_linked_unary_function(
            function.name,
            function.function,
            value,
            context.budget_state,
        )
    if bind:
        for binding in pipeline.bindings:
            context.set_variable(binding, value, assignment=pipeline.is_assignment)
    return value


def _invoke_linked_unary_function(
    name: str,
    function: Callable[..., object],
    value: object,
    budget_state: ExecutionBudgetState | None,
) -> object:
    if budget_state is not None:
        budget_state.consume_function_call()
    try:
        return unwrap_function_result(reject_awaitable(function(value)))
    except TemplateExecutionError:
        raise
    except Exception as error:
        raise TemplateExecutionError(f"function {name!r} failed: {error}") from error


def _invoke_linked_direct_function(
    name: str,
    function: Callable[..., object],
    arguments: list[object],
    budget_state: ExecutionBudgetState | None,
) -> object:
    if budget_state is not None:
        budget_state.consume_function_call()
    try:
        return unwrap_function_result(reject_awaitable(function(*arguments)))
    except TemplateExecutionError:
        raise
    except Exception as error:
        raise TemplateExecutionError(f"function {name!r} failed: {error}") from error


def _write_text(writer: _TextWriter, value: str) -> None:
    written = writer.write(value)
    if written != len(value):
        raise OSError(f"short write: wrote {written} of {len(value)} characters")


@dataclass(slots=True)
class _BudgetedWriter:
    writer: _TextWriter
    state: ExecutionBudgetState

    def write(self, value: str, /) -> int:
        self.state.consume_output(len(value))
        return self.writer.write(value)


def _evaluate_command(
    command: CompiledCommand,
    context: _ExecutionContext,
    *,
    piped: object,
) -> object:
    first = command.arguments[0]
    if first.kind is OperandKind.FUNCTION:
        name = first.value
        if not isinstance(name, str):
            raise TemplateExecutionError("invalid compiled function name")
        if name in context.logical_builtins:
            return _evaluate_logical(name, command, context, piped=piped)
        function = context.functions.get(name)
        if function is None:
            raise TemplateExecutionError(f"function {name!r} is not defined")
        arguments = [
            _evaluate_argument(item, context) for item in command.arguments[1:]
        ]
        if piped is not INVALID:
            arguments.append(piped)
        return _invoke_registered_function(
            name,
            function,
            arguments,
            context.call_specs[name],
            context,
        )
    arguments = [_evaluate_operand(first, context)]
    arguments.extend(
        _evaluate_argument(item, context) for item in command.arguments[1:]
    )
    if piped is not INVALID:
        arguments.append(piped)
    first_value = arguments[0]
    if is_bound_method(first_value):
        method_name = getattr(first_value, "__name__", "method")
        return _invoke_registered_function(
            method_name if isinstance(method_name, str) else "method",
            first_value,
            arguments[1:],
            _UNPREPARED_CALL,
            context,
        )
    if len(arguments) != 1:
        raise TemplateExecutionError("non-callable command has arguments")
    return first_value


def _evaluate_argument(operand: Operand, context: _ExecutionContext) -> object:
    return _invoke_argument_method(_evaluate_operand(operand, context), context)


def _invoke_argument_method(value: object, context: _ExecutionContext) -> object:
    if not is_bound_method(value):
        return value
    method_name = getattr(value, "__name__", "method")
    return _invoke_registered_function(
        method_name if isinstance(method_name, str) else "method",
        value,
        [],
        _UNPREPARED_CALL,
        context,
    )


def _evaluate_operand(operand: Operand, context: _ExecutionContext) -> object:
    kind = operand.kind
    if kind is OperandKind.DOT:
        value = context.dot
    elif kind is OperandKind.NIL:
        value = UNTYPED_NIL
    elif kind is OperandKind.BOOL:
        value = operand.value is True
    elif kind in {OperandKind.NUMBER, OperandKind.COMPLEX}:
        value = _number_value(
            operand.value,
            is_complex=kind is OperandKind.COMPLEX,
        )
    elif kind is OperandKind.STRING:
        value = operand.value
    elif kind is OperandKind.CHARACTER:
        value = ord(operand.value) if isinstance(operand.value, str) else INVALID
    elif kind is OperandKind.FIELD:
        value = _lookup_chain(context.dot, operand.fields, context)
    elif kind is OperandKind.VARIABLE:
        name = operand.value
        value = context.lookup_variable(name) if isinstance(name, str) else INVALID
        value = _lookup_chain(value, operand.fields, context)
    elif kind is OperandKind.SUBPIPELINE:
        if operand.pipeline is None:
            return INVALID
        value = _evaluate_pipeline(operand.pipeline, context)
        value = _lookup_chain(value, operand.fields, context)
    elif kind is OperandKind.FUNCTION and isinstance(operand.value, str):
        function = context.functions.get(operand.value)
        if function is None:
            raise TemplateExecutionError(f"function {operand.value!r} is not defined")
        value = _invoke_registered_function(
            operand.value,
            function,
            [],
            context.call_specs[operand.value],
            context,
        )
    else:
        raise TemplateExecutionError(f"operand {kind.name} is not directly evaluable")
    return value


def _lookup_chain(
    value: object,
    fields: tuple[str, ...],
    context: _ExecutionContext,
) -> object:
    for index, member_name in enumerate(fields):
        value = context.adapter.lookup(value, member_name)
        if value is INVALID:
            break
        if index < len(fields) - 1 and is_bound_method(value):
            value = _invoke_registered_function(
                member_name, value, [], _UNPREPARED_CALL, context
            )
    return value


def _invoke_registered_function(
    name: str,
    function: Callable[..., object],
    arguments: list[object],
    spec: object = _UNPREPARED_CALL,
    context: _ExecutionContext | None = None,
) -> object:
    budget_state = None if context is None else context.budget_state
    if budget_state is not None:
        budget_state.consume_function_call()
    try:
        if isinstance(function, ContextFunction):
            if context is None:
                raise TemplateExecutionError(
                    f"context function {name!r} has no execution context"
                )
            session = require_render_session(context.session)
            location = context.location
            render_context = RenderContext(
                session,
                root=context.root,
                dot=context.dot,
                source_name=("template" if location is None else location.source_name),
                template_name=(
                    "template" if location is None else location.template_name
                ),
            )
            result = invoke_prepared_context_function(
                name,
                require_sync_implementation(function),
                render_context,
                arguments,
                cast(CallSpec | None, spec),
            )
        else:
            result = (
                invoke_template_function(name, function, arguments)
                if spec is _UNPREPARED_CALL
                else invoke_prepared_template_function(
                    name,
                    function,
                    arguments,
                    cast(CallSpec | None, spec),
                )
            )
        return unwrap_function_result(reject_awaitable(result))
    except TemplateExecutionError:
        raise
    except TemplateCallArityError as error:
        raise TemplateExecutionError(str(error)) from error
    except Exception as error:
        raise TemplateExecutionError(f"function {name!r} failed: {error}") from error


def _require_pipeline(instruction: Instruction) -> CompiledPipeline:
    argument = instruction.argument
    if not isinstance(argument, CompiledPipeline):
        raise _invalid_instruction(instruction)
    return argument


def _require_branch(instruction: Instruction) -> BranchTarget:
    argument = instruction.argument
    if not isinstance(argument, BranchTarget):
        raise _invalid_instruction(instruction)
    return argument


def _require_call(instruction: Instruction) -> CallTarget:
    argument = instruction.argument
    if not isinstance(argument, CallTarget):
        raise _invalid_instruction(instruction)
    return argument


def _require_range(instruction: Instruction) -> RangeTarget:
    argument = instruction.argument
    if not isinstance(argument, RangeTarget):
        raise _invalid_instruction(instruction)
    return argument


def _require_range_next(instruction: Instruction) -> RangeNextTarget:
    argument = instruction.argument
    if not isinstance(argument, RangeNextTarget):
        raise _invalid_instruction(instruction)
    return argument


def _invalid_instruction(instruction: Instruction) -> TemplateExecutionError:
    return TemplateExecutionError(
        f"invalid argument for instruction {instruction.opcode.name}"
    )


def format_value(value: object, format_mode: FormatMode = "go") -> str:
    """Format one action result for template output."""

    if value is UNTYPED_NIL:
        raise TemplateExecutionError("nil is not a command")
    if value is INVALID:
        return "<no value>"
    if format_mode == "python":
        return str(value)
    if value is None:
        return "<no value>"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, float):
        return sprintf("%v", value, format_mode=format_mode)
    if isinstance(value, GoPointer):
        pointer = cast(GoPointer[object], value)
        return "<nil>" if pointer.value is None else f"0x{pointer.address:x}"
    if isinstance(value, (bytes, bytearray)):
        return f"[{' '.join(str(item) for item in value)}]"
    if isinstance(value, complex):
        sign = "+" if value.imag >= 0 else "-"
        return f"({value.real:g}{sign}{abs(value.imag):g}i)"
    if isinstance(value, Mapping):
        mapping = cast(Mapping[object, object], value)
        keys = _sorted_mapping_keys(list(mapping))
        entries = (
            f"{_format_nested(key, format_mode)}:"
            f"{_format_nested(mapping[key], format_mode)}"
            for key in keys
        )
        return f"map[{' '.join(entries)}]"
    if isinstance(value, (list, tuple)):
        sequence = cast(list[object] | tuple[object, ...], value)
        return f"[{' '.join(_format_nested(item, format_mode) for item in sequence)}]"
    return str(value)


def _format_nested(value: object, format_mode: FormatMode) -> str:
    if value is None:
        return "<nil>"
    return format_value(value, format_mode)


def _range_entries(
    value: object, binding_count: int = 0
) -> Iterable[tuple[object, object]]:
    if value is INVALID or value is UNTYPED_NIL or value is None:
        return ()
    if isinstance(value, Mapping):
        mapping = cast(Mapping[object, object], value)
        keys: list[object] = list(mapping)
        keys = _sorted_mapping_keys(keys)
        return ((key, mapping[key]) for key in keys)
    if isinstance(value, (list, tuple)):
        sequence = cast(list[object] | tuple[object, ...], value)
        return enumerate(sequence)
    if isinstance(value, int) and not isinstance(value, bool):
        if binding_count > 1:
            raise TemplateExecutionError(
                f"can't use {value} to iterate over more than one variable"
            )
        return ((index, index) for index in range(max(value, 0)))
    if isinstance(value, GoSeq):
        if binding_count > 1:
            raise TemplateExecutionError(
                "can't use GoSeq to iterate over more than one variable"
            )
        sequence = cast(GoSeq[object], value)
        return ((INVALID, item) for item in sequence.values)
    if isinstance(value, GoSeq2):
        sequence2 = cast(GoSeq2[object, object], value)
        if binding_count > 1:
            return ((key, item) for key, item in sequence2.values)
        return ((INVALID, key) for key, _ in sequence2.values)
    if isinstance(value, Iterable) and not isinstance(value, (str, bytes)):
        iterable = cast(Iterable[object], value)
        return enumerate(iterable)
    raise TemplateExecutionError(f"range cannot iterate over {type(value).__name__}")


def _next_range_item(
    iterator: Iterator[tuple[object, object]],
) -> tuple[object, object]:
    try:
        return next(iterator)
    except StopIteration:
        raise
    except TemplateExecutionError:
        raise
    except Exception as error:
        raise TemplateExecutionError(f"range iterator failed: {error}") from error


def _mapping_sort_key(value: object) -> tuple[str, str]:
    return type(value).__name__, repr(value)


def _complex_sort_key(value: complex) -> tuple[float, float]:
    return float(value.real), float(value.imag)


def _sorted_mapping_keys(keys: list[object]) -> list[object]:
    if keys and all(type(key) is complex for key in keys):
        complex_keys = [cast(complex, key) for key in keys]
        return cast(list[object], sorted(complex_keys, key=_complex_sort_key))
    if (
        keys
        and all(type(key) is type(keys[0]) for key in keys)
        and isinstance(keys[0], (bool, int, float, str))
    ):
        return sorted(keys)  # type: ignore[type-var]
    return sorted(keys, key=_mapping_sort_key)


def _enter_range_item(
    context: _ExecutionContext,
    pipeline: CompiledPipeline,
    key: object,
    value: object,
) -> None:
    context.dot = value
    bindings = pipeline.bindings
    if len(bindings) == 1:
        context.set_variable(bindings[0], value, assignment=pipeline.is_assignment)
    elif len(bindings) == 2:
        context.set_variable(bindings[0], key, assignment=pipeline.is_assignment)
        context.set_variable(bindings[1], value, assignment=pipeline.is_assignment)


@lru_cache(maxsize=2)
def _builtin_functions(
    format_mode: FormatMode,
) -> PreparedFunctionRegistry:
    return PreparedFunctionRegistry(
        {
            "call": _call,
            "eq": _equal,
            "ge": _greater_equal,
            "gt": _greater,
            "html": partial(_html, format_mode=format_mode),
            "index": _index,
            "js": partial(_js, format_mode=format_mode),
            "le": _less_equal,
            "len": _length,
            "lt": _less,
            "ne": _not_equal,
            "not": _not,
            "print": partial(_print, format_mode=format_mode),
            "printf": partial(_printf, format_mode=format_mode),
            "println": partial(_println, format_mode=format_mode),
            "slice": _slice,
            "urlquery": partial(_urlquery, format_mode=format_mode),
        }
    )


def _execution_function_registry(
    format_mode: FormatMode,
    functions: Mapping[str, Callable[..., object]] | None,
    *,
    sandbox: SandboxPolicy | None = None,
) -> PreparedFunctionRegistry:
    if (
        isinstance(functions, PreparedFunctionRegistry)
        and functions.includes_builtins
        and sandbox is None
    ):
        return functions
    builtins = _builtin_functions(format_mode)
    registry = dict(builtins)
    call_specs = dict(builtins.call_specs)
    if functions is not None:
        registry.update(functions)
        if isinstance(functions, PreparedFunctionRegistry):
            call_specs.update(functions.call_specs)
        else:
            prepared = PreparedFunctionRegistry(functions)
            call_specs.update(prepared.call_specs)
    if sandbox is not None:
        registry.pop("call", None)
        call_specs.pop("call", None)
    return PreparedFunctionRegistry(registry, call_specs, includes_builtins=True)


def _evaluate_logical(
    name: str,
    command: CompiledCommand,
    context: _ExecutionContext,
    *,
    piped: object,
) -> object:
    operands = command.arguments[1:]
    if not operands and piped is INVALID:
        raise TemplateExecutionError(f"function {name!r} requires an argument")
    value: object = INVALID
    for operand in operands:
        value = _evaluate_operand(operand, context)
        truth = context.adapter.is_true(value)
        if (name == "and" and not truth) or (name == "or" and truth):
            return value
    if piped is not INVALID:
        return piped
    return value


def _equal(first: object, *others: object) -> bool:
    if not others:
        raise TypeError("eq requires at least two arguments")
    return any(_equal_pair(first, other) for other in others)


def _not_equal(left: object, right: object) -> bool:
    return not _equal_pair(left, right)


def _less(left: object, right: object) -> bool:
    return _order_compare(left, right, "lt")


def _less_equal(left: object, right: object) -> bool:
    return _order_compare(left, right, "le")


def _greater(left: object, right: object) -> bool:
    return _order_compare(left, right, "gt")


def _greater_equal(left: object, right: object) -> bool:
    return _order_compare(left, right, "ge")


def _comparison_kind(value: object) -> str:
    if value is INVALID or value is UNTYPED_NIL or value is None:
        return "nil"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, complex):
        return "complex"
    if isinstance(value, str):
        return "string"
    if isinstance(value, GoPointer):
        return "pointer"
    return "other"


def _equal_pair(left: object, right: object) -> bool:
    left_kind = _comparison_kind(left)
    right_kind = _comparison_kind(right)
    if left_kind == "nil" or right_kind == "nil":
        if left_kind == right_kind:
            return True
        nonnil = right if left_kind == "nil" else left
        if isinstance(nonnil, GoPointer):
            return cast(GoPointer[object], nonnil).value is None
        if _is_noncomparable(nonnil) or callable(nonnil):
            return False
        raise TypeError("incompatible types for comparison")
    if left_kind != right_kind:
        raise TypeError("incompatible types for comparison")
    if _is_noncomparable(left) or _is_noncomparable(right):
        raise TypeError("non-comparable type")
    if isinstance(left, GoPointer) and isinstance(right, GoPointer):
        left_pointer = cast(GoPointer[object], left)
        right_pointer = cast(GoPointer[object], right)
        if left_pointer.target_type != right_pointer.target_type:
            raise TypeError("incompatible types for comparison")
        return left_pointer.address == right_pointer.address
    return left == right


def _is_noncomparable(value: object) -> bool:
    return isinstance(
        value,
        (Mapping, list, tuple, set, frozenset, bytes, bytearray),
    )


def _order_compare(left: object, right: object, operation: str) -> bool:
    left_kind = _comparison_kind(left)
    right_kind = _comparison_kind(right)
    if left_kind != right_kind:
        raise TypeError("incompatible types for comparison")
    if left_kind not in {"int", "float", "string"}:
        raise TypeError("invalid type for comparison")
    if operation == "lt":
        return left < right  # type: ignore[operator]
    if operation == "le":
        return left <= right  # type: ignore[operator]
    if operation == "gt":
        return left > right  # type: ignore[operator]
    return left >= right  # type: ignore[operator]


def _not(value: object) -> bool:
    return not ValueAdapter().is_true(value)


def _length(value: object) -> int:
    if isinstance(value, str):
        return len(value.encode())
    if not isinstance(value, Sized):
        raise TypeError(f"value of type {type(value).__name__} has no length")
    return len(value)


def _printf(
    format_string: object,
    *values: object,
    format_mode: FormatMode,
) -> str:
    return sprintf(format_string, *values, format_mode=format_mode)


def _print(*values: object, format_mode: FormatMode) -> str:
    return _join_print_values(
        values,
        untyped_nil="<nil>",
        format_mode=format_mode,
    )


def _join_print_values(
    values: tuple[object, ...],
    *,
    untyped_nil: str,
    format_mode: FormatMode,
) -> str:
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
            untyped_nil if value is UNTYPED_NIL else format_value(value, format_mode)
        )
        previous = value
    return "".join(output)


def _println(*values: object, format_mode: FormatMode) -> str:
    formatted = (
        "<nil>" if value is UNTYPED_NIL else format_value(value, format_mode)
        for value in values
    )
    return " ".join(formatted) + "\n"


def _index(value: object, *indexes: object) -> object:
    for index in indexes:
        if isinstance(value, Mapping):
            mapping = cast(Mapping[object, object], value)
            value = (
                mapping[index]
                if index in mapping
                else mapping.zero
                if isinstance(mapping, TypedMap)
                else INVALID
            )
        elif isinstance(value, (list, tuple, str, bytes)):
            if not isinstance(index, int) or isinstance(index, bool):
                raise TypeError("sequence index must be an integer")
            sequence = (
                value.encode()
                if isinstance(value, str)
                else cast(list[object] | tuple[object, ...] | bytes, value)
            )
            if index < 0 or index >= len(sequence):
                raise IndexError("index out of range")
            value = sequence[index]
        else:
            raise TypeError(f"cannot index value of type {type(value).__name__}")
    return value


def _slice(value: object, *indexes: object) -> object:
    if not isinstance(value, (list, tuple, str, bytes)):
        raise TypeError(f"cannot slice value of type {type(value).__name__}")
    if len(indexes) > 3 or not all(
        isinstance(index, int) and not isinstance(index, bool) for index in indexes
    ):
        raise TypeError("slice requires zero to three integer indexes")
    if len(indexes) == 3 and isinstance(value, str):
        raise TypeError("cannot three-index slice a string")
    is_string = isinstance(value, str)
    sequence = (
        value.encode()
        if is_string
        else cast(list[object] | tuple[object, ...] | bytes, value)
    )
    length = len(sequence)
    start = cast(int, indexes[0]) if indexes else 0
    stop = cast(int, indexes[1]) if len(indexes) >= 2 else length
    capacity = cast(int, indexes[2]) if len(indexes) == 3 else length
    if not 0 <= start <= stop <= capacity <= length:
        raise IndexError("slice index out of bounds")
    sliced = sequence[start:stop]
    if is_string:
        return cast(bytes, sliced).decode(errors="replace")
    return cast(object, sliced)


def _call(function: object, *arguments: object) -> object:
    if not callable(function):
        raise TypeError(f"value of type {type(function).__name__} is not callable")
    return invoke_template_function("call target", function, arguments)


def _html(*values: object, format_mode: FormatMode) -> str:
    text = _join_print_values(
        values,
        untyped_nil="<no value>",
        format_mode=format_mode,
    )
    replacements = {
        "\x00": "\ufffd",
        '"': "&#34;",
        "'": "&#39;",
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
    }
    return "".join(replacements.get(character, character) for character in text)


def _urlquery(*values: object, format_mode: FormatMode) -> str:
    return quote_plus(
        _join_print_values(
            values,
            untyped_nil="<no value>",
            format_mode=format_mode,
        ),
        safe="",
    )


def _js(*values: object, format_mode: FormatMode) -> str:
    text = _join_print_values(
        values,
        untyped_nil="<no value>",
        format_mode=format_mode,
    )
    replacements = {
        "\\": r"\\",
        "'": r"\'",
        '"': r"\"",
        "<": r"\u003C",
        ">": r"\u003E",
        "&": r"\u0026",
        "=": r"\u003D",
    }
    output: list[str] = []
    for character in text:
        replacement = replacements.get(character)
        if replacement is not None:
            output.append(replacement)
        elif ord(character) < 0x20 or ord(character) in {0x2028, 0x2029}:
            output.append(f"\\u{ord(character):04X}")
        else:
            output.append(character)
    return "".join(output)
