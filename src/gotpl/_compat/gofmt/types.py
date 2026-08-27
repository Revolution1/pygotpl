"""Public value and protocol types shared by the two formatter surfaces."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, Literal, Protocol, TypeVar

FormatMode = Literal["go", "python"]
FormatValueKind = Literal["default", "syntax", "type"]
_Value = TypeVar("_Value")


@dataclass(frozen=True, slots=True)
class GoFormatSpec:
    """Formatting state supplied to a Go-compatible custom formatter."""

    verb: str
    flags: str
    width: int | None
    precision: int | None


class GoFormatter(Protocol):
    """A Python adaptation of Go's ``fmt.Formatter`` interface."""

    def __go_format__(self, spec: GoFormatSpec) -> str:
        """Return the complete formatted representation for *spec*."""

        ...


class GoFormatValueAdapter(Protocol):
    """Supply formatting for a value owned by an integrating package."""

    def __go_format_value__(
        self,
        kind: FormatValueKind,
        mode: FormatMode,
        *,
        nested: bool,
    ) -> str:
        """Return the value's default, syntax, or type representation."""

        ...


class GoTypedMapping(Protocol):
    """Expose optional Go key and value type names for a Python mapping."""

    def __go_map_type__(self) -> tuple[str, str] | None:
        """Return ``(key_type, value_type)`` or ``None`` when unknown."""

        ...


@dataclass(frozen=True, slots=True)
class GoPointer(Generic[_Value]):
    """Represent a typed Go pointer using stable Python object identity."""

    value: _Value | None
    target_type: str = "interface {}"

    @property
    def address(self) -> int:
        """Return zero for nil or the adapted Python object's identity."""
        return 0 if self.value is None else id(self.value)
