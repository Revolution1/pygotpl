"""Python-native duration behavior with a Go-inspired object API."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import timedelta
from decimal import ROUND_HALF_EVEN, Decimal
from typing import TypeAlias, overload

from .go import Duration as GoDuration

Scalar: TypeAlias = int | float | Decimal

_UNIT_NANOSECONDS = {
    "ns": 1,
    "us": 1_000,
    "µs": 1_000,
    "μs": 1_000,
    "ms": 1_000_000,
    "s": 1_000_000_000,
    "m": 60_000_000_000,
    "h": 3_600_000_000_000,
}
_PART = re.compile(r"(?P<amount>(?:\d+(?:\.\d*)?|\.\d+))(?P<unit>ns|us|µs|μs|ms|s|m|h)")


def _numeric_decimal(value: Scalar) -> Decimal:
    if isinstance(value, bool) or not isinstance(  # pyright: ignore[reportUnnecessaryIsInstance]
        value, (int, float, Decimal)
    ):
        raise TypeError("duration value must be an int, float, or Decimal")
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("duration value must be finite")
        return Decimal.from_float(value)
    converted = Decimal(value)
    if not converted.is_finite():
        raise ValueError("duration value must be finite")
    return converted


def _round_decimal(value: Decimal) -> int:
    return int(value.to_integral_value(rounding=ROUND_HALF_EVEN))


def _scaled_nanoseconds(value: Scalar, unit: int) -> int:
    if isinstance(value, int) and not isinstance(value, bool):
        return value * unit
    return _round_decimal(_numeric_decimal(value) * unit)


def _timedelta_nanoseconds(value: timedelta) -> int:
    return (
        value.days * 86_400_000_000_000
        + value.seconds * 1_000_000_000
        + value.microseconds * 1_000
    )


def _decimal_unit(value: int, unit: int, precision: int) -> str:
    whole, fraction = divmod(value, unit)
    if fraction == 0:
        return str(whole)
    digits = f"{fraction:0{precision}d}".rstrip("0")
    return f"{whole}.{digits}"


def _truncating_quotient(dividend: int, divisor: int) -> int:
    quotient = abs(dividend) // abs(divisor)
    return -quotient if (dividend < 0) != (divisor < 0) else quotient


@dataclass(frozen=True, slots=True, order=True)
class Duration:
    """An immutable, arbitrary-precision duration measured in nanoseconds."""

    nanoseconds: int = 0

    def __post_init__(self) -> None:
        if isinstance(self.nanoseconds, bool) or not isinstance(  # pyright: ignore[reportUnnecessaryIsInstance]
            self.nanoseconds, int
        ):
            raise TypeError("duration nanoseconds must be an integer")

    @classmethod
    def parse(cls, value: str) -> Duration:
        """Parse Go-inspired duration text with exact decimal arithmetic."""

        if not isinstance(  # pyright: ignore[reportUnnecessaryIsInstance]
            value, str
        ):
            raise TypeError("duration text must be a string")
        original = value
        negative = value.startswith("-")
        if value[:1] in {"+", "-"}:
            value = value[1:]
        if value == "0":
            return cls()
        if not value:
            raise ValueError(f"invalid duration: {original!r}")

        position = 0
        total = Decimal()
        for matched in _PART.finditer(value):
            if matched.start() != position:
                raise ValueError(f"invalid duration: {original!r}")
            total += (
                Decimal(matched.group("amount"))
                * _UNIT_NANOSECONDS[matched.group("unit")]
            )
            position = matched.end()
        if position != len(value) or position == 0:
            raise ValueError(f"invalid duration: {original!r}")
        return cls(_round_decimal(-total if negative else total))

    @classmethod
    def from_nanoseconds(cls, value: Scalar) -> Duration:
        return cls(_scaled_nanoseconds(value, 1))

    @classmethod
    def from_microseconds(cls, value: Scalar) -> Duration:
        return cls(_scaled_nanoseconds(value, 1_000))

    @classmethod
    def from_milliseconds(cls, value: Scalar) -> Duration:
        return cls(_scaled_nanoseconds(value, 1_000_000))

    @classmethod
    def from_seconds(cls, value: Scalar) -> Duration:
        return cls(_scaled_nanoseconds(value, 1_000_000_000))

    @classmethod
    def from_minutes(cls, value: Scalar) -> Duration:
        return cls(_scaled_nanoseconds(value, 60_000_000_000))

    @classmethod
    def from_hours(cls, value: Scalar) -> Duration:
        return cls(_scaled_nanoseconds(value, 3_600_000_000_000))

    @classmethod
    def from_days(cls, value: Scalar) -> Duration:
        return cls(_scaled_nanoseconds(value, 86_400_000_000_000))

    @classmethod
    def from_weeks(cls, value: Scalar) -> Duration:
        return cls(_scaled_nanoseconds(value, 604_800_000_000_000))

    @classmethod
    def from_timedelta(cls, value: timedelta) -> Duration:
        if not isinstance(  # pyright: ignore[reportUnnecessaryIsInstance]
            value, timedelta
        ):
            raise TypeError("value must be datetime.timedelta")
        return cls(_timedelta_nanoseconds(value))

    @classmethod
    def from_go(cls, value: GoDuration) -> Duration:
        if not isinstance(  # pyright: ignore[reportUnnecessaryIsInstance]
            value, GoDuration
        ):
            raise TypeError("value must be goduration.go.Duration")
        return cls(value.nanoseconds)

    def to_go(self) -> GoDuration:
        """Convert to the checked signed-64-bit Go surface."""

        return GoDuration(self.nanoseconds)

    def to_timedelta(self) -> timedelta:
        """Convert with Python's round-half-even microsecond precision."""

        microseconds = _round_decimal(Decimal(self.nanoseconds) / 1_000)
        return timedelta(microseconds=microseconds)

    def __str__(self) -> str:
        if self.nanoseconds == 0:
            return "0s"
        sign = "-" if self.nanoseconds < 0 else ""
        value = abs(self.nanoseconds)
        if value < 1_000_000_000:
            if value < 1_000:
                return f"{sign}{value}ns"
            if value < 1_000_000:
                return f"{sign}{_decimal_unit(value, 1_000, 3)}µs"
            return f"{sign}{_decimal_unit(value, 1_000_000, 6)}ms"
        seconds, fraction = divmod(value, 1_000_000_000)
        minutes, second = divmod(seconds, 60)
        hours, minute = divmod(minutes, 60)
        prefix = f"{hours}h{minute}m" if hours else (f"{minute}m" if minute else "")
        second_text = str(second)
        if fraction:
            second_text += f".{fraction:09d}".rstrip("0")
        return f"{sign}{prefix}{second_text}s"

    def __add__(self, other: object) -> Duration:
        if isinstance(other, Duration):
            return Duration(self.nanoseconds + other.nanoseconds)
        if isinstance(other, timedelta):
            return Duration(self.nanoseconds + _timedelta_nanoseconds(other))
        return NotImplemented

    def __radd__(self, other: object) -> Duration:
        if other == 0:
            return self
        return self.__add__(other)

    def __sub__(self, other: object) -> Duration:
        if isinstance(other, Duration):
            return Duration(self.nanoseconds - other.nanoseconds)
        if isinstance(other, timedelta):
            return Duration(self.nanoseconds - _timedelta_nanoseconds(other))
        return NotImplemented

    def __rsub__(self, other: object) -> Duration:
        if isinstance(other, timedelta):
            return Duration(_timedelta_nanoseconds(other) - self.nanoseconds)
        return NotImplemented

    def __neg__(self) -> Duration:
        return Duration(-self.nanoseconds)

    def __abs__(self) -> Duration:
        return self if self.nanoseconds >= 0 else -self

    def __mul__(self, other: object) -> Duration:
        if isinstance(other, bool) or not isinstance(other, (int, float, Decimal)):
            raise TypeError("duration multiplier must be an int, float, or Decimal")
        return Duration(_scaled_nanoseconds(other, self.nanoseconds))

    def __rmul__(self, other: object) -> Duration:
        return self.__mul__(other)

    @overload
    def __truediv__(self, other: Duration) -> float: ...

    @overload
    def __truediv__(self, other: Scalar) -> Duration: ...

    def __truediv__(self, other: object) -> Duration | float:
        if isinstance(other, Duration):
            if other.nanoseconds == 0:
                raise ZeroDivisionError("duration division by zero")
            return self.nanoseconds / other.nanoseconds
        if isinstance(other, bool) or not isinstance(other, (int, float, Decimal)):
            return NotImplemented
        divisor = _numeric_decimal(other)
        if divisor == 0:
            raise ZeroDivisionError("duration division by zero")
        return Duration(_round_decimal(Decimal(self.nanoseconds) / divisor))

    @overload
    def __floordiv__(self, other: Duration | timedelta) -> int: ...

    @overload
    def __floordiv__(self, other: int) -> Duration: ...

    def __floordiv__(self, other: object) -> Duration | int:
        if isinstance(other, Duration):
            divisor = other.nanoseconds
            if divisor == 0:
                raise ZeroDivisionError("duration floor division by zero")
            return self.nanoseconds // divisor
        if isinstance(other, timedelta):
            divisor = _timedelta_nanoseconds(other)
            if divisor == 0:
                raise ZeroDivisionError("duration floor division by zero")
            return self.nanoseconds // divisor
        if isinstance(other, int) and not isinstance(other, bool):
            if other == 0:
                raise ZeroDivisionError("duration floor division by zero")
            return Duration(self.nanoseconds // other)
        return NotImplemented

    def __mod__(self, other: object) -> Duration:
        if isinstance(other, Duration):
            divisor = other.nanoseconds
        elif isinstance(other, timedelta):
            divisor = _timedelta_nanoseconds(other)
        else:
            return NotImplemented
        if divisor == 0:
            raise ZeroDivisionError("duration modulo by zero")
        return Duration(self.nanoseconds % divisor)

    def __divmod__(self, other: object) -> tuple[int, Duration]:
        if isinstance(other, Duration):
            divisor = other.nanoseconds
        elif isinstance(other, timedelta):
            divisor = _timedelta_nanoseconds(other)
        else:
            return NotImplemented
        if divisor == 0:
            raise ZeroDivisionError("duration divmod by zero")
        quotient, remainder = divmod(self.nanoseconds, divisor)
        return quotient, Duration(remainder)

    def __bool__(self) -> bool:
        return self.nanoseconds != 0

    def __int__(self) -> int:
        return self.nanoseconds

    def __index__(self) -> int:
        return self.nanoseconds

    def round(self, multiple: Duration) -> Duration:
        """Round to a multiple using Python's ties-to-even convention."""

        if not isinstance(  # pyright: ignore[reportUnnecessaryIsInstance]
            multiple, Duration
        ):
            raise TypeError("rounding multiple must be a Duration")
        quantum = multiple.nanoseconds
        if quantum <= 0:
            return self
        magnitude = abs(self.nanoseconds)
        quotient, remainder = divmod(magnitude, quantum)
        if remainder * 2 > quantum or (remainder * 2 == quantum and quotient % 2):
            quotient += 1
        result = quotient * quantum
        return Duration(-result if self.nanoseconds < 0 else result)

    def truncate(self, multiple: Duration) -> Duration:
        """Truncate toward zero to a duration multiple."""

        if not isinstance(  # pyright: ignore[reportUnnecessaryIsInstance]
            multiple, Duration
        ):
            raise TypeError("truncation multiple must be a Duration")
        if multiple.nanoseconds <= 0:
            return self
        return Duration(
            _truncating_quotient(self.nanoseconds, multiple.nanoseconds)
            * multiple.nanoseconds
        )

    def total_nanoseconds(self) -> int:
        return self.nanoseconds

    def total_microseconds(self) -> float:
        return self.nanoseconds / 1_000

    def total_milliseconds(self) -> float:
        return self.nanoseconds / 1_000_000

    def total_seconds(self) -> float:
        return self.nanoseconds / 1_000_000_000

    def total_minutes(self) -> float:
        return self.nanoseconds / 60_000_000_000

    def total_hours(self) -> float:
        return self.nanoseconds / 3_600_000_000_000

    def total_days(self) -> float:
        return self.nanoseconds / 86_400_000_000_000

    def total_weeks(self) -> float:
        return self.nanoseconds / 604_800_000_000_000


NANOSECOND = Duration(1)
MICROSECOND = Duration(1_000)
MILLISECOND = Duration(1_000_000)
SECOND = Duration(1_000_000_000)
MINUTE = Duration(60_000_000_000)
HOUR = Duration(3_600_000_000_000)
DAY = Duration(86_400_000_000_000)
WEEK = Duration(604_800_000_000_000)

__all__ = [
    "DAY",
    "HOUR",
    "MICROSECOND",
    "MILLISECOND",
    "MINUTE",
    "NANOSECOND",
    "SECOND",
    "WEEK",
    "Duration",
]
