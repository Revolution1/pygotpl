"""Internal template execution primitives; not a stable public API."""

# pyright: reportUnusedImport=false
# ruff: noqa: F401

from .async_vm import AsyncTextWriter, render_program_async, render_program_async_to
from .gofmt import FormatMode, GoFormatSpec, GoFormatter
from .policy import ExecutionBudget, SandboxPolicy
from .results import FunctionResult
from .sync_vm import (
    render_linked_program,
    render_linked_program_to,
    render_program,
    render_program_to,
)
from .values import (
    INVALID,
    UNTYPED_NIL,
    GoPointer,
    GoSeq,
    GoSeq2,
    MissingKeyMode,
    TypedMap,
    ValueAdapter,
)

__all__: list[str] = []
