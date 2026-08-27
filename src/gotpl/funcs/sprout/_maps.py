"""Sprout map functions with pipeline-first signatures and dotted dig keys."""

from __future__ import annotations

from typing import TypeGuard, cast

from gotpl.funcs.sprig import generic_func_map
from gotpl.runtime import FunctionResult

from .registry import TemplateFunction

_SPRIG = generic_func_map()


def _dict(*values: object) -> object:
    return _SPRIG["dict"](*values)


def _get(key: str, value: dict[str, object]) -> object:
    return value.get(key, "")


def _set(key: str, item: object, value: dict[str, object]) -> dict[str, object]:
    value[key] = item
    return value


def _unset(key: str, value: dict[str, object]) -> dict[str, object]:
    value.pop(key, None)
    return value


def _keys(*values: dict[str, object]) -> list[str]:
    return [key for value in values for key in value]


def _values(*values: dict[str, object]) -> list[object]:
    return [item for value in values for item in value.values()]


def _pluck(key: str, *values: dict[str, object]) -> list[object]:
    return [value[key] for value in values if key in value]


def _pick(*args: object) -> object:
    parsed = _selection_args("pick", args)
    if isinstance(parsed, FunctionResult):
        return parsed
    keys, value = parsed
    return {key: value[key] for key in keys if key in value}


def _omit(*args: object) -> object:
    parsed = _selection_args("omit", args)
    if isinstance(parsed, FunctionResult):
        return parsed
    keys, value = parsed
    omitted = set(keys)
    return {key: item for key, item in value.items() if key not in omitted}


def _selection_args(
    name: str, args: tuple[object, ...]
) -> tuple[list[str], dict[str, object]] | FunctionResult:
    if len(args) < 2:
        return FunctionResult.failure(
            ValueError(f"{name} requires at least two arguments")
        )
    value = args[-1]
    if not isinstance(value, dict):
        return FunctionResult.failure(
            TypeError("last argument must be a map[string]any")
        )
    keys: list[str] = []
    for key in args[:-1]:
        if not isinstance(key, str):
            return FunctionResult.failure(TypeError("all keys must be strings"))
        keys.append(key)
    return keys, cast(dict[str, object], value)


def _dig(*args: object) -> object:
    if len(args) < 2:
        return FunctionResult.failure(
            ValueError(
                "dig requires at least two arguments: "
                "a sequence of keys and a dictionary"
            )
        )
    value = args[-1]
    if not _is_string_map(value):
        return FunctionResult.failure(
            TypeError("last argument must be a map[string]any")
        )

    keys: list[str] = []
    for position, raw_key in enumerate(args[:-1]):
        if not isinstance(raw_key, str):
            return FunctionResult.failure(
                TypeError(
                    f"cannot parse keys: all keys must be strings, "
                    f"got {type(raw_key).__name__} at position {position}"
                )
            )
        try:
            keys.extend(_split_key(raw_key))
        except ValueError as error:
            return FunctionResult.failure(ValueError(f"cannot split keys: {error}"))

    return _dig_into(value, keys)


def _dig_into(mapping: dict[str, object], keys: list[str]) -> object:
    current = mapping
    for index, key in enumerate(keys):
        if key not in current:
            return None
        value: object = current[key]
        if index == len(keys) - 1:
            return value
        if not _is_string_map(value):
            return FunctionResult.failure(
                TypeError(f"value at key {key!r} is not a nested dictionary")
            )
        current = value
    return FunctionResult.failure(ValueError("unexpected termination of key traversal"))


def _is_string_map(value: object) -> TypeGuard[dict[str, object]]:
    if not isinstance(value, dict):
        return False
    mapping = cast(dict[object, object], value)
    return all(isinstance(key, str) for key in mapping)


def _split_key(key: str) -> list[str]:
    parts: list[str] = []
    segment: list[str] = []
    index = 0
    while index < len(key):
        character = key[index]
        if character == ".":
            if not segment:
                raise ValueError(f"empty key segment in path {key!r}")
            parts.append("".join(segment))
            segment.clear()
        elif character == "\\":
            index += 1
            if index >= len(key):
                raise ValueError(
                    f"invalid escape sequence: trailing backslash in key {key!r}"
                )
            escaped = key[index]
            if escaped not in {".", "\\"}:
                raise ValueError(f"invalid escape sequence: \\{escaped} in key {key!r}")
            segment.append(escaped)
        else:
            segment.append(character)
        index += 1
    if key and not segment:
        raise ValueError(f"empty key segment in path {key!r}")
    parts.append("".join(segment))
    return parts


def _has_key(key: str, value: dict[str, object]) -> bool:
    return key in value


def _must_function(name: str) -> TemplateFunction:
    return _SPRIG[name]


def functions() -> dict[str, TemplateFunction]:
    """Return the complete raw Sprout maps registry."""

    return {
        "dict": _dict,
        "get": _get,
        "set": _set,
        "unset": _unset,
        "keys": _keys,
        "values": _values,
        "pluck": _pluck,
        "pick": _pick,
        "omit": _omit,
        "dig": _dig,
        "hasKey": _has_key,
        "merge": _must_function("mustMerge"),
        "mergeOverwrite": _must_function("mustMergeOverwrite"),
    }
