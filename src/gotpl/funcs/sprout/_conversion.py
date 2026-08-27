"""Strict Sprout value conversion functions."""

from __future__ import annotations

from goduration.go import Duration
from gotime.go import LOCAL, Location, Time

from gotpl._compat.gofmt.go import sprintf
from gotpl.runtime import FunctionResult

from .registry import TemplateFunction

_INT64_MIN = -(1 << 63)
_INT64_MAX = (1 << 63) - 1
_UINT64_MAX = (1 << 64) - 1


def _failure(target: str, value: object, error: Exception) -> FunctionResult:
    return FunctionResult.failure(
        ValueError(f"failed to convert {value!r} to {target}: {error}")
    )


def _to_bool(value: object) -> object:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        normalized = value.strip()
        if normalized in {"1", "t", "T", "true", "TRUE", "True"}:
            return True
        if normalized in {"0", "f", "F", "false", "FALSE", "False"}:
            return False
    return _failure("bool", value, TypeError("invalid syntax"))


def _integer(value: object) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, (bytes, bytearray)):
        value = bytes(value).decode()
    if isinstance(value, str):
        text = value.strip()
        try:
            return int(text, 0)
        except ValueError:
            return int(text, 10)
    raise TypeError(f"unable to cast {type(value).__name__} to int")


def _signed(value: object, target: str) -> object:
    try:
        result = _integer(value)
        if not _INT64_MIN <= result <= _INT64_MAX:
            raise OverflowError("value out of signed 64-bit range")
        return result
    except (OverflowError, TypeError, ValueError) as error:
        return _failure(target, value, error)


def _to_int(value: object) -> object:
    return _signed(value, "int")


def _to_int64(value: object) -> object:
    return _signed(value, "int64")


def _unsigned(value: object, target: str) -> object:
    try:
        result = _integer(value)
        if result < 0:
            result &= _UINT64_MAX
        if result > _UINT64_MAX:
            raise OverflowError("value out of unsigned 64-bit range")
        return result
    except (OverflowError, TypeError, ValueError) as error:
        return _failure(target, value, error)


def _to_uint(value: object) -> object:
    return _unsigned(value, "uint")


def _to_uint64(value: object) -> object:
    return _unsigned(value, "uint64")


def _to_float64(value: object) -> object:
    try:
        if isinstance(value, bool):
            return 1.0 if value else 0.0
        if isinstance(value, (int, float, str, bytes, bytearray)):
            return float(value)
        raise TypeError(f"unable to cast {type(value).__name__} to float64")
    except (OverflowError, TypeError, ValueError) as error:
        return _failure("float64", value, error)


def _to_octal(value: object) -> object:
    try:
        return int(sprintf("%v", value), 8)
    except (TypeError, ValueError) as error:
        return FunctionResult.failure(ValueError(f"failed to parse octal: {error}"))


def _to_string(value: object) -> str:
    if isinstance(value, (bytes, bytearray)):
        return bytes(value).decode(errors="replace")
    if isinstance(value, Exception):
        return str(value)
    return sprintf("%v", value)


def _to_date(layout: str, value: str) -> object:
    try:
        return Time.parse_in_location(layout, value, LOCAL)
    except (TypeError, ValueError) as error:
        return FunctionResult.failure(error)


def _to_local_date(layout: str, timezone: str, value: str) -> object:
    try:
        return Time.parse_in_location(layout, value, Location.load(timezone))
    except (TypeError, ValueError) as error:
        return FunctionResult.failure(error)


def _to_duration(value: object) -> object:
    try:
        if isinstance(value, Duration):
            return value
        if isinstance(value, str):
            return Duration.parse(value)
        return Duration(_integer(value))
    except (OverflowError, TypeError, ValueError) as error:
        return _failure("time.Duration", value, error)


def functions() -> dict[str, TemplateFunction]:
    """Return the complete raw Sprout conversion registry."""

    return {
        "toBool": _to_bool,
        "toInt": _to_int,
        "toInt64": _to_int64,
        "toUint": _to_uint,
        "toUint64": _to_uint64,
        "toFloat64": _to_float64,
        "toOctal": _to_octal,
        "toString": _to_string,
        "toDate": _to_date,
        "toLocalDate": _to_local_date,
        "toDuration": _to_duration,
    }
