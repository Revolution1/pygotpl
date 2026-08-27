"""Compilation from template syntax to execution instructions."""

from .compiler import compile_template
from .instructions import (
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

__all__ = [
    "BranchTarget",
    "CallTarget",
    "CompiledCommand",
    "CompiledPipeline",
    "Instruction",
    "OpCode",
    "Operand",
    "OperandKind",
    "Program",
    "RangeNextTarget",
    "RangeTarget",
    "compile_template",
]
