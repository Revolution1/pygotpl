"""Sprig defaulting and selection functions."""

import base64
import json
import math
from collections.abc import Sized
from decimal import Decimal
from typing import cast

from gotpl.runtime import INVALID, UNTYPED_NIL, FunctionResult

from ._values import NilSlice


def empty(value: object) -> bool:
    """Return whether a value has Sprig's type-specific zero value."""

    if value is INVALID or value is UNTYPED_NIL or value is None:
        return True
    if isinstance(value, bool):
        return not value
    if isinstance(value, (int, float, complex)):
        return value == 0
    if isinstance(value, (str, bytes, bytearray, list, tuple, dict, set, frozenset)):
        return len(cast(Sized, value)) == 0
    return False


def default(default_value: object, *given: object) -> object:
    if not given or empty(given[0]):
        return default_value
    return given[0]


def coalesce(*values: object) -> object:
    for value in values:
        if not empty(value):
            return value
    return None


def all_values(*values: object) -> bool:
    return all(not empty(value) for value in values)


def any_value(*values: object) -> bool:
    return any(not empty(value) for value in values)


def ternary(true_value: object, false_value: object, condition: bool) -> object:
    return true_value if condition else false_value


def from_json(value: str) -> object:
    try:
        return _json_loads(value)
    except (json.JSONDecodeError, TypeError, ValueError):
        return None


def must_from_json(value: str) -> FunctionResult:
    try:
        return FunctionResult.success(_json_loads(value))
    except (json.JSONDecodeError, TypeError, ValueError) as error:
        return FunctionResult.failure(error)


def to_json(value: object) -> str:
    try:
        return _json_dumps(value, html_safe=True)
    except (TypeError, ValueError):
        return ""


def must_to_json(value: object) -> FunctionResult:
    try:
        return FunctionResult.success(_json_dumps(value, html_safe=True))
    except (TypeError, ValueError) as error:
        return FunctionResult.failure(error)


def to_pretty_json(value: object) -> str:
    try:
        return _json_dumps(value, html_safe=True, pretty=True)
    except (TypeError, ValueError):
        return ""


def must_to_pretty_json(value: object) -> FunctionResult:
    try:
        return FunctionResult.success(_json_dumps(value, html_safe=True, pretty=True))
    except (TypeError, ValueError) as error:
        return FunctionResult.failure(error)


def to_raw_json(value: object) -> str:
    return _json_dumps(value, html_safe=False)


def must_to_raw_json(value: object) -> FunctionResult:
    try:
        return FunctionResult.success(_json_dumps(value, html_safe=False))
    except (TypeError, ValueError) as error:
        return FunctionResult.failure(error)


def _json_dumps(
    value: object,
    *,
    html_safe: bool,
    pretty: bool = False,
) -> str:
    return _json_encode(value, html_safe=html_safe, pretty=pretty, level=0, seen=set())


def _json_loads(value: str) -> object:
    def reject_constant(constant: str) -> object:
        raise ValueError(f"invalid JSON constant {constant}")

    return json.loads(
        value,
        parse_int=float,
        parse_float=float,
        parse_constant=reject_constant,
    )


def _json_encode(
    value: object,
    *,
    html_safe: bool,
    pretty: bool,
    level: int,
    seen: set[int],
) -> str:
    if value is None:
        return "null"
    if isinstance(value, NilSlice):
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return _go_json_float(value)
    if isinstance(value, str):
        return _json_string(value, html_safe=html_safe)
    if isinstance(value, (bytes, bytearray)):
        encoded = base64.b64encode(bytes(value)).decode()
        return _json_string(encoded, html_safe=html_safe)
    if isinstance(value, (list, tuple)):
        return _json_sequence(
            cast(list[object] | tuple[object, ...], value),
            html_safe=html_safe,
            pretty=pretty,
            level=level,
            seen=seen,
        )
    if isinstance(value, dict):
        return _json_mapping(
            cast(dict[object, object], value),
            html_safe=html_safe,
            pretty=pretty,
            level=level,
            seen=seen,
        )
    raise TypeError(f"unsupported type: {type(value).__name__}")


def _json_sequence(
    value: list[object] | tuple[object, ...],
    *,
    html_safe: bool,
    pretty: bool,
    level: int,
    seen: set[int],
) -> str:
    identity = id(value)
    if identity in seen:
        raise ValueError("encountered a cycle")
    seen.add(identity)
    try:
        items = [
            _json_encode(
                item,
                html_safe=html_safe,
                pretty=pretty,
                level=level + 1,
                seen=seen,
            )
            for item in value
        ]
    finally:
        seen.remove(identity)
    if not items:
        return "[]"
    if not pretty:
        return "[" + ",".join(items) + "]"
    indentation = "  " * (level + 1)
    return (
        "[\n"
        + indentation
        + (",\n" + indentation).join(items)
        + "\n"
        + "  " * level
        + "]"
    )


def _json_mapping(
    value: dict[object, object],
    *,
    html_safe: bool,
    pretty: bool,
    level: int,
    seen: set[int],
) -> str:
    identity = id(value)
    if identity in seen:
        raise ValueError("encountered a cycle")
    entries: list[tuple[str, object]] = []
    for key, item in value.items():
        if isinstance(key, str):
            encoded_key = key
        elif isinstance(key, int) and not isinstance(key, bool):
            encoded_key = str(key)
        else:
            raise TypeError(f"unsupported map key type: {type(key).__name__}")
        entries.append((encoded_key, item))
    entries.sort(key=lambda entry: entry[0])
    seen.add(identity)
    try:
        separator = ": " if pretty else ":"
        items = [
            _json_string(key, html_safe=html_safe)
            + separator
            + _json_encode(
                item,
                html_safe=html_safe,
                pretty=pretty,
                level=level + 1,
                seen=seen,
            )
            for key, item in entries
        ]
    finally:
        seen.remove(identity)
    if not items:
        return "{}"
    if not pretty:
        return "{" + ",".join(items) + "}"
    indentation = "  " * (level + 1)
    return (
        "{\n"
        + indentation
        + (",\n" + indentation).join(items)
        + "\n"
        + "  " * level
        + "}"
    )


def _json_string(value: str, *, html_safe: bool) -> str:
    result = json.encoder.encode_basestring(value)
    if html_safe:
        result = (
            result.replace("&", r"\u0026")
            .replace("<", r"\u003c")
            .replace(">", r"\u003e")
        )
    return result.replace("\u2028", r"\u2028").replace("\u2029", r"\u2029")


def _go_json_float(value: float) -> str:
    if not math.isfinite(value):
        raise ValueError("unsupported float value")
    absolute = abs(value)
    rendered = repr(value).lower()
    if absolute != 0 and (absolute < 1e-6 or absolute >= 1e21):
        mantissa, exponent = rendered.split("e")
        exponent_value = int(exponent)
        sign = "+" if exponent_value >= 0 else "-"
        return f"{mantissa}e{sign}{abs(exponent_value)}"
    if "e" in rendered:
        return format(Decimal(rendered), "f")
    return rendered[:-2] if rendered.endswith(".0") else rendered
