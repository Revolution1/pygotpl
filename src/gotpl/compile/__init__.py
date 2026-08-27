"""Internal template compiler primitives; not a stable public API."""

# pyright: reportUnusedImport=false
# ruff: noqa: F401

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

__all__: list[str] = []
