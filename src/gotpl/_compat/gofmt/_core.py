"""A focused pure-Python implementation of Go fmt formatting semantics."""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from dataclasses import dataclass, replace
from functools import lru_cache
from typing import cast

from .types import FormatMode, FormatValueKind, GoFormatSpec, GoPointer


@dataclass(frozen=True, slots=True)
class _Directive:
    flags: str
    width: int | None
    precision: int | None
    verb: str
    value_index: int | None = None
    width_from_arg: bool = False
    width_index: int | None = None
    precision_from_arg: bool = False
    precision_index: int | None = None
    bad_index: bool = False


def sprintf(
    format_string: object,
    *values: object,
    format_mode: FormatMode = "go",
) -> str:
    """Format values using the Go fmt verbs exposed by template printf."""

    if not isinstance(format_string, str):
        raise TypeError("printf format must be a string")
    output: list[str] = []
    position = 0
    value_index = 0
    used_indexes: set[int] = set()
    reordered = False

    def take(index: int | None) -> tuple[object | None, bool]:
        nonlocal value_index
        resolved = value_index if index is None else index
        value_index = resolved + 1
        if resolved >= len(values):
            return None, False
        used_indexes.add(resolved)
        return values[resolved], True

    while position < len(format_string):
        percent = format_string.find("%", position)
        if percent < 0:
            output.append(format_string[position:])
            break
        output.append(format_string[position:percent])
        if percent + 1 < len(format_string) and format_string[percent + 1] == "%":
            output.append("%")
            position = percent + 2
            continue
        directive, position = _parse_directive(format_string, percent + 1)
        if directive is None:
            reordered = reordered or format_string.startswith("%[", percent)
            output.append("%!(NOVERB)")
            break
        has_explicit_index = (
            directive.value_index is not None
            or directive.width_index is not None
            or directive.precision_index is not None
            or directive.bad_index
        )
        reordered = reordered or has_explicit_index
        if directive.bad_index:
            output.append(f"%!{directive.verb}(BADINDEX)")
            continue
        if directive.width_index is not None and directive.width_index >= len(values):
            output.append(f"%!{directive.verb}(BADINDEX)")
            continue
        if directive.width_from_arg:
            width_value, present = take(directive.width_index)
            if (
                not present
                or not isinstance(width_value, int)
                or isinstance(width_value, bool)
            ):
                output.append("%!(BADWIDTH)")
            elif width_value < 0:
                directive = replace(
                    directive,
                    flags=directive.flags + "-",
                    width=-width_value,
                )
            else:
                directive = replace(directive, width=width_value)
        if directive.precision_from_arg:
            precision_value, present = take(directive.precision_index)
            if (
                not present
                or not isinstance(precision_value, int)
                or isinstance(precision_value, bool)
            ):
                output.append("%!(BADPREC)")
            elif precision_value < 0:
                directive = replace(directive, precision=None)
            else:
                directive = replace(directive, precision=precision_value)
            if not present and directive.precision_index is not None:
                output.append(f"%!{directive.verb}(BADINDEX)")
                continue
        if directive.value_index is not None and directive.value_index >= len(values):
            output.append(f"%!{directive.verb}(BADINDEX)")
            continue
        value, present = take(directive.value_index)
        if not present:
            output.append(f"%!{directive.verb}(MISSING)")
            continue
        output.append(_format_directive(directive, value, format_mode))
    extra_values = [
        value for index, value in enumerate(values) if index not in used_indexes
    ]
    if extra_values and not reordered:
        extras = ", ".join(
            f"{_type_name(value, format_mode)}={_default_value(value, format_mode)}"
            for value in extra_values
        )
        output.append(f"%!(EXTRA {extras})")
    return "".join(output)


@lru_cache(maxsize=4_096)
def _parse_directive(text: str, position: int) -> tuple[_Directive | None, int]:
    flags_start = position
    while position < len(text) and text[position] in "+-# 0":
        position += 1
    flags = text[flags_start:position]
    initial_index, position, has_initial_index, bad_index = _parse_index(text, position)
    width_start = position
    while position < len(text) and text[position].isdigit():
        position += 1
    width = int(text[width_start:position]) if position > width_start else None
    width_from_arg = position < len(text) and text[position] == "*"
    width_index = initial_index if width_from_arg and has_initial_index else None
    value_index = initial_index if has_initial_index and not width_from_arg else None
    if width_from_arg:
        position += 1
    precision: int | None = None
    precision_from_arg = False
    precision_index: int | None = None
    if position < len(text) and text[position] == ".":
        position += 1
        index, position, has_index, index_is_bad = _parse_index(text, position)
        bad_index = bad_index or index_is_bad
        if position < len(text) and text[position] == "*":
            precision_from_arg = True
            precision_index = index if has_index else None
            position += 1
        else:
            precision_start = position
            while position < len(text) and text[position].isdigit():
                position += 1
            precision = (
                int(text[precision_start:position]) if position > precision_start else 0
            )
    trailing_index, position, has_trailing_index, trailing_bad = _parse_index(
        text, position
    )
    bad_index = bad_index or trailing_bad
    if has_trailing_index:
        value_index = trailing_index
    if position >= len(text):
        return None, position
    return (
        _Directive(
            flags,
            width,
            precision,
            text[position],
            value_index,
            width_from_arg,
            width_index,
            precision_from_arg,
            precision_index,
            bad_index,
        ),
        position + 1,
    )


def _parse_index(text: str, position: int) -> tuple[int | None, int, bool, bool]:
    if position >= len(text) or text[position] != "[":
        return None, position, False, False
    closing = text.find("]", position + 1)
    if closing < 0:
        return None, len(text), False, True
    contents = text[position + 1 : closing]
    if not contents.isdigit() or int(contents) < 1:
        return None, closing + 1, False, True
    return int(contents) - 1, closing + 1, True, False


def _format_directive(
    directive: _Directive,
    value: object,
    format_mode: FormatMode,
) -> str:
    verb = directive.verb
    formatter = getattr(value, "__go_format__", None)
    if format_mode == "go" and callable(formatter):
        rendered = formatter(
            GoFormatSpec(
                verb,
                directive.flags,
                directive.width,
                directive.precision,
            )
        )
        if not isinstance(rendered, str):
            raise TypeError("__go_format__ must return a string")
        return rendered
    if verb == "p":
        return _format_pointer(value, directive, format_mode)
    if verb == "T":
        return _pad(_type_name(value, format_mode), directive)
    if verb == "v":
        rendered = (
            _syntax_value(value, format_mode)
            if "#" in directive.flags
            else _default_value(value, format_mode)
        )
        return _pad(rendered, directive)
    if verb == "t":
        if not isinstance(value, bool):
            return _bad_verb(verb, value, format_mode)
        return _pad("true" if value else "false", directive)
    if verb == "q" and isinstance(value, int) and not isinstance(value, bool):
        return _pad(
            _quote_rune(chr(value), ascii_only="+" in directive.flags), directive
        )
    byte_value = _as_bytes(value)
    if verb in {"s", "q", "x", "X"} and byte_value is not None:
        if directive.precision is not None:
            byte_value = byte_value[: directive.precision]
        if verb == "s":
            rendered = byte_value.decode(errors="replace")
        elif verb == "q":
            rendered = _quote_string(
                byte_value.decode(errors="replace"),
                ascii_only="+" in directive.flags,
                raw="#" in directive.flags,
            )
        else:
            rendered = byte_value.hex()
            if verb == "X":
                rendered = rendered.upper()
        return _pad(rendered, directive)
    if verb in {"s", "q", "x", "X"} and isinstance(value, str):
        if verb in {"x", "X"}:
            encoded = value.encode()
            if directive.precision is not None:
                encoded = encoded[: directive.precision]
            rendered = encoded.hex()
            if verb == "X":
                rendered = rendered.upper()
            return _pad(rendered, directive)
        rendered = value
        if directive.precision is not None:
            rendered = rendered[: directive.precision]
        if verb == "q":
            rendered = _quote_string(
                rendered,
                ascii_only="+" in directive.flags,
                raw="#" in directive.flags,
            )
        return _pad(rendered, directive)
    if (
        verb in {"d", "b", "o", "O", "x", "X", "c", "U"}
        and isinstance(value, int)
        and not isinstance(value, bool)
    ):
        return _format_integer(value, directive)
    if verb in {"b", "e", "E", "f", "F", "g", "G", "x", "X"} and isinstance(
        value, (float, complex)
    ):
        return _format_float(value, directive)
    return _bad_verb(verb, value, format_mode)


def _format_integer(value: int, directive: _Directive) -> str:
    verb = directive.verb
    if verb == "c":
        return _pad(chr(value), directive)
    if verb == "U":
        precision = directive.precision or 4
        return _pad(f"U+{value:0{precision}X}", directive)
    base_verb = {"d": "d", "b": "b", "o": "o", "O": "o", "x": "x", "X": "X"}[verb]
    digits = format(abs(value), base_verb)
    if directive.precision is not None:
        digits = digits.rjust(directive.precision, "0")
    prefix = ""
    if value < 0:
        prefix = "-"
    elif "+" in directive.flags:
        prefix = "+"
    elif " " in directive.flags:
        prefix = " "
    if "#" in directive.flags or verb == "O":
        prefix += {"b": "0b", "o": "0", "O": "0o", "x": "0x", "X": "0X"}.get(verb, "")
    return _pad_numeric(prefix, digits, directive)


def _format_pointer(
    value: object, directive: _Directive, format_mode: FormatMode
) -> str:
    if isinstance(value, GoPointer):
        address = value.address
    elif format_mode == "python" and value is not None:
        address = id(value)
    else:
        return _bad_verb("p", value, format_mode)
    prefix = "" if "#" in directive.flags else "0x"
    return _pad_numeric(prefix, f"{address:x}", directive)


def _format_float(value: float | complex, directive: _Directive) -> str:
    if isinstance(value, complex):
        if directive.verb in {"b", "x", "X"}:
            component = replace(directive, width=None)
            real = _format_float(value.real, component)
            imaginary = _format_float(abs(value.imag), component)
            sign = "+" if value.imag >= 0 else "-"
            return _pad(f"({real}{sign}{imaginary}i)", directive)
        precision = 6 if directive.precision is None else directive.precision
        real = format(value.real, f".{precision}{directive.verb}")
        imaginary = format(abs(value.imag), f".{precision}{directive.verb}")
        sign = "+" if value.imag >= 0 else "-"
        return _pad(f"({real}{sign}{imaginary}i)", directive)
    if math.isnan(value):
        return _pad("NaN", directive)
    if math.isinf(value):
        return _pad(("+" if value > 0 else "-") + "Inf", directive)
    if directive.verb == "b":
        significand, exponent = math.frexp(value)
        mantissa = int(significand * (1 << 53))
        return _pad_numeric(
            "", f"{mantissa}p{exponent - 53:+d}".replace("p+", "p"), directive
        )
    if directive.verb in {"x", "X"}:
        rendered = _hex_float(value, uppercase=directive.verb == "X")
        return _pad_numeric("", rendered, directive, zero_with_precision=True)
    if directive.verb in {"g", "G"} and directive.precision is None:
        rendered = _go_shortest_float(value)
        if directive.verb == "G":
            rendered = rendered.upper()
        if value >= 0 and "+" in directive.flags:
            rendered = "+" + rendered
        elif value >= 0 and " " in directive.flags:
            rendered = " " + rendered
        return _pad_numeric("", rendered, directive, zero_with_precision=True)
    precision = 6 if directive.precision is None else directive.precision
    rendered = format(value, f".{precision}{directive.verb}")
    if value >= 0 and "+" in directive.flags:
        rendered = "+" + rendered
    elif value >= 0 and " " in directive.flags:
        rendered = " " + rendered
    return _pad_numeric("", rendered, directive, zero_with_precision=True)


def _hex_float(value: float, *, uppercase: bool) -> str:
    mantissa, exponent = value.hex().split("p")
    integer, fraction = mantissa.split(".")
    fraction = fraction.rstrip("0")
    exponent_value = int(exponent)
    significand = integer if not fraction else f"{integer}.{fraction}"
    rendered = f"{significand}p{exponent_value:+03d}"
    return rendered.upper() if uppercase else rendered


def _pad(value: str, directive: _Directive) -> str:
    if directive.width is None or len(value) >= directive.width:
        return value
    fill = "0" if "0" in directive.flags and "-" not in directive.flags else " "
    if "-" in directive.flags:
        return value.ljust(directive.width, fill)
    return value.rjust(directive.width, fill)


def _pad_numeric(
    prefix: str,
    digits: str,
    directive: _Directive,
    *,
    zero_with_precision: bool = False,
) -> str:
    value = prefix + digits
    if directive.width is None or len(value) >= directive.width:
        return value
    if "-" in directive.flags:
        return value.ljust(directive.width)
    if "0" in directive.flags and (directive.precision is None or zero_with_precision):
        return prefix + digits.rjust(directive.width - len(prefix), "0")
    return value.rjust(directive.width)


def _bad_verb(verb: str, value: object, format_mode: FormatMode) -> str:
    type_name = _type_name(value, format_mode)
    rendered = _default_value(value, format_mode)
    if type_name == "<nil>" and rendered == "<nil>":
        return f"%!{verb}(<nil>)"
    return f"%!{verb}({type_name}={rendered})"


def _default_value(
    value: object,
    format_mode: FormatMode,
    *,
    nested: bool = False,
) -> str:
    adapted = _adapt_value(value, "default", format_mode, nested=nested)
    if adapted is not None:
        return adapted
    if format_mode == "python":
        return str(value)
    if value is None:
        return "<nil>"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, float):
        if math.isnan(value):
            return "NaN"
        if math.isinf(value):
            return ("+" if value > 0 else "-") + "Inf"
        return _go_shortest_float(value)
    if isinstance(value, GoPointer):
        pointer = cast(GoPointer[object], value)
        return "<nil>" if pointer.value is None else f"0x{pointer.address:x}"
    byte_value = _as_bytes(value)
    if byte_value is not None:
        return f"[{' '.join(str(item) for item in byte_value)}]"
    if isinstance(value, Mapping):
        mapping = cast(Mapping[object, object], value)
        keys = _ordered_mapping_keys(mapping)
        entries = (
            f"{_default_value(key, format_mode, nested=True)}:"
            f"{_default_value(mapping[key], format_mode, nested=True)}"
            for key in keys
        )
        return f"map[{' '.join(entries)}]"
    if isinstance(value, (list, tuple)):
        sequence = cast(list[object] | tuple[object, ...], value)
        items = (_default_value(item, format_mode, nested=True) for item in sequence)
        return f"[{' '.join(items)}]"
    if isinstance(value, complex):
        sign = "+" if value.imag >= 0 else "-"
        real = _go_shortest_float(value.real)
        imaginary = _go_shortest_float(abs(value.imag))
        return f"({real}{sign}{imaginary}i)"
    if type(value) is object:
        return f"<object object at 0x{id(value):x}>"
    return str(value)


def _go_shortest_float(value: float) -> str:
    if value == 0.0:
        return "-0" if math.copysign(1.0, value) < 0.0 else "0"
    sign = "-" if value < 0.0 else ""
    rendered = repr(abs(value)).lower()
    if "e" in rendered:
        mantissa, raw_exponent = rendered.split("e")
        exponent = int(raw_exponent)
        digits = mantissa.replace(".", "").lstrip("0").rstrip("0")
    else:
        integer, _, fraction = rendered.partition(".")
        raw_digits = integer + fraction
        first = next(
            index for index, character in enumerate(raw_digits) if character != "0"
        )
        exponent = len(integer) - first - 1
        digits = raw_digits[first:].rstrip("0")
    if exponent < -4 or exponent >= 6:
        mantissa = digits[0] + (f".{digits[1:]}" if len(digits) > 1 else "")
        exponent_sign = "+" if exponent >= 0 else "-"
        return f"{sign}{mantissa}e{exponent_sign}{abs(exponent):02d}"
    decimal_position = exponent + 1
    if decimal_position <= 0:
        return f"{sign}0.{('0' * -decimal_position)}{digits}"
    if decimal_position >= len(digits):
        return sign + digits + ("0" * (decimal_position - len(digits)))
    return f"{sign}{digits[:decimal_position]}.{digits[decimal_position:]}"


def _syntax_value(value: object, format_mode: FormatMode) -> str:
    adapted = _adapt_value(value, "syntax", format_mode, nested=True)
    if adapted is not None:
        return adapted
    if format_mode == "python":
        return repr(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, GoPointer):
        pointer = cast(GoPointer[object], value)
        if pointer.value is None:
            return f"(*{pointer.target_type})(nil)"
        return f"(*{pointer.target_type})(0x{pointer.address:x})"
    byte_value = _as_bytes(value)
    if byte_value is not None:
        entries = ", ".join(f"0x{item:x}" for item in byte_value)
        return f"[]byte{{{entries}}}"
    if isinstance(value, Mapping):
        mapping = cast(Mapping[object, object], value)
        keys = _ordered_mapping_keys(mapping)
        entries = (
            f"{_syntax_value(key, format_mode)}:"
            f"{_syntax_value(mapping[key], format_mode)}"
            for key in keys
        )
        explicit_type = _go_map_type(cast(object, value))
        map_type = (
            f"map[{explicit_type[0]}]{explicit_type[1]}"
            if explicit_type is not None
            else "map[string]interface {}"
        )
        return map_type + "{" + ", ".join(entries) + "}"
    if isinstance(value, (list, tuple)):
        sequence = cast(list[object] | tuple[object, ...], value)
        entries = ", ".join(_syntax_value(item, format_mode) for item in sequence)
        return "[]interface {}{" + entries + "}"
    return _default_value(value, format_mode, nested=True)


def _type_name(value: object, format_mode: FormatMode) -> str:
    adapted = _adapt_value(value, "type", format_mode, nested=True)
    if adapted is not None:
        return adapted
    if format_mode == "python":
        return type(value).__name__
    if value is None:
        return "<nil>"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float64"
    if isinstance(value, complex):
        return "complex128"
    if isinstance(value, str):
        return "string"
    if isinstance(value, GoPointer):
        return f"*{value.target_type}"
    if _as_bytes(value) is not None:
        return "[]uint8"
    if isinstance(value, Mapping):
        explicit_type = _go_map_type(cast(object, value))
        if explicit_type is not None:
            return f"map[{explicit_type[0]}]{explicit_type[1]}"
        return "map[string]interface {}"
    if isinstance(value, (list, tuple)):
        return "[]interface {}"
    if callable(value):
        return "func"
    return type(value).__name__


def _as_bytes(value: object) -> bytes | None:
    if isinstance(value, bytes):
        return value
    if isinstance(value, bytearray):
        return bytes(value)
    return None


def _adapt_value(
    value: object,
    kind: FormatValueKind,
    mode: FormatMode,
    *,
    nested: bool,
) -> str | None:
    adapter = getattr(value, "__go_format_value__", None)
    if not callable(adapter):
        return None
    rendered = adapter(kind, mode, nested=nested)
    if not isinstance(rendered, str):
        raise TypeError("__go_format_value__ must return a string")
    return rendered


def _go_map_type(value: object) -> tuple[str, str] | None:
    adapter = getattr(value, "__go_map_type__", None)
    if not callable(adapter):
        return None
    result: object = adapter()
    if result is None:
        return None
    if not isinstance(result, tuple):
        raise TypeError("__go_map_type__ must return two non-empty strings or None")
    typed_result = cast(tuple[object, ...], result)
    if len(typed_result) != 2:
        raise TypeError("__go_map_type__ must return two non-empty strings or None")
    key_type, value_type = typed_result
    if not (
        isinstance(key_type, str)
        and key_type
        and isinstance(value_type, str)
        and value_type
    ):
        raise TypeError("__go_map_type__ must return two non-empty strings or None")
    return key_type, value_type


def _ordered_mapping_keys(mapping: Mapping[object, object]) -> list[object]:
    keys = list(mapping)
    if keys and all(type(key) is complex for key in keys):
        return sorted(
            keys,
            key=lambda key: (
                cast(complex, key).real,
                cast(complex, key).imag,
            ),
        )
    if (
        keys
        and all(type(key) is type(keys[0]) for key in keys)
        and isinstance(keys[0], (bool, int, float, str))
    ):
        return sorted(keys)  # type: ignore[type-var]
    return sorted(keys, key=lambda key: (type(key).__name__, repr(key)))


def _quote_string(value: str, *, ascii_only: bool, raw: bool) -> str:
    if (
        raw
        and "`" not in value
        and all(character == "\t" or character.isprintable() for character in value)
    ):
        return f"`{value}`"
    return (
        '"'
        + "".join(_quote_character(item, ascii_only=ascii_only) for item in value)
        + '"'
    )


def _quote_rune(value: str, *, ascii_only: bool) -> str:
    return "'" + _quote_character(value, ascii_only=ascii_only, quote="'") + "'"


def _quote_character(
    value: str,
    *,
    ascii_only: bool,
    quote: str = '"',
) -> str:
    escapes = {
        "\a": r"\a",
        "\b": r"\b",
        "\f": r"\f",
        "\n": r"\n",
        "\r": r"\r",
        "\t": r"\t",
        "\v": r"\v",
        "\\": r"\\",
    }
    if value in escapes:
        return escapes[value]
    if value == quote:
        return "\\" + value
    codepoint = ord(value)
    if ascii_only and codepoint > 0x7F:
        if codepoint <= 0xFFFF:
            return f"\\u{codepoint:04x}"
        return f"\\U{codepoint:08x}"
    if value.isprintable():
        return value
    if codepoint <= 0x7F:
        return f"\\x{codepoint:02x}"
    if codepoint <= 0xFFFF:
        return f"\\u{codepoint:04x}"
    return f"\\U{codepoint:08x}"
