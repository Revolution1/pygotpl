"""Sprout slice functions with pipeline-friendly target ordering."""

from __future__ import annotations

from typing import cast

from gotpl._compat.gofmt.go import sprintf
from gotpl.funcs.sprig import generic_func_map
from gotpl.runtime import INVALID, UNTYPED_NIL, FunctionResult

from .registry import TemplateFunction

_SPRIG = generic_func_map()


def _list(*values: object) -> list[object]:
    return list(values)


def _sequence(value: object, operation: str) -> list[object] | FunctionResult:
    if value is None or value is UNTYPED_NIL or value is INVALID:
        return FunctionResult.failure(ValueError(f"cannot {operation} nil"))
    sequence = _sequence_value(value)
    if sequence is None:
        return FunctionResult.failure(
            TypeError(f"cannot {operation} on type {type(value).__name__}")
        )
    return list(sequence)


def _sequence_value(value: object) -> list[object] | tuple[object, ...] | None:
    if isinstance(value, list):
        return cast(list[object], value)
    if isinstance(value, tuple):
        return cast(tuple[object, ...], value)
    return None


def _append(item: object, value: object) -> object:
    result = _sequence(value, "append")
    if isinstance(result, FunctionResult):
        return result
    return [*result, item]


def _prepend(item: object, value: object) -> object:
    result = _sequence(value, "prepend")
    if isinstance(result, FunctionResult):
        return result
    return [item, *result]


def _concat(*values: object) -> list[object]:
    result: list[object] = []
    for value in values:
        sequence = _sequence_value(value)
        if sequence is not None:
            result.extend(sequence)
    return result


def _chunk(size: int, value: object) -> object:
    result = _sequence(value, "chunk")
    if isinstance(result, FunctionResult):
        return result
    if size <= 0:
        return FunctionResult.failure(ValueError("chunk size must be positive"))
    return [result[index : index + size] for index in range(0, len(result), size)]


def _equal(left: object, right: object) -> bool:
    return bool(_SPRIG["deepEqual"](left, right))


def _uniq(value: object) -> object:
    sequence = _sequence(value, "uniq")
    if isinstance(sequence, FunctionResult):
        return sequence
    result: list[object] = []
    for item in sequence:
        if not any(_equal(item, existing) for existing in result):
            result.append(item)
    return result


def _compact(value: object) -> object:
    sequence = _sequence(value, "compact")
    if isinstance(sequence, FunctionResult):
        return sequence
    return [item for item in sequence if not _SPRIG["empty"](item)]


def _flatten(value: object) -> object:
    return _flatten_depth(-1, value)


def _flatten_depth(depth: int, value: object) -> object:
    sequence = _sequence(value, "flatten")
    if isinstance(sequence, FunctionResult):
        return sequence
    return _flatten_sequence(sequence, depth)


def _flatten_sequence(value: list[object], remaining: int) -> list[object]:
    result: list[object] = []
    for item in value:
        sequence = _sequence_value(item)
        if sequence is not None and (remaining > 0 or remaining <= -1):
            result.extend(_flatten_sequence(list(sequence), remaining - 1))
        else:
            result.append(item)
    return result


def _slice(*args: object) -> object:
    if not args:
        return FunctionResult.failure(
            ValueError("slice requires at least one argument")
        )
    value = args[-1]
    sequence = _sequence(value, "slice")
    if isinstance(sequence, FunctionResult):
        return sequence
    if not sequence:
        return None
    indices = args[:-1]
    try:
        start = _index(indices[0]) if indices else 0
        end = _index(indices[1]) if len(indices) > 1 else len(sequence)
    except (TypeError, ValueError) as error:
        return FunctionResult.failure(error)
    if start < 0 or start > len(sequence):
        return FunctionResult.failure(IndexError("start index out of bounds"))
    if end < start or end > len(sequence):
        return FunctionResult.failure(IndexError("end index out of bounds"))
    return sequence[start:end]


def _has(element: object, value: object) -> object:
    if value is None or value is UNTYPED_NIL or value is INVALID:
        return False
    sequence = _sequence(value, "find has")
    if isinstance(sequence, FunctionResult):
        return sequence
    return any(_equal(element, item) for item in sequence)


def _without(*args: object) -> object:
    if len(args) < 2:
        return FunctionResult.failure(
            ValueError("without requires at least two arguments")
        )
    sequence = _sequence(args[-1], "without")
    if isinstance(sequence, FunctionResult):
        return sequence
    omitted = args[:-1]
    return [
        item
        for item in sequence
        if not any(_equal(item, excluded) for excluded in omitted)
    ]


def _rest(value: object) -> object:
    sequence = _sequence(value, "rest")
    if isinstance(sequence, FunctionResult):
        return sequence
    return sequence[1:] if sequence else None


def _initial(value: object) -> object:
    sequence = _sequence(value, "initial")
    if isinstance(sequence, FunctionResult):
        return sequence
    return sequence[:-1] if sequence else None


def _first(value: object) -> object:
    sequence = _sequence(value, "first")
    if isinstance(sequence, FunctionResult):
        return sequence
    return sequence[0] if sequence else None


def _last(value: object) -> object:
    sequence = _sequence(value, "last")
    if isinstance(sequence, FunctionResult):
        return sequence
    return sequence[-1] if sequence else None


def _reverse(value: object) -> object:
    sequence = _sequence(value, "reverse")
    if isinstance(sequence, FunctionResult):
        return sequence
    return list(reversed(sequence))


def _sort_alpha(value: object) -> object:
    return _SPRIG["sortAlpha"](value)


def _split_list(separator: str, value: str) -> object:
    return _SPRIG["splitList"](separator, value)


def _str_slice(value: object) -> list[str]:
    if value is None or value is UNTYPED_NIL or value is INVALID:
        return []
    sequence = _sequence_value(value)
    if sequence is not None:
        return [
            sprintf("%v", item)
            for item in sequence
            if item is not None and item is not UNTYPED_NIL and item is not INVALID
        ]
    return [sprintf("%v", value)]


def _index(value: object) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        return int(value, 0)
    raise TypeError(f"cannot convert {type(value).__name__} to an index")


def _until(count: int) -> list[int]:
    return list(range(0, count, -1 if count < 0 else 1))


def _until_step(start: int, stop: int, step: int) -> list[int]:
    if (stop < start and step >= 0) or (stop >= start and step <= 0):
        return []
    return list(range(start, stop, step))


def functions() -> dict[str, TemplateFunction]:
    """Return the complete raw Sprout slices registry."""

    return {
        "list": _list,
        "append": _append,
        "prepend": _prepend,
        "concat": _concat,
        "chunk": _chunk,
        "uniq": _uniq,
        "compact": _compact,
        "flatten": _flatten,
        "flattenDepth": _flatten_depth,
        "slice": _slice,
        "has": _has,
        "without": _without,
        "rest": _rest,
        "initial": _initial,
        "first": _first,
        "last": _last,
        "reverse": _reverse,
        "sortAlpha": _sort_alpha,
        "splitList": _split_list,
        "strSlice": _str_slice,
        "until": _until,
        "untilStep": _until_step,
    }
