"""Explicit Python adaptation for Go function value/error results."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Self


@dataclass(frozen=True, slots=True)
class FunctionResult:
    """Represent a Go-style function value and optional error without tuples."""

    value: object = None
    error: Exception | None = None

    def __post_init__(self) -> None:
        if self.error is not None and not isinstance(  # pyright: ignore[reportUnnecessaryIsInstance]
            self.error, Exception
        ):
            raise TypeError("FunctionResult error must be an exception or None")

    @classmethod
    def success(cls, value: object = None) -> Self:
        """Create a successful function result."""

        return cls(value)

    @classmethod
    def failure(cls, error: Exception, value: object = None) -> Self:
        """Create a failed function result with an optional partial value."""

        return cls(value, error)


def unwrap_function_result(value: object) -> object:
    """Return an ordinary value or raise an explicit function-result error."""

    if not isinstance(value, FunctionResult):
        return value
    if value.error is not None:
        raise value.error
    return value.value
