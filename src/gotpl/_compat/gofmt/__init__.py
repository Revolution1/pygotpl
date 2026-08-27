"""Private Go-compatible formatting support for gotpl."""

from .go import (
    GoFormatSpec,
    GoFormatter,
    GoFormatValueAdapter,
    GoPointer,
    sprintf,
)

__all__ = [
    "GoFormatSpec",
    "GoFormatValueAdapter",
    "GoFormatter",
    "GoPointer",
    "sprintf",
]
