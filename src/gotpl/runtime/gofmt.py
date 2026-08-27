"""Template-facing adapters for the private formatting compatibility layer."""

from __future__ import annotations

from typing import Literal, TypeAlias

from gotpl._compat.gofmt import GoFormatSpec, GoFormatter
from gotpl._compat.gofmt.go import sprintf as go_sprintf
from gotpl._compat.gofmt.python import sprintf as python_sprintf
from gotpl._compat.gofmt.types import FormatValueKind

FormatMode: TypeAlias = Literal["go", "python"]


class _TemplateNone:
    __slots__ = ()

    def __go_format_value__(
        self,
        kind: FormatValueKind,
        mode: FormatMode,
        *,
        nested: bool,
    ) -> str:
        del nested
        if kind == "type":
            return "NoneType" if mode == "python" else "<nil>"
        return "<no value>"


_TEMPLATE_NONE = _TemplateNone()


def sprintf(
    format_string: object,
    *values: object,
    format_mode: FormatMode = "go",
) -> str:
    """Format template values using the explicitly selected semantic surface."""
    adapted_values = values
    for value in values:
        if value is None:
            adapted_values = tuple(
                _TEMPLATE_NONE if item is None else item for item in values
            )
            break
    if format_mode == "python":
        return python_sprintf(format_string, *adapted_values)
    return go_sprintf(format_string, *adapted_values)


__all__ = ["FormatMode", "GoFormatSpec", "GoFormatter", "sprintf"]
