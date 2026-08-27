"""Sprout numeric operations with first-operand type preservation."""

from __future__ import annotations

import math
from collections.abc import Callable

from gotpl.runtime import FunctionResult

from .registry import TemplateFunction

_Operation = Callable[[float, float], float]


def _float(value: object) -> float:
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, (bytes, bytearray)):
        value = bytes(value).decode()
    if isinstance(value, str):
        return float(value.strip())
    raise TypeError(f"unable to cast {type(value).__name__} to float64")


def _int(value: object) -> int:
    return int(_float(value))


def _conversion_failure(target: str, value: object, error: Exception) -> FunctionResult:
    return FunctionResult.failure(
        ValueError(f"failed to convert {value!r} to {target}: {error}")
    )


def _clean(value: float) -> float:
    if value == 0 or not math.isfinite(value):
        return value
    magnitude = math.floor(math.log10(abs(value)))
    scale = 10.0 ** (14 - magnitude)
    scaled = value * scale
    rounded = math.floor(scaled + 0.5) if scaled >= 0 else math.ceil(scaled - 0.5)
    return rounded / scale


def _restore_type(value: float, prototype: object) -> object:
    if isinstance(prototype, bool):
        return bool(value)
    if isinstance(prototype, int):
        return int(value)
    if isinstance(prototype, float):
        return value
    raise TypeError(f"cannot convert numeric result to {type(prototype).__name__}")


def _operate(
    values: tuple[object, ...], operation: _Operation, initial: object
) -> object:
    if not values:
        return initial
    try:
        result = _float(values[0])
        for value in values[1:]:
            result = operation(result, _float(value))
        return _restore_type(_clean(result), values[0])
    except (OverflowError, TypeError, ValueError) as error:
        return _conversion_failure("float64", values[0], error)


def _floor(value: object) -> object:
    try:
        return float(math.floor(_float(value)))
    except (OverflowError, TypeError, ValueError) as error:
        return _conversion_failure("float64", value, error)


def _ceil(value: object) -> object:
    try:
        return float(math.ceil(_float(value)))
    except (OverflowError, TypeError, ValueError) as error:
        return _conversion_failure("float64", value, error)


def _round(value: object, power: int, *options: float) -> object:
    threshold = options[0] if options else 0.5
    try:
        scale = 10.0**power
        digit = _float(value) * scale
        fraction, _ = math.modf(digit)
        rounded = math.ceil(digit) if fraction >= threshold else math.floor(digit)
        return rounded / scale
    except (OverflowError, TypeError, ValueError) as error:
        return _conversion_failure("float64", value, error)


def _add(*values: object) -> object:
    return _operate(values, lambda left, right: left + right, 0.0)


def _add1(value: object) -> object:
    one: object = 1.0 if isinstance(value, float) else 1
    return _add(value, one)


def _sub(*values: object) -> object:
    return _operate(values, lambda left, right: left - right, 0.0)


def _mul(*values: object) -> object:
    result = _operate(values, lambda left, right: left * right, 1)
    if isinstance(result, FunctionResult):
        return result
    return _int(result)


def _mulf(*values: object) -> object:
    return _operate(values, lambda left, right: left * right, 1.0)


def _divf(*values: object) -> object:
    if not values:
        return 0.0
    try:
        result = _float(values[0])
        for value in values[1:]:
            divisor = _float(value)
            if divisor == 0:
                if result == 0:
                    result = math.nan
                else:
                    result = math.copysign(math.inf, result * divisor)
            else:
                result /= divisor
        return _clean(result)
    except (OverflowError, TypeError, ValueError) as error:
        return _conversion_failure("float64", values[0], error)


def _div(*values: object) -> object:
    try:
        if any(_float(value) == 0 for value in values[1:]):
            return FunctionResult.failure(ValueError("cannot divide by zero"))
    except (TypeError, ValueError) as error:
        return _conversion_failure("float64", values[0], error)
    result = _divf(*values)
    if isinstance(result, FunctionResult):
        return result
    return _int(result)


def _mod(value: object, divisor: object) -> object:
    try:
        result = math.fmod(_float(value), _float(divisor))
        return _restore_type(result, value)
    except (OverflowError, TypeError, ValueError) as error:
        return _conversion_failure("float64", value, error)


def _minimum(value: object, *values: object) -> object:
    try:
        return min(_int(item) for item in (value, *values))
    except (OverflowError, TypeError, ValueError) as error:
        return _conversion_failure("int64", value, error)


def _minimum_float(value: object, *values: object) -> object:
    try:
        return min(_float(item) for item in (value, *values))
    except (OverflowError, TypeError, ValueError) as error:
        return _conversion_failure("float64", value, error)


def _maximum(value: object, *values: object) -> object:
    try:
        return max(_int(item) for item in (value, *values))
    except (OverflowError, TypeError, ValueError) as error:
        return _conversion_failure("int64", value, error)


def _maximum_float(value: object, *values: object) -> object:
    try:
        return max(_float(item) for item in (value, *values))
    except (OverflowError, TypeError, ValueError) as error:
        return _conversion_failure("float64", value, error)


def functions() -> dict[str, TemplateFunction]:
    """Return the complete raw Sprout numeric registry."""

    return {
        "floor": _floor,
        "ceil": _ceil,
        "round": _round,
        "add": _add,
        "add1": _add1,
        "sub": _sub,
        "mul": _mul,
        "mulf": _mulf,
        "div": _div,
        "divf": _divf,
        "mod": _mod,
        "min": _minimum,
        "minf": _minimum_float,
        "max": _maximum,
        "maxf": _maximum_float,
    }
