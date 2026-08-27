"""Python-native formatting surface with a Go-shaped API."""

from __future__ import annotations

from ._core import sprintf as _sprintf


def sprintf(format_string: object, *values: object) -> str:
    """Apply Go directive syntax with Python value rendering conventions."""
    return _sprintf(format_string, *values, format_mode="python")


__all__ = ["sprintf"]
