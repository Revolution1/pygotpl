"""Go-compatible formatting surface."""

from __future__ import annotations

from ._core import sprintf as _sprintf
from .types import GoFormatSpec, GoFormatter, GoFormatValueAdapter, GoPointer


def sprintf(format_string: object, *values: object) -> str:
    """Format values using Go ``fmt.Sprintf`` directives."""
    return _sprintf(format_string, *values, format_mode="go")


__all__ = [
    "GoFormatSpec",
    "GoFormatValueAdapter",
    "GoFormatter",
    "GoPointer",
    "sprintf",
]
