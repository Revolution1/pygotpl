"""Sprig list construction and transformation functions."""

from __future__ import annotations

from collections.abc import Callable
from typing import cast

from gotpl.runtime import FunctionResult

from ._values import NilSlice, go_kind_of
from .defaults import empty
from .numeric import to_int


def make_list(*values: object) -> list[object]:
    return list(values)


def append(value: object, item: object) -> list[object]:
    return [*_sequence(value, "push"), item]


def prepend(value: object, item: object) -> list[object]:
    return [item, *_sequence(value, "prepend")]


def first(value: object) -> object:
    sequence = _sequence(value, "find first")
    return sequence[0] if sequence else None


def last(value: object) -> object:
    sequence = _sequence(value, "find last")
    return sequence[-1] if sequence else None


def rest(value: object) -> list[object]:
    sequence = _sequence(value, "find rest")
    return sequence[1:] if sequence else NilSlice()


def initial(value: object) -> list[object]:
    sequence = _sequence(value, "find initial")
    return sequence[:-1] if sequence else NilSlice()


def reverse(value: object) -> list[object]:
    return list(reversed(_sequence(value, "find reverse")))


def compact(value: object) -> list[object]:
    return [item for item in _sequence(value, "compact") if not empty(item)]


def uniq(value: object) -> list[object]:
    result: list[object] = []
    for item in _sequence(value, "find uniq"):
        if not any(deep_equal_value(item, existing) for existing in result):
            result.append(item)
    return result


def without(value: object, *excluded: object) -> list[object]:
    return [
        item
        for item in _sequence(value, "find without")
        if not any(deep_equal_value(item, omitted) for omitted in excluded)
    ]


def has(needle: object, value: object) -> bool:
    if value is None:
        return False
    return any(deep_equal_value(needle, item) for item in _sequence(value, "find has"))


def slice_list(value: object, *indices: object) -> list[object]:
    sequence = _sequence(value, "slice")
    if not sequence:
        return NilSlice()
    start = to_int(indices[0]) if indices else 0
    end = to_int(indices[1]) if len(indices) >= 2 else len(sequence)
    if len(indices) > 2 or not 0 <= start <= end <= len(sequence):
        raise IndexError("slice bounds out of range")
    return sequence[start:end]


def concat(*values: object) -> list[object]:
    result: list[object] = []
    for value in values:
        result.extend(_sequence(value, "concat"))
    return result or NilSlice()


def chunk(size: int, value: object) -> list[list[object]]:
    sequence = _sequence(value, "chunk")
    if size <= 0:
        raise ValueError("chunk size must be positive")
    return [sequence[index : index + size] for index in range(0, len(sequence), size)]


def must_append(value: object, item: object) -> FunctionResult:
    return _must(lambda: append(value, item))


def must_prepend(value: object, item: object) -> FunctionResult:
    return _must(lambda: prepend(value, item))


def must_first(value: object) -> FunctionResult:
    return _must(lambda: first(value))


def must_last(value: object) -> FunctionResult:
    return _must(lambda: last(value))


def must_rest(value: object) -> FunctionResult:
    return _must(lambda: rest(value))


def must_initial(value: object) -> FunctionResult:
    return _must(lambda: initial(value))


def must_reverse(value: object) -> FunctionResult:
    return _must(lambda: reverse(value))


def must_compact(value: object) -> FunctionResult:
    return _must(lambda: compact(value))


def must_uniq(value: object) -> FunctionResult:
    return _must(lambda: uniq(value))


def must_without(value: object, *excluded: object) -> FunctionResult:
    return _must(lambda: without(value, *excluded))


def must_has(needle: object, value: object) -> FunctionResult:
    return _must(lambda: has(needle, value))


def must_slice(value: object, *indices: object) -> FunctionResult:
    try:
        return FunctionResult.success(slice_list(value, *indices))
    except (IndexError, _NilReflectionPanic):
        raise
    except Exception as error:
        return FunctionResult.failure(error)


def must_chunk(size: int, value: object) -> FunctionResult:
    try:
        return FunctionResult.success(chunk(size, value))
    except (ValueError, _NilReflectionPanic):
        raise
    except Exception as error:
        return FunctionResult.failure(error)


def _must(operation: Callable[[], object]) -> FunctionResult:
    try:
        return FunctionResult.success(operation())
    except _NilReflectionPanic:
        raise
    except Exception as error:
        return FunctionResult.failure(error)


def _sequence(value: object, operation: str) -> list[object]:
    if value is None:
        raise _NilReflectionPanic(
            "runtime error: invalid memory address or nil pointer dereference"
        )
    if isinstance(value, (bytes, bytearray, list, tuple)):
        sequence = cast(bytes | bytearray | list[object] | tuple[object, ...], value)
        return list(sequence)
    kind = go_kind_of(value)
    article = "as list" if operation == "concat" else f"on type {kind}"
    if operation == "concat":
        raise TypeError(f"Cannot concat type {kind} {article}")
    if operation == "slice":
        raise TypeError(f"list should be type of slice or array but {kind}")
    if operation == "chunk":
        raise TypeError(f"Cannot chunk type {kind}")
    raise TypeError(f"Cannot {operation} {article}")


class _NilReflectionPanic(RuntimeError):
    """Model the upstream nil-interface reflection panic separately from errors."""


def deep_equal_value(left: object, right: object) -> bool:
    return _deep_equal_value(left, right, set())


def _deep_equal_value(
    left: object,
    right: object,
    visited: set[tuple[int, int]],
) -> bool:
    if type(left) is not type(right):
        return False
    if callable(left):
        return False
    if isinstance(left, (list, tuple)) and isinstance(right, (list, tuple)):
        left_sequence = cast(list[object] | tuple[object, ...], left)
        right_sequence = cast(list[object] | tuple[object, ...], right)
        pair = (id(left_sequence), id(right_sequence))
        if pair in visited:
            return True
        visited.add(pair)
        return len(left_sequence) == len(right_sequence) and all(
            _deep_equal_value(a, b, visited)
            for a, b in zip(left_sequence, right_sequence, strict=True)
        )
    if isinstance(left, dict) and isinstance(right, dict):
        left_dict = cast(dict[object, object], left)
        right_dict = cast(dict[object, object], right)
        pair = (id(left_dict), id(right_dict))
        if pair in visited:
            return True
        visited.add(pair)
        return left_dict.keys() == right_dict.keys() and all(
            _deep_equal_value(left_dict[key], right_dict[key], visited)
            for key in left_dict
        )
    try:
        return bool(left == right)
    except Exception:
        return False
