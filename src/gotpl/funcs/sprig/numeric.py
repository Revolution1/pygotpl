"""Sprig integer conversion, arithmetic, and sequence functions."""

from __future__ import annotations

import math
import re
from decimal import ROUND_HALF_UP, Decimal, localcontext
from fractions import Fraction

from gotpl.runtime.gofmt import sprintf

_INT64_MIN = -(1 << 63)
_INT64_MAX = (1 << 63) - 1
_DECIMAL_DIVISION_QUANTUM = Decimal("1e-16")
# Sprig converts every operand through float64 before decimal arithmetic.  This
# comfortably covers the full finite float64 exponent range while remaining
# below PyPy's integer-to-string safety limit in its pure-Python decimal module.
_DECIMAL_CONTEXT_PRECISION = 1_024
_DECIMAL_DIGITS = r"[0-9](?:_?[0-9])*"
_HEX_DIGITS = r"[0-9a-fA-F](?:_?[0-9a-fA-F])*"
_DECIMAL_FLOAT = re.compile(
    rf"[+-]?(?:{_DECIMAL_DIGITS}(?:\.(?:{_DECIMAL_DIGITS})?)?|"
    rf"\.{_DECIMAL_DIGITS})(?:[eE][+-]?{_DECIMAL_DIGITS})?"
)
_HEX_FLOAT = re.compile(
    rf"[+-]?0[xX]_?(?:{_HEX_DIGITS}(?:\.(?:{_HEX_DIGITS})?)?|"
    rf"\.{_HEX_DIGITS})[pP][+-]?{_DECIMAL_DIGITS}"
)


def to_float64(value: object) -> float:
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, str):
        return _parse_go_float(value)
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError, OverflowError):
        return 0.0


def to_int(value: object) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return _wrap_int64(value)
    if isinstance(value, float):
        if not math.isfinite(value) or value < _INT64_MIN or value >= 1 << 63:
            return _INT64_MIN
        return int(value)
    if isinstance(value, str):
        return _parse_go_int(value)
    return 0


def to_decimal(value: object) -> int:
    return _parse_bounded_int(sprintf("%v", value), 8)


def atoi(value: str) -> int:
    return _parse_bounded_int(value, 10)


def add1(value: object) -> int:
    return _wrap_int64(to_int(value) + 1)


def add(*values: object) -> int:
    result = 0
    for value in values:
        result = _wrap_int64(result + to_int(value))
    return result


def sub(first: object, second: object) -> int:
    return _wrap_int64(to_int(first) - to_int(second))


def div(first: object, second: object) -> int:
    dividend = to_int(first)
    divisor = to_int(second)
    quotient = abs(dividend) // abs(divisor)
    result = -quotient if (dividend < 0) != (divisor < 0) else quotient
    return _wrap_int64(result)


def mod(first: object, second: object) -> int:
    dividend = to_int(first)
    divisor = to_int(second)
    remainder = abs(dividend) % abs(divisor)
    return -remainder if dividend < 0 else remainder


def mul(first: object, *values: object) -> int:
    result = to_int(first)
    for value in values:
        result = _wrap_int64(result * to_int(value))
    return result


def maximum(first: object, *values: object) -> int:
    return max((to_int(first), *(to_int(value) for value in values)))


def minimum(first: object, *values: object) -> int:
    return min((to_int(first), *(to_int(value) for value in values)))


def add1f(value: object) -> float:
    return _decimal_result(_decimal(value) + Decimal(1))


def addf(*values: object) -> float:
    with localcontext() as context:
        context.prec = _DECIMAL_CONTEXT_PRECISION
        result = Decimal(0)
        for value in values:
            result += _decimal(value)
        return _decimal_result(result)


def subf(first: object, *values: object) -> float:
    with localcontext() as context:
        context.prec = _DECIMAL_CONTEXT_PRECISION
        result = _decimal(first)
        for value in values:
            result -= _decimal(value)
        return _decimal_result(result)


def divf(first: object, *values: object) -> float:
    with localcontext() as context:
        context.prec = _DECIMAL_CONTEXT_PRECISION
        result = _decimal(first)
        for value in values:
            divisor = _decimal(value)
            if divisor.is_zero():
                raise ZeroDivisionError("decimal division by 0")
            result = (result / divisor).quantize(
                _DECIMAL_DIVISION_QUANTUM,
                rounding=ROUND_HALF_UP,
            )
        return _decimal_result(result)


def mulf(first: object, *values: object) -> float:
    with localcontext() as context:
        context.prec = _DECIMAL_CONTEXT_PRECISION
        result = _decimal(first)
        for value in values:
            result *= _decimal(value)
        return _decimal_result(result)


def maxf(first: object, *values: object) -> float:
    result = to_float64(first)
    for value in values:
        candidate = to_float64(value)
        result = _float_max(result, candidate)
    return result


def minf(first: object, *values: object) -> float:
    result = to_float64(first)
    for value in values:
        candidate = to_float64(value)
        result = _float_min(result, candidate)
    return result


def ceil(value: object) -> float:
    converted = to_float64(value)
    if not math.isfinite(converted) or converted == 0.0:
        return converted
    return float(math.ceil(converted))


def floor(value: object) -> float:
    converted = to_float64(value)
    if not math.isfinite(converted) or converted == 0.0:
        return converted
    return float(math.floor(converted))


def round_number(
    value: object,
    places: int,
    *round_options: float,
) -> float:
    threshold = round_options[0] if round_options else 0.5
    converted = to_float64(value)
    if not math.isfinite(converted):
        return converted
    try:
        power = math.pow(10, places)
    except OverflowError:
        power = math.inf
    if power == 0.0 or math.isinf(power):
        return math.nan
    digit = power * converted
    exact_digit = Fraction.from_float(power) * Fraction.from_float(converted)
    integer = math.trunc(exact_digit)
    fraction = float(exact_digit - integer)
    rounded = _go_ceil(digit) if fraction >= threshold else _go_floor(digit)
    return rounded / power


def until(count: int) -> list[int]:
    step = -1 if count < 0 else 1
    return until_step(0, count, step)


def until_step(start: int, stop: int, step: int) -> list[int]:
    if (stop < start and step >= 0) or (stop >= start and step <= 0):
        return []
    return list(range(start, stop, step))


def seq(*parameters: int) -> str:
    if len(parameters) == 1:
        start, end = 1, parameters[0]
        step = -1 if end < start else 1
    elif len(parameters) == 2:
        start, end = parameters
        step = -1 if end < start else 1
    elif len(parameters) == 3:
        start, step, end = parameters
        if end < start and step > 0:
            return ""
    else:
        return ""
    inclusive_stop = end + (-1 if end < start else 1)
    return " ".join(str(value) for value in until_step(start, inclusive_stop, step))


def _decimal(value: object) -> Decimal:
    converted = to_float64(value)
    if not math.isfinite(converted):
        if math.isnan(converted):
            label = "NaN"
        else:
            label = ("+" if converted > 0 else "-") + "Inf"
        raise ValueError(f"Cannot create a Decimal from {label}")
    return Decimal(0) if converted == 0.0 else Decimal(str(converted))


def _decimal_result(value: Decimal) -> float:
    return float(value)


def _parse_go_float(value: str) -> float:
    if not value.isascii() or value != value.strip():
        return 0.0
    lowered = value.lower()
    if lowered == "nan":
        return math.nan
    if lowered in {"inf", "+inf", "infinity", "+infinity"}:
        return math.inf
    if lowered in {"-inf", "-infinity"}:
        return -math.inf
    parser = float.fromhex if _HEX_FLOAT.fullmatch(value) else float
    if parser is float and not _DECIMAL_FLOAT.fullmatch(value):
        return 0.0
    try:
        parsed = parser(value.replace("_", ""))
    except (ValueError, OverflowError):
        return 0.0
    return parsed if math.isfinite(parsed) else 0.0


def _wrap_int64(value: int) -> int:
    return (value + (1 << 63)) % (1 << 64) - (1 << 63)


def _parse_go_int(value: str) -> int:
    trimmed = _trim_zero_decimal(value)
    if not _is_go_integer(trimmed):
        return 0
    unsigned = trimmed.lstrip("+-")
    if (
        len(unsigned) > 1
        and unsigned.startswith("0")
        and unsigned[1]
        not in {
            "b",
            "B",
            "o",
            "O",
            "x",
            "X",
        }
    ):
        return _parse_bounded_int(trimmed.replace("_", ""), 8)
    parsed = int(trimmed, 0)
    return parsed if _INT64_MIN <= parsed <= _INT64_MAX else 0


def _parse_bounded_int(
    value: str,
    base: int,
) -> int:
    if not value.isascii() or value != value.strip():
        return 0
    digits = value.lstrip("+-")
    alphabet = "01234567" if base == 8 else "0123456789"
    if not digits or any(character not in alphabet for character in digits):
        return 0
    parsed = int(value, base)
    return parsed if _INT64_MIN <= parsed <= _INT64_MAX else 0


def _trim_zero_decimal(value: str) -> str:
    found_zero = False
    for index in range(len(value), 0, -1):
        character = value[index - 1]
        if character == "." and found_zero:
            return value[: index - 1]
        if character == "0":
            found_zero = True
        else:
            return value
    return value


def _is_go_integer(value: str) -> bool:
    if not value.isascii() or value != value.strip():
        return False
    unsigned = value.lstrip("+-")
    if not unsigned:
        return False
    patterns = (
        r"0[bB]_?[01](?:_?[01])*",
        r"0[oO]_?[0-7](?:_?[0-7])*",
        r"0[xX]_?[0-9a-fA-F](?:_?[0-9a-fA-F])*",
        r"0(?:_?[0-7])*",
        r"[1-9](?:_?[0-9])*",
    )
    return any(re.fullmatch(pattern, unsigned) for pattern in patterns)


def _float_max(left: float, right: float) -> float:
    if math.isnan(left) or math.isnan(right):
        return math.nan
    if left == 0.0 and right == 0.0:
        return -0.0 if _negative(left) and _negative(right) else 0.0
    return max(left, right)


def _float_min(left: float, right: float) -> float:
    if math.isnan(left) or math.isnan(right):
        return math.nan
    if left == 0.0 and right == 0.0:
        return -0.0 if _negative(left) or _negative(right) else 0.0
    return min(left, right)


def _negative(value: float) -> bool:
    return math.copysign(1.0, value) < 0.0


def _go_ceil(value: float) -> float:
    if not math.isfinite(value) or value == 0.0:
        return value
    return float(math.ceil(value))


def _go_floor(value: float) -> float:
    if not math.isfinite(value) or value == 0.0:
        return value
    return float(math.floor(value))
