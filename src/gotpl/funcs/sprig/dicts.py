"""Sprig dictionary construction, selection, and mutation functions."""

from __future__ import annotations

from copy import deepcopy
from typing import cast

from gotpl.runtime import FunctionResult

from .defaults import empty
from .strings import to_string


def make_dict(*values: object) -> dict[str, object]:
    result: dict[str, object] = {}
    for index in range(0, len(values), 2):
        key = to_string(values[index])
        result[key] = values[index + 1] if index + 1 < len(values) else ""
    return result


def get(value: dict[str, object], key: str) -> object:
    return value.get(key, "")


def set_value(value: dict[str, object], key: str, item: object) -> dict[str, object]:
    value[key] = item
    return value


def unset(value: dict[str, object], key: str) -> dict[str, object]:
    value.pop(key, None)
    return value


def has_key(value: dict[str, object], key: str) -> bool:
    return key in value


def pluck(key: str, *values: dict[str, object]) -> list[object]:
    return [value[key] for value in values if key in value]


def keys(*values: dict[str, object]) -> list[str]:
    return [key for value in values for key in value]


def values(value: dict[str, object]) -> list[object]:
    return list(value.values())


def pick(value: dict[str, object], *selected: str) -> dict[str, object]:
    return {key: value[key] for key in selected if key in value}


def omit(value: dict[str, object], *excluded: str) -> dict[str, object]:
    excluded_keys = set(excluded)
    return {key: item for key, item in value.items() if key not in excluded_keys}


def deep_copy(value: object) -> object:
    try:
        return deepcopy(value)
    except Exception as error:
        raise RuntimeError(f"deepCopy error: {error}") from error


def must_deep_copy(value: object) -> FunctionResult:
    try:
        return FunctionResult.success(deepcopy(value))
    except Exception as error:
        return FunctionResult.failure(error)


def merge(destination: dict[str, object], *sources: dict[str, object]) -> object:
    try:
        return _merge(destination, sources, overwrite=False)
    except Exception:
        return ""


def must_merge(
    destination: dict[str, object], *sources: dict[str, object]
) -> FunctionResult:
    try:
        return FunctionResult.success(_merge(destination, sources, overwrite=False))
    except Exception as error:
        return FunctionResult.failure(error)


def merge_overwrite(
    destination: dict[str, object], *sources: dict[str, object]
) -> object:
    try:
        return _merge(destination, sources, overwrite=True)
    except Exception:
        return ""


def must_merge_overwrite(
    destination: dict[str, object], *sources: dict[str, object]
) -> FunctionResult:
    try:
        return FunctionResult.success(_merge(destination, sources, overwrite=True))
    except Exception as error:
        return FunctionResult.failure(error)


def dig(*values: object) -> FunctionResult:
    if len(values) < 3:
        raise TypeError("dig needs at least three arguments")
    keys = values[:-2]
    fallback = values[-2]
    current: object = values[-1]
    if not isinstance(current, dict):
        raise TypeError("dig requires a dictionary")
    for index, key in enumerate(keys):
        if not isinstance(key, str):
            raise TypeError("dig keys must be strings")
        mapping = cast(dict[str, object], current)
        if key not in mapping:
            return FunctionResult.success(fallback)
        current = mapping[key]
        if index < len(keys) - 1 and not isinstance(current, dict):
            raise TypeError("dig encountered a non-dictionary value")
    return FunctionResult.success(cast(object, current))


def _merge(
    destination: dict[str, object],
    sources: tuple[dict[str, object], ...],
    *,
    overwrite: bool,
) -> dict[str, object]:
    for source in sources:
        _merge_into(destination, source, overwrite=overwrite)
    return destination


def _merge_into(
    destination: dict[str, object],
    source: dict[str, object],
    *,
    overwrite: bool,
) -> None:
    for key, source_value in source.items():
        destination_value: object = destination.get(key)
        if isinstance(destination_value, dict) and isinstance(source_value, dict):
            _merge_into(
                cast(dict[str, object], destination_value),
                cast(dict[str, object], source_value),
                overwrite=overwrite,
            )
        elif (
            key not in destination
            or overwrite
            or empty(cast(object, destination_value))
        ):
            destination[key] = source_value
