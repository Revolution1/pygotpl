"""Immutable Go-compatible duration values."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from json import dumps as json_dumps
from typing import TypeAlias, overload

MIN_NANOSECONDS = -(1 << 63)
MAX_NANOSECONDS = (1 << 63) - 1

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
_NUMBER = re.compile(r"(?:\d+(?:\.\d*)?|\.\d+)")
_PART = re.compile(r"(?P<amount>(?:\d+(?:\.\d*)?|\.\d+))(?P<unit>[^.\d]+)")
Scalar: TypeAlias = int | float | Decimal


class DurationParseError(ValueError):
    """Report a Go-compatible duration parsing failure."""

    def __init__(self, message: str, value: str) -> None:
        self.message = message
        self.value = value
        super().__init__(f"time: {message} {_go_quote(value)}")


def _go_quote(value: str) -> str:
    return json_dumps(value, ensure_ascii=False)


def _checked_nanoseconds(value: int) -> int:
    if isinstance(value, bool) or not isinstance(  # pyright: ignore[reportUnnecessaryIsInstance]
        value, int
    ):
        raise TypeError("duration nanoseconds must be an integer")
    if not MIN_NANOSECONDS <= value <= MAX_NANOSECONDS:
        raise OverflowError("duration exceeds signed 64-bit nanosecond range")
    return value


def _wrapped_nanoseconds(value: int) -> int:
    return (value - MIN_NANOSECONDS) % (1 << 64) + MIN_NANOSECONDS


def _scalar_decimal(value: Scalar) -> Decimal:
    if isinstance(value, bool) or not isinstance(  # pyright: ignore[reportUnnecessaryIsInstance]
        value, (int, float, Decimal)
    ):
        raise TypeError("duration scalar must be an int, float, or Decimal")
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("duration scalar must be finite")
    converted = value if isinstance(value, Decimal) else Decimal(str(value))
    if not converted.is_finite():
        raise ValueError("duration scalar must be finite")
    return converted


def _scaled_nanoseconds(value: Scalar, unit: int) -> int:
    return _checked_nanoseconds(int(_scalar_decimal(value) * unit))


def _truncating_quotient(dividend: int, divisor: int) -> int:
    quotient = abs(dividend) // abs(divisor)
    return -quotient if (dividend < 0) != (divisor < 0) else quotient


def _decimal_unit(value: int, unit: int, precision: int) -> str:
    whole, fraction = divmod(value, unit)
    if fraction == 0:
        return str(whole)
    digits = f"{fraction:0{precision}d}".rstrip("0")
    return f"{whole}.{digits}"


def _go_part_nanoseconds(amount: str, unit: int) -> int:
    whole_text, separator, fraction_text = amount.partition(".")
    whole = int(whole_text or "0")
    if whole > (1 << 63) // unit:
        raise OverflowError
    value = whole * unit
    if not separator or not fraction_text:
        return value

    precision = min(len(fraction_text), 19)
    fraction = int(fraction_text[:precision])
    if fraction > 1 << 63:
        precision = 18
        fraction = int(fraction_text[:precision])
    scale = 10.0**precision
    if fraction:
        # Go intentionally uses float64 here to retain nanosecond accuracy for
        # fractions of hours. Python's float has the same IEEE-754 precision.
        value += int(float(fraction) * (float(unit) / scale))
    return value


@dataclass(frozen=True, slots=True, order=True)
class Duration:
    """A signed 64-bit count of nanoseconds with Python-friendly operations."""

    nanoseconds: int = 0

    def __post_init__(self) -> None:
        _checked_nanoseconds(self.nanoseconds)

    @classmethod
    def parse(cls, value: str) -> Duration:
        """Parse Go ``time.ParseDuration`` syntax."""

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
            raise DurationParseError("invalid duration", original)
        total = 0
        position = 0
        while position < len(value):
            part = _PART.match(value, position)
            if part is None:
                if _NUMBER.match(value, position) is not None:
                    raise DurationParseError("missing unit in duration", original)
                raise DurationParseError("invalid duration", original)
            amount = part.group("amount")
            unit_text = part.group("unit")
            if unit_text not in _UNIT_NANOSECONDS:
                raise DurationParseError(
                    f"unknown unit {_go_quote(unit_text)} in duration",
                    original,
                )
            unit_nanoseconds = _UNIT_NANOSECONDS[unit_text]
            try:
                total += (
                    _go_part_nanoseconds(amount, unit_nanoseconds)
                    if "." in amount
                    else int(amount) * unit_nanoseconds
                )
            except OverflowError as error:
                raise DurationParseError("invalid duration", original) from error
            if total > 1 << 63:
                raise DurationParseError("invalid duration", original)
            position = part.end()
        if not negative and total == 1 << 63:
            raise DurationParseError("invalid duration", original)
        return cls(-total if negative else total)

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
    def from_timedelta(cls, value: timedelta) -> Duration:
        if not isinstance(  # pyright: ignore[reportUnnecessaryIsInstance]
            value, timedelta
        ):
            raise TypeError("value must be datetime.timedelta")
        return cls(
            value.days * 86_400_000_000_000
            + value.seconds * 1_000_000_000
            + value.microseconds * 1_000
        )

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
        if not isinstance(other, Duration):
            return NotImplemented
        return Duration(_wrapped_nanoseconds(self.nanoseconds + other.nanoseconds))

    def __sub__(self, other: object) -> Duration:
        if not isinstance(other, Duration):
            return NotImplemented
        return Duration(_wrapped_nanoseconds(self.nanoseconds - other.nanoseconds))

    def __neg__(self) -> Duration:
        return Duration(_wrapped_nanoseconds(-self.nanoseconds))

    def __abs__(self) -> Duration:
        if self.nanoseconds == MIN_NANOSECONDS:
            return MAX_DURATION
        return self if self.nanoseconds >= 0 else -self

    def __mul__(self, other: object) -> Duration:
        if isinstance(other, Duration):
            multiplier = other.nanoseconds
        elif isinstance(  # pyright: ignore[reportUnnecessaryIsInstance]
            other, int
        ) and not isinstance(other, bool):
            multiplier = other
        else:
            raise TypeError("duration multiplier must be an integer or Duration")
        return Duration(_wrapped_nanoseconds(self.nanoseconds * multiplier))

    def __rmul__(self, other: object) -> Duration:
        return self.__mul__(other)

    @overload
    def __truediv__(self, other: Duration) -> Duration: ...

    @overload
    def __truediv__(self, other: int) -> Duration: ...

    def __truediv__(self, other: Duration | int) -> Duration:
        if isinstance(other, Duration):
            divisor = other.nanoseconds
        elif isinstance(  # pyright: ignore[reportUnnecessaryIsInstance]
            other, int
        ) and not isinstance(other, bool):
            divisor = other
        else:
            raise TypeError("duration divisor must be an integer or Duration")
        if divisor == 0:
            raise ZeroDivisionError("duration division by zero")
        return Duration(
            _wrapped_nanoseconds(_truncating_quotient(self.nanoseconds, divisor))
        )

    def __floordiv__(self, other: Duration | int) -> Duration:
        if isinstance(other, Duration):
            divisor = other.nanoseconds
        elif isinstance(  # pyright: ignore[reportUnnecessaryIsInstance]
            other, int
        ) and not isinstance(other, bool):
            divisor = other
        else:
            raise TypeError("duration divisor must be an integer or Duration")
        if divisor == 0:
            raise ZeroDivisionError("duration division by zero")
        return Duration(
            _wrapped_nanoseconds(_truncating_quotient(self.nanoseconds, divisor))
        )

    def __mod__(self, other: Duration | int) -> Duration:
        if isinstance(other, Duration):
            divisor = other.nanoseconds
        elif isinstance(  # pyright: ignore[reportUnnecessaryIsInstance]
            other, int
        ) and not isinstance(other, bool):
            divisor = other
        else:
            raise TypeError("duration divisor must be an integer or Duration")
        if divisor == 0:
            raise ZeroDivisionError("duration modulo by zero")
        quotient = _truncating_quotient(self.nanoseconds, divisor)
        return Duration(self.nanoseconds - quotient * divisor)

    def __divmod__(self, other: Duration | int) -> tuple[Duration, Duration]:
        return self.__truediv__(other), self.__mod__(other)

    def __int__(self) -> int:
        return self.nanoseconds

    def __index__(self) -> int:
        return self.nanoseconds

    def __and__(self, other: object) -> Duration:
        if not isinstance(other, Duration):
            return NotImplemented
        return Duration(self.nanoseconds & other.nanoseconds)

    def __or__(self, other: object) -> Duration:
        if not isinstance(other, Duration):
            return NotImplemented
        return Duration(self.nanoseconds | other.nanoseconds)

    def __xor__(self, other: object) -> Duration:
        if not isinstance(other, Duration):
            return NotImplemented
        return Duration(self.nanoseconds ^ other.nanoseconds)

    def __invert__(self) -> Duration:
        return Duration(~self.nanoseconds)

    def __lshift__(self, other: object) -> Duration:
        if isinstance(other, bool) or not isinstance(other, int):
            return NotImplemented
        if other < 0:
            raise ValueError("negative shift count")
        return Duration(_wrapped_nanoseconds(self.nanoseconds << other))

    def __rshift__(self, other: object) -> Duration:
        if isinstance(other, bool) or not isinstance(other, int):
            return NotImplemented
        if other < 0:
            raise ValueError("negative shift count")
        return Duration(self.nanoseconds >> other)

    def round(self, multiple: Duration) -> Duration:
        """Round to the nearest multiple, with ties away from zero."""

        if not isinstance(  # pyright: ignore[reportUnnecessaryIsInstance]
            multiple, Duration
        ):
            raise TypeError("rounding multiple must be a Duration")
        quantum = multiple.nanoseconds
        if quantum <= 0:
            return self
        quotient = _truncating_quotient(self.nanoseconds, quantum)
        remainder = self.nanoseconds - quotient * quantum
        magnitude = abs(remainder)
        if magnitude * 2 < quantum:
            result = self.nanoseconds - remainder
        else:
            result = self.nanoseconds + (
                quantum - magnitude if self.nanoseconds >= 0 else -quantum + magnitude
            )
        return Duration(max(MIN_NANOSECONDS, min(MAX_NANOSECONDS, result)))

    def truncate(self, multiple: Duration) -> Duration:
        """Round toward zero to a multiple."""

        if not isinstance(  # pyright: ignore[reportUnnecessaryIsInstance]
            multiple, Duration
        ):
            raise TypeError("truncation multiple must be a Duration")
        quantum = multiple.nanoseconds
        if quantum <= 0:
            return self
        quotient = _truncating_quotient(self.nanoseconds, quantum)
        return Duration(quotient * quantum)

    def total_nanoseconds(self) -> int:
        return self.nanoseconds

    def total_microseconds(self) -> int:
        return _truncating_quotient(self.nanoseconds, 1_000)

    def total_milliseconds(self) -> int:
        return _truncating_quotient(self.nanoseconds, 1_000_000)

    def total_seconds(self) -> float:
        return self.nanoseconds / 1_000_000_000

    def total_minutes(self) -> float:
        return self.nanoseconds / 60_000_000_000

    def total_hours(self) -> float:
        return self.nanoseconds / 3_600_000_000_000

    def to_timedelta(self, *, allow_precision_loss: bool = False) -> timedelta:
        remainder = abs(self.nanoseconds) % 1_000
        if remainder and not allow_precision_loss:
            raise ValueError("conversion would lose nanosecond precision")
        microseconds = _truncating_quotient(self.nanoseconds, 1_000)
        return timedelta(microseconds=microseconds)


NANOSECOND = Duration(1)
MICROSECOND = Duration(1_000)
MILLISECOND = Duration(1_000_000)
SECOND = Duration(1_000_000_000)
MINUTE = Duration(60_000_000_000)
HOUR = Duration(3_600_000_000_000)
MIN_DURATION = Duration(MIN_NANOSECONDS)
MAX_DURATION = Duration(MAX_NANOSECONDS)
