"""Immutable linked execution metadata derived from generic programs."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

from gotpl.compile import (
    BranchTarget,
    CompiledPipeline,
    Instruction,
    OpCode,
    Operand,
    OperandKind,
    Program,
    RangeTarget,
)

from .callables import CallSpec, PreparedFunctionRegistry
from .context import ContextFunction
from .values import INVALID, UNTYPED_NIL, number_value


@dataclass(frozen=True, slots=True)
class LinkedConstantOperand:
    """A literal decoded once while linking rather than on every render."""

    value: object


@dataclass(frozen=True, slots=True)
class LinkedDotOperand:
    """The current dot without a generic operand-kind dispatch."""


@dataclass(frozen=True, slots=True)
class LinkedFieldOperand:
    """A field chain rooted at the current dot."""

    fields: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class LinkedVariableOperand:
    """A named variable and its optional field chain."""

    name: str
    fields: tuple[str, ...]


LinkedOperand = (
    Operand
    | LinkedConstantOperand
    | LinkedDotOperand
    | LinkedFieldOperand
    | LinkedVariableOperand
)


@dataclass(frozen=True, slots=True)
class LinkedValueCommand:
    """A command whose operands produce a value without a registry lookup."""

    operands: tuple[LinkedOperand, ...]


@dataclass(frozen=True, slots=True)
class LinkedFunctionCommand:
    """A command with its immutable callable and call metadata resolved."""

    name: str
    function: Callable[..., object]
    spec: CallSpec | None
    operands: tuple[LinkedOperand, ...]
    direct: bool


@dataclass(frozen=True, slots=True)
class LinkedUnaryFunction:
    """A prevalidated unary function fed by the preceding pipeline value."""

    name: str
    function: Callable[..., object]


@dataclass(frozen=True, slots=True)
class LinkedFieldPipeline:
    """A direct dot-field lookup followed by prevalidated unary functions."""

    bindings: tuple[str, ...]
    is_assignment: bool
    fields: tuple[str, ...]
    functions: tuple[LinkedUnaryFunction, ...]
    source_start: int


@dataclass(frozen=True, slots=True)
class LinkedVariablePipeline:
    """A direct variable lookup followed by prevalidated unary functions."""

    bindings: tuple[str, ...]
    is_assignment: bool
    name: str
    fields: tuple[str, ...]
    functions: tuple[LinkedUnaryFunction, ...]
    source_start: int


LinkedCommand = LinkedValueCommand | LinkedFunctionCommand


@dataclass(frozen=True, slots=True)
class LinkedPipeline:
    """A write pipeline aligned with one generic instruction."""

    bindings: tuple[str, ...]
    is_assignment: bool
    commands: tuple[LinkedCommand, ...]
    source_start: int


LinkedWritePipeline = LinkedPipeline | LinkedFieldPipeline | LinkedVariablePipeline
LinkedControlPipeline = LinkedFieldPipeline | LinkedVariablePipeline


@dataclass(frozen=True, slots=True)
class LinkedProgram:
    """Sidecar linked metadata that preserves the generic reference program."""

    program: Program
    write_pipelines: tuple[LinkedWritePipeline | None, ...]
    control_pipelines: tuple[LinkedControlPipeline | None, ...] | None
    definitions: tuple[LinkedProgram, ...] = ()
    namespace: Mapping[str, LinkedProgram] = field(
        default_factory=lambda: MappingProxyType({}),
        compare=False,
        repr=False,
    )
    program_namespace: Mapping[str, Program] = field(
        default_factory=lambda: MappingProxyType({}),
        compare=False,
        repr=False,
    )
    linked_write_count: int = 0
    linked_control_count: int = 0
    template_call_count: int = 0


def link_program(
    program: Program,
    functions: PreparedFunctionRegistry,
    *,
    logical_builtins: frozenset[str] = frozenset({"and", "or"}),
) -> LinkedProgram:
    """Resolve safe write-pipeline metadata without changing generic IR."""

    linked: list[LinkedWritePipeline | None] = []
    controls: list[LinkedControlPipeline | None] | None = None
    for index, instruction in enumerate(program.instructions):
        pipeline = instruction.argument
        linked.append(
            _link_pipeline(pipeline, functions, logical_builtins)
            if instruction.opcode is OpCode.WRITE_PIPELINE
            and isinstance(pipeline, CompiledPipeline)
            else None
        )
        if (
            instruction.opcode is OpCode.JUMP_IF_FALSE
            or instruction.opcode is OpCode.ENTER_WITH
            or instruction.opcode is OpCode.ITERATE
        ):
            if controls is None:
                prefix: list[LinkedControlPipeline | None] = [
                    None for _ in range(index)
                ]
                controls = prefix
            controls.append(
                _link_control_pipeline(instruction, functions, logical_builtins)
            )
        elif controls is not None:
            controls.append(None)
    definitions = tuple(
        link_program(
            definition,
            functions,
            logical_builtins=logical_builtins,
        )
        for definition in program.definitions
    )
    linked_namespace: dict[str, LinkedProgram] = {
        definition.program.name: definition for definition in definitions
    }
    program_namespace: dict[str, Program] = {
        name: definition.program for name, definition in linked_namespace.items()
    }
    control_pipelines = (
        None if controls is None or not any(controls) else tuple(controls)
    )
    result = LinkedProgram(
        program,
        tuple(linked),
        control_pipelines,
        definitions,
        MappingProxyType(linked_namespace),
        MappingProxyType(program_namespace),
        sum(item is not None for item in linked)
        + sum(item.linked_write_count for item in definitions),
        (
            0
            if control_pipelines is None
            else sum(item is not None for item in control_pipelines)
        )
        + sum(item.linked_control_count for item in definitions),
        sum(
            instruction.opcode is OpCode.CALL_TEMPLATE
            for instruction in program.instructions
        )
        + sum(item.template_call_count for item in definitions),
    )
    if program.name:
        program_namespace[program.name] = program
    return result


def _link_control_pipeline(
    instruction: Instruction,
    functions: PreparedFunctionRegistry,
    logical_builtins: frozenset[str],
) -> LinkedFieldPipeline | LinkedVariablePipeline | None:
    argument = instruction.argument
    pipeline = (
        argument.pipeline
        if (
            instruction.opcode is OpCode.JUMP_IF_FALSE
            or instruction.opcode is OpCode.ENTER_WITH
        )
        and isinstance(argument, BranchTarget)
        else argument.pipeline
        if instruction.opcode is OpCode.ITERATE and isinstance(argument, RangeTarget)
        else None
    )
    return (
        None
        if pipeline is None
        else _link_lookup_pipeline(pipeline, functions, logical_builtins)
    )


def _link_pipeline(
    pipeline: CompiledPipeline,
    functions: PreparedFunctionRegistry,
    logical_builtins: frozenset[str],
) -> LinkedWritePipeline | None:
    lookup = _link_lookup_pipeline(pipeline, functions, logical_builtins)
    if lookup is not None:
        return lookup
    commands: list[LinkedCommand] = []
    for index, command in enumerate(pipeline.commands):
        if not command.arguments:
            return None
        first = command.arguments[0]
        if first.kind is not OperandKind.FUNCTION:
            commands.append(
                LinkedValueCommand(
                    tuple(_link_operand(item) for item in command.arguments)
                )
            )
            continue
        name = first.value
        if not isinstance(name, str) or name in logical_builtins:
            return None
        function = functions.get(name)
        if function is None:
            return None
        spec = functions.call_specs.get(name)
        argument_count = len(command.arguments) - 1 + (index > 0)
        commands.append(
            LinkedFunctionCommand(
                name,
                function,
                spec,
                tuple(_link_operand(item) for item in command.arguments[1:]),
                not isinstance(function, ContextFunction)
                and (
                    spec is None
                    or (
                        spec.arity_error(name, argument_count) is None
                        and not spec.requires_type_validation
                    )
                ),
            )
        )
    return LinkedPipeline(
        pipeline.bindings,
        pipeline.is_assignment,
        tuple(commands),
        pipeline.source_start,
    )


def _link_lookup_pipeline(
    pipeline: CompiledPipeline,
    functions: PreparedFunctionRegistry,
    logical_builtins: frozenset[str],
) -> LinkedFieldPipeline | LinkedVariablePipeline | None:
    commands = pipeline.commands
    if not commands or len(commands[0].arguments) != 1:
        return None
    operand = commands[0].arguments[0]
    if operand.kind not in {OperandKind.FIELD, OperandKind.VARIABLE}:
        return None
    unary: list[LinkedUnaryFunction] = []
    for command in commands[1:]:
        if not command.arguments:
            return None
        first = command.arguments[0]
        name = first.value
        if (
            first.kind is not OperandKind.FUNCTION
            or not isinstance(name, str)
            or name in logical_builtins
            or len(command.arguments) != 1
        ):
            return None
        function = functions.get(name)
        if function is None:
            return None
        if isinstance(function, ContextFunction):
            return None
        spec = functions.call_specs.get(name)
        if spec is not None and (
            spec.arity_error(name, 1) is not None or spec.requires_type_validation
        ):
            return None
        unary.append(LinkedUnaryFunction(name, function))
    common = (
        pipeline.bindings,
        pipeline.is_assignment,
    )
    if operand.kind is OperandKind.FIELD:
        return LinkedFieldPipeline(
            *common,
            operand.fields,
            tuple(unary),
            pipeline.source_start,
        )
    name = operand.value
    if not isinstance(name, str):
        return None
    return LinkedVariablePipeline(
        *common,
        name,
        operand.fields,
        tuple(unary),
        pipeline.source_start,
    )


def _link_operand(operand: Operand) -> LinkedOperand:
    kind = operand.kind
    if kind is OperandKind.DOT:
        return LinkedDotOperand()
    if kind is OperandKind.NIL:
        return LinkedConstantOperand(UNTYPED_NIL)
    if kind is OperandKind.BOOL:
        return LinkedConstantOperand(operand.value is True)
    if kind is OperandKind.NUMBER or kind is OperandKind.COMPLEX:
        return LinkedConstantOperand(
            number_value(operand.value, is_complex=kind is OperandKind.COMPLEX)
        )
    if kind is OperandKind.STRING:
        return LinkedConstantOperand(operand.value)
    if kind is OperandKind.CHARACTER:
        return LinkedConstantOperand(
            ord(operand.value) if isinstance(operand.value, str) else INVALID
        )
    if kind is OperandKind.FIELD:
        return LinkedFieldOperand(operand.fields)
    if kind is OperandKind.VARIABLE and isinstance(operand.value, str):
        return LinkedVariableOperand(operand.value, operand.fields)
    return operand
