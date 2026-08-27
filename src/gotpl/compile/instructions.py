"""Immutable execution instructions independent of the parser AST."""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import TypeAlias


class OperandKind(Enum):
    """Kinds of values addressable by a compiled command."""

    DOT = auto()
    NIL = auto()
    BOOL = auto()
    NUMBER = auto()
    COMPLEX = auto()
    STRING = auto()
    CHARACTER = auto()
    FUNCTION = auto()
    FIELD = auto()
    VARIABLE = auto()
    SUBPIPELINE = auto()


@dataclass(frozen=True, slots=True)
class Operand:
    """A compact command operand with pre-split lookup fields."""

    kind: OperandKind
    value: str | bool | None = None
    fields: tuple[str, ...] = ()
    pipeline: "CompiledPipeline | None" = None


@dataclass(frozen=True, slots=True)
class CompiledCommand:
    """A command ready for runtime evaluation."""

    arguments: tuple[Operand, ...]


@dataclass(frozen=True, slots=True)
class CompiledPipeline:
    """A pipeline without parser nodes or repeated name splitting."""

    bindings: tuple[str, ...]
    is_assignment: bool
    commands: tuple[CompiledCommand, ...]
    source_start: int = field(default=0, compare=False)


@dataclass(frozen=True, slots=True)
class BranchTarget:
    """A condition pipeline and its false branch instruction index."""

    pipeline: CompiledPipeline
    target: int


@dataclass(frozen=True, slots=True)
class RangeTarget:
    """A range pipeline and its empty and completed instruction indices."""

    pipeline: CompiledPipeline
    empty_target: int
    exit_target: int


@dataclass(frozen=True, slots=True)
class RangeNextTarget:
    """The body and exit targets for advancing an active range."""

    body_target: int
    exit_target: int


@dataclass(frozen=True, slots=True)
class CallTarget:
    """A named template call and its optional dot pipeline."""

    name: str
    pipeline: CompiledPipeline | None


class OpCode(Enum):
    """Operations understood by the template virtual machines."""

    WRITE_TEXT = auto()
    WRITE_DOT = auto()
    WRITE_PIPELINE = auto()
    EVAL_PIPELINE = auto()
    PUSH_SCOPE = auto()
    POP_SCOPE = auto()
    JUMP_IF_FALSE = auto()
    ENTER_WITH = auto()
    EXIT_WITH = auto()
    ITERATE = auto()
    NEXT_ITERATION = auto()
    BREAK_RANGE = auto()
    JUMP = auto()
    CALL_TEMPLATE = auto()


InstructionArgument: TypeAlias = (
    str
    | int
    | CompiledPipeline
    | BranchTarget
    | RangeTarget
    | RangeNextTarget
    | CallTarget
    | None
)


@dataclass(frozen=True, slots=True)
class Instruction:
    """A single operation with source metadata."""

    opcode: OpCode
    argument: InstructionArgument
    source_start: int


@dataclass(frozen=True, slots=True)
class Program:
    """A reusable immutable instruction stream and template namespace."""

    instructions: tuple[Instruction, ...]
    name: str = ""
    definitions: tuple["Program", ...] = ()
    source: str = field(default="", compare=False)
    source_name: str = field(default="", compare=False)
