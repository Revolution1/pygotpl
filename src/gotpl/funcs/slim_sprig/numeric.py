"""Numeric behavior retained by the Slim-Sprig v3.0.0 fork."""

from __future__ import annotations

import math

_INT64_MIN = -(1 << 63)
_INT64_MAX = (1 << 63) - 1


def to_int(value: object) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        if value > _INT64_MAX:
            return _INT64_MAX
        if value < _INT64_MIN:
            return _INT64_MIN
        return value
    if isinstance(value, float):
        if not math.isfinite(value) or value < _INT64_MIN or value >= 1 << 63:
            return _INT64_MIN
        return int(value)
    if isinstance(value, str):
        try:
            parsed = int(value, 10)
        except ValueError:
            return 0
        return parsed if _INT64_MIN <= parsed <= _INT64_MAX else 0
    return 0


def add1(value: object) -> int:
    return _wrap(to_int(value) + 1)


def add(*values: object) -> int:
    result = 0
    for value in values:
        result = _wrap(result + to_int(value))
    return result


def sub(first: object, second: object) -> int:
    return _wrap(to_int(first) - to_int(second))


def div(first: object, second: object) -> int:
    dividend = to_int(first)
    divisor = to_int(second)
    quotient = abs(dividend) // abs(divisor)
    return _wrap(-quotient if (dividend < 0) != (divisor < 0) else quotient)


def mod(first: object, second: object) -> int:
    dividend = to_int(first)
    divisor = to_int(second)
    return dividend - div(dividend, divisor) * divisor


def mul(first: object, *values: object) -> int:
    result = to_int(first)
    for value in values:
        result = _wrap(result * to_int(value))
    return result


def maximum(first: object, *values: object) -> int:
    return max((to_int(first), *(to_int(value) for value in values)))


def minimum(first: object, *values: object) -> int:
    return min((to_int(first), *(to_int(value) for value in values)))


def _wrap(value: int) -> int:
    return (value + (1 << 63)) % (1 << 64) - (1 << 63)
