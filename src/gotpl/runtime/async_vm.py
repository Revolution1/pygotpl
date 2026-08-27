"""Asynchronous execution of compact template programs."""

from collections.abc import Awaitable, Callable, Mapping
from io import StringIO
from typing import Protocol, cast

from gotpl.compile.instructions import (
    CompiledCommand,
    CompiledPipeline,
    OpCode,
    Operand,
    OperandKind,
    Program,
)
from gotpl.errors import TemplateExecutionError

from .awaitables import is_awaitable
from .callables import (
    CallSpec,
    TemplateCallArityError,
    invoke_prepared_template_function,
    invoke_template_function,
)
from .gofmt import FormatMode
from .policy import ExecutionBudget, ExecutionBudgetState, SandboxPolicy
from .results import unwrap_function_result
from .sync_vm import (
    _MAX_TEMPLATE_DEPTH,  # pyright: ignore[reportPrivateUsage]
    _enter_range_item,  # pyright: ignore[reportPrivateUsage]
    _execution_function_registry,  # pyright: ignore[reportPrivateUsage]
    _ExecutionContext,  # pyright: ignore[reportPrivateUsage]
    _ExecutionLocation,  # pyright: ignore[reportPrivateUsage]
    _invalid_instruction,  # pyright: ignore[reportPrivateUsage]
    _next_range_item,  # pyright: ignore[reportPrivateUsage]
    _number_value,  # pyright: ignore[reportPrivateUsage]
    _range_entries,  # pyright: ignore[reportPrivateUsage]
    _RangeState,  # pyright: ignore[reportPrivateUsage]
    _require_branch,  # pyright: ignore[reportPrivateUsage]
    _require_call,  # pyright: ignore[reportPrivateUsage]
    _require_pipeline,  # pyright: ignore[reportPrivateUsage]
    _require_range,  # pyright: ignore[reportPrivateUsage]
    _require_range_next,  # pyright: ignore[reportPrivateUsage]
    format_value,
)
from .values import INVALID, UNTYPED_NIL, MissingKeyMode, is_bound_method

_UNPREPARED_CALL = object()


class AsyncTextWriter(Protocol):
    """Structural writer accepted by the asynchronous runtime."""

    def write(self, value: str, /) -> int | Awaitable[int]: ...


async def render_program_async(
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
) -> str:
    """Execute a compiled program and return its text asynchronously."""

    output = StringIO()
    await render_program_async_to(
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
    )
    return output.getvalue()


async def render_program_async_to(
    program: Program,
    writer: AsyncTextWriter,
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
) -> None:
    """Execute a compiled program against a sync or async text writer."""

    location = _ExecutionLocation() if _location is None else _location
    try:
        budget_state = (
            ExecutionBudgetState(budget) if budget is not None else _budget_state
        )
        budgeted_writer: AsyncTextWriter = (
            _AsyncBudgetedWriter(writer, budget_state)
            if budget_state is not None
            else writer
        )
        await _render_program_async_to(
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
        )
    except TemplateExecutionError as error:
        error.attach_location(
            location.source,
            location.position,
            source_name=location.source_name,
            template_name=location.template_name,
        )
        raise


async def _render_program_async_to(
    program: Program,
    writer: AsyncTextWriter,
    data: object,
    *,
    functions: Mapping[str, Callable[..., object]] | None,
    missing_key: MissingKeyMode,
    format_mode: FormatMode,
    _namespace: Mapping[str, Program] | None,
    _depth: int,
    _logical_builtins: frozenset[str] | None,
    _location: _ExecutionLocation,
    sandbox: SandboxPolicy | None,
    _budget_state: ExecutionBudgetState | None,
) -> None:
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
    )
    current_program = program
    instructions = current_program.instructions
    pc = 0
    frames: list[tuple[Program, _ExecutionContext, int]] | None = None
    while True:
        if pc >= len(instructions):
            if not frames:
                break
            current_program, context, pc = frames.pop()
            instructions = current_program.instructions
            _location.program = current_program
            _location.position = 0
            continue
        instruction = instructions[pc]
        _location.position = instruction.source_start
        opcode = instruction.opcode
        if opcode is OpCode.WRITE_TEXT:
            if isinstance(instruction.argument, str):
                await _write_text(writer, instruction.argument)
            pc += 1
        elif opcode is OpCode.WRITE_DOT:
            await _write_text(writer, format_value(context.dot, context.format_mode))
            pc += 1
        elif opcode is OpCode.WRITE_PIPELINE:
            value = await _evaluate_pipeline(_require_pipeline(instruction), context)
            await _write_text(writer, format_value(value, context.format_mode))
            pc += 1
        elif opcode is OpCode.EVAL_PIPELINE:
            await _evaluate_pipeline(_require_pipeline(instruction), context)
            pc += 1
        elif opcode is OpCode.PUSH_SCOPE:
            context.push_scope()
            pc += 1
        elif opcode is OpCode.POP_SCOPE:
            context.pop_scope()
            pc += 1
        elif opcode is OpCode.JUMP_IF_FALSE:
            target = _require_branch(instruction)
            value = await _evaluate_pipeline(target.pipeline, context)
            pc = pc + 1 if context.adapter.is_true(value) else target.target
        elif opcode is OpCode.ENTER_WITH:
            target = _require_branch(instruction)
            value = await _evaluate_pipeline(target.pipeline, context)
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
            value = await _evaluate_pipeline(target.pipeline, context, bind=False)
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
                else await _evaluate_pipeline(target.pipeline, context)
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
            current_program = callee
            instructions = current_program.instructions
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
            )
            pc = 0
        else:
            raise TemplateExecutionError(
                f"opcode {opcode.name} is not implemented by the asynchronous runtime"
            )


async def _write_text(writer: AsyncTextWriter, value: str) -> None:
    written = writer.write(value)
    if is_awaitable(written):
        written = await written
    if written != len(value):
        raise OSError(f"short write: wrote {written} of {len(value)} characters")


class _AsyncBudgetedWriter:
    __slots__ = ("state", "writer")

    def __init__(self, writer: AsyncTextWriter, state: ExecutionBudgetState) -> None:
        self.writer = writer
        self.state = state

    def write(self, value: str, /) -> int | Awaitable[int]:
        self.state.consume_output(len(value))
        return self.writer.write(value)


async def _evaluate_pipeline(
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
        value = await _evaluate_command(commands[0], context, piped=INVALID)
    else:
        for index, command in enumerate(commands):
            value = await _evaluate_command(
                command,
                context,
                piped=value if index else INVALID,
            )
    if bind:
        for binding in pipeline.bindings:
            context.set_variable(binding, value, assignment=pipeline.is_assignment)
    return value


async def _evaluate_command(
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
            return await _evaluate_logical(name, command, context, piped=piped)
        function = context.functions.get(name)
        if function is None:
            raise TemplateExecutionError(f"function {name!r} is not defined")
        arguments = [
            await _evaluate_operand(item, context) for item in command.arguments[1:]
        ]
        if piped is not INVALID:
            arguments.append(piped)
        return await _invoke_registered_function(
            name,
            function,
            arguments,
            context.call_specs[name],
            context.budget_state,
        )
    arguments = [await _evaluate_operand(item, context) for item in command.arguments]
    if piped is not INVALID:
        arguments.append(piped)
    first_value = arguments[0]
    if is_bound_method(first_value):
        method_name = getattr(first_value, "__name__", "method")
        return await _invoke_registered_function(
            method_name if isinstance(method_name, str) else "method",
            first_value,
            arguments[1:],
            _UNPREPARED_CALL,
            context.budget_state,
        )
    if len(arguments) != 1:
        raise TemplateExecutionError("non-callable command has arguments")
    return first_value


async def _evaluate_operand(operand: Operand, context: _ExecutionContext) -> object:
    kind = operand.kind
    if kind is OperandKind.DOT:
        value = context.dot
    elif kind is OperandKind.NIL:
        value = UNTYPED_NIL
    elif kind is OperandKind.BOOL:
        value = operand.value is True
    elif kind in {OperandKind.NUMBER, OperandKind.COMPLEX}:
        value = _number_value(operand.value, is_complex=kind is OperandKind.COMPLEX)
    elif kind is OperandKind.STRING:
        value = operand.value
    elif kind is OperandKind.CHARACTER:
        value = ord(operand.value) if isinstance(operand.value, str) else INVALID
    elif kind is OperandKind.FIELD:
        value = await _lookup_chain(context.dot, operand.fields, context)
    elif kind is OperandKind.VARIABLE:
        name = operand.value
        value = context.lookup_variable(name) if isinstance(name, str) else INVALID
        value = await _lookup_chain(value, operand.fields, context)
    elif kind is OperandKind.SUBPIPELINE:
        if operand.pipeline is None:
            return INVALID
        value = await _evaluate_pipeline(operand.pipeline, context)
        value = await _lookup_chain(value, operand.fields, context)
    elif kind is OperandKind.FUNCTION and isinstance(operand.value, str):
        function = context.functions.get(operand.value)
        if function is None:
            raise TemplateExecutionError(f"function {operand.value!r} is not defined")
        value = await _invoke_registered_function(
            operand.value,
            function,
            [],
            context.call_specs[operand.value],
            context.budget_state,
        )
    else:
        raise TemplateExecutionError(f"operand {kind.name} is not directly evaluable")
    return value


async def _lookup_chain(
    value: object,
    fields: tuple[str, ...],
    context: _ExecutionContext,
) -> object:
    for index, field in enumerate(fields):
        value = context.adapter.lookup(value, field)
        if value is INVALID:
            break
        if index < len(fields) - 1 and is_bound_method(value):
            value = await _invoke_registered_function(
                field, value, [], _UNPREPARED_CALL, context.budget_state
            )
    return value


async def _invoke_registered_function(
    name: str,
    function: Callable[..., object],
    arguments: list[object],
    spec: object = _UNPREPARED_CALL,
    budget_state: ExecutionBudgetState | None = None,
) -> object:
    if budget_state is not None:
        budget_state.consume_function_call()
    try:
        value = (
            invoke_template_function(name, function, arguments)
            if spec is _UNPREPARED_CALL
            else invoke_prepared_template_function(
                name,
                function,
                arguments,
                cast(CallSpec | None, spec),
            )
        )
        if is_awaitable(value):
            value = await value
        return unwrap_function_result(value)
    except TemplateCallArityError as error:
        raise TemplateExecutionError(str(error)) from error
    except TemplateExecutionError:
        raise
    except Exception as error:
        raise TemplateExecutionError(f"function {name!r} failed: {error}") from error


async def _evaluate_logical(
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
        value = await _evaluate_operand(operand, context)
        truth = context.adapter.is_true(value)
        if (name == "and" and not truth) or (name == "or" and truth):
            return value
    if piped is not INVALID:
        return piped
    return value
