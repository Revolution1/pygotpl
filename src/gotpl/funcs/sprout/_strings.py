"""Sprout string registry behavior pinned to v1.1.1."""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import cast

from gotpl._compat.gofmt.go import sprintf
from gotpl.funcs.sprig import generic_func_map
from gotpl.runtime import INVALID, UNTYPED_NIL, FunctionResult

from .registry import TemplateFunction

_SPRIG = generic_func_map()
_NIL_VALUES = (None, UNTYPED_NIL, INVALID)


def _is_nil(value: object) -> bool:
    return any(value is item for item in _NIL_VALUES)


def _go_upper(value: str) -> str:
    return str(_SPRIG["upper"](value))


def _go_lower(value: str) -> str:
    return str(_SPRIG["lower"](value))


def _go_space(character: str) -> bool:
    return character.isspace() and character not in "\x1c\x1d\x1e\x1f"


def _nospace(value: str) -> str:
    return "".join(character for character in value if not _go_space(character))


def _join(separator: str, value: object) -> str:
    if _is_nil(value):
        return ""
    if isinstance(value, (bytes, bytearray)):
        values: tuple[object, ...] | list[object] = list(value)
    elif isinstance(value, (list, tuple)):
        values = cast(list[object] | tuple[object, ...], value)
    else:
        values = [value]
    return separator.join(
        str(_SPRIG["toString"](item)) for item in values if not _is_nil(item)
    )


def _ellipsis(value: str, offset: int, max_width: int) -> str:
    if max_width < 4 or (offset > 0 and max_width < 7):
        return value
    if len(value) <= max_width or len(value) <= offset:
        return value[offset:]
    end = offset + max_width - 3
    if offset > 0:
        end -= 3
        return "..." + value[offset:end] + "..."
    return value[offset:end] + "..."


def _initials(value: str) -> str:
    return "".join(word[0] for word in value.split(" ") if word)


def _word_wrap(
    wrap_length: int,
    newline: str,
    wrap_long_words: bool,
    value: str,
) -> str:
    wrap_length = max(1, wrap_length)
    newline = newline or "\n"
    output: list[str] = []
    current_length = 0
    for word in value.split():
        word_length = len(word)
        if current_length > 0 and current_length + 1 + word_length > wrap_length:
            output.append(newline)
            current_length = 0
        if wrap_long_words and word_length > wrap_length:
            for index, character in enumerate(word):
                output.append(character)
                current_length += 1
                if index < word_length - 1 and current_length == wrap_length:
                    output.append(newline)
                    current_length = 0
        else:
            if current_length > 0:
                output.append(" ")
                current_length += 1
            output.append(word)
            current_length += word_length
    return "".join(output)


def _quote(*values: object) -> str:
    output: list[str] = []
    for index, value in enumerate(values):
        if _is_nil(value):
            continue
        if index > 0:
            output.append(" ")
        output.append(sprintf("%q", sprintf("%v", value)))
    return "".join(output)


def _squote(*values: object) -> str:
    output: list[str] = []
    for index, value in enumerate(values):
        if _is_nil(value):
            continue
        if index > 0:
            output.append(" ")
        output.append("'" + sprintf("%v", value) + "'")
    return "".join(output)


@dataclass(frozen=True, slots=True)
class _CaseStyle:
    separator: str | None
    capitalize_first: bool = False
    capitalize_next: bool = False
    force_lower: bool = False
    force_upper: bool = False


_CAMEL = _CaseStyle(None, capitalize_next=True, force_lower=True)
_KEBAB = _CaseStyle("-", force_lower=True)
_PASCAL = _CaseStyle(
    None, capitalize_first=True, capitalize_next=True, force_lower=True
)
_DOT = _CaseStyle(".", force_lower=True)
_PATH = _CaseStyle("/", force_lower=True)
_CONSTANT = _CaseStyle("_", force_upper=True)
_SNAKE = _CaseStyle("_", force_lower=True)


def _is_upper(character: str) -> bool:
    return character.isupper()


def _is_lower(character: str) -> bool:
    return character.islower()


def _is_content(character: str) -> bool:
    return character.isalpha() or character.isdecimal()


def _transform(style: _CaseStyle, value: str) -> str:
    output: list[str] = []
    capitalize_next = style.capitalize_next if style.capitalize_first else False
    last_rune: str | None = None
    last_letter: str | None = None

    for index, character in enumerate(value):
        next_rune = value[index + 1] if index + 1 < len(value) else ""
        if character in " -_":
            if style.separator is not None and last_rune != style.separator:
                output.append(style.separator)
            if last_letter is not None:
                capitalize_next = True
            last_rune = style.separator
            continue

        if _is_upper(character) and output and last_rune != style.separator:
            if style.separator is not None:
                boundary = bool(
                    (last_rune is not None and _is_lower(last_rune))
                    or (
                        last_rune is not None
                        and _is_upper(last_rune)
                        and bool(next_rune)
                        and _is_lower(next_rune)
                    )
                )
            else:
                boundary = bool(
                    (
                        last_rune is not None
                        and _is_lower(last_rune)
                        and bool(next_rune)
                        and _is_content(next_rune)
                    )
                    or (
                        last_rune is not None
                        and _is_upper(last_rune)
                        and bool(next_rune)
                        and _is_lower(next_rune)
                    )
                )
            if boundary:
                if style.separator is not None:
                    output.append(style.separator)
                capitalize_next = True

        if (
            style.separator is not None
            and output
            and last_rune != style.separator
            and character.isdecimal()
            and (last_rune is None or not last_rune.isdecimal())
        ):
            output.append(style.separator)

        if capitalize_next and style.capitalize_next:
            output.append(_go_upper(character))
            capitalize_next = False
        elif style.force_lower:
            output.append(_go_lower(character))
        elif style.force_upper:
            output.append(_go_upper(character))
        else:
            output.append(character)

        last_rune = character
        if character.isalpha():
            last_letter = character

    return "".join(output)


def _title(value: str) -> str:
    # x/text English title casing treats hyphens and whitespace as boundaries,
    # while underscores remain within a word.
    output: list[str] = []
    word_start = True
    for character in value:
        if word_start and character.isalpha():
            output.append(_go_upper(character))
            word_start = False
        else:
            output.append(_go_lower(character) if character.isalpha() else character)
            if character.isalpha() or character.isdecimal() or character == "_":
                word_start = False
        if _go_space(character) or character == "-":
            word_start = True
    return "".join(output)


def _untitle(value: str) -> str:
    output: list[str] = []
    word_start = True
    for character in value:
        if _go_space(character):
            word_start = True
            output.append(character)
        elif word_start:
            output.append(_go_lower(character))
            word_start = False
        else:
            output.append(character)
    return "".join(output)


def _swap_case(value: str) -> str:
    return "".join(
        _go_upper(character) if _is_lower(character) else _go_lower(character)
        for character in value
    )


def _swap_first_letter(value: str, *, uppercase: bool) -> str:
    for index, character in enumerate(value):
        if not character.isalpha():
            continue
        if uppercase and _is_upper(character):
            return value
        if not uppercase and _is_lower(character):
            return value
        replacement = _go_upper(character) if uppercase else _go_lower(character)
        return value[:index] + replacement + value[index + 1 :]
    return value


def _split_parts(separator: str, count: int | None, value: str) -> list[str]:
    if separator == "":
        parts = list(value)
        if count is not None and count >= 0 and len(parts) > count:
            parts = [*parts[: count - 1], "".join(parts[count - 1 :])]
        return parts
    if count is None or count < 0:
        return value.split(separator)
    if count == 0:
        return []
    return value.split(separator, count - 1)


def _split(separator: str, value: str) -> dict[str, str]:
    return {
        f"_{index}": part
        for index, part in enumerate(_split_parts(separator, None, value))
    }


def _splitn(separator: str, count: int, value: str) -> dict[str, str]:
    return {
        f"_{index}": part
        for index, part in enumerate(_split_parts(separator, count, value))
    }


def _substring(start: int, end: int, value: str) -> str:
    encoded = value.encode()
    length = len(encoded)
    if start < 0:
        start += length
    if end < 0:
        end += length
    start = max(0, start)
    if end > length or end == 0:
        end = length
    if start > end:
        return ""
    return encoded[start:end].decode(errors="replace")


def _seq(*params: int) -> str:
    if not 1 <= len(params) <= 3:
        return ""
    if len(params) == 1:
        start, end = 1, params[0]
        step = -1 if end < start else 1
    elif len(params) == 2:
        start, end = params
        step = -1 if end < start else 1
    else:
        start, step, end = params
        if end < start and step > 0:
            return ""
    if step == 0 or (end > start and step < 0) or (end < start and step > 0):
        return ""
    stop = end + (-1 if end < start else 1)
    return " ".join(str(number) for number in range(start, stop, step))


def _escape(charset: str, value: str) -> str:
    escape_set = set(charset) | {"\\"}
    return "".join(
        ("\\" + character) if character in escape_set else character
        for character in value
    )


def _unescape(charset: str, value: str) -> FunctionResult:
    valid = set(charset) | {"\\"}
    output: list[str] = []
    index = 0
    while index < len(value):
        character = value[index]
        if character != "\\":
            output.append(character)
            index += 1
            continue
        if index + 1 >= len(value):
            return FunctionResult.failure(
                ValueError(
                    "invalid escape sequence: trailing backslash in "
                    + sprintf("%q", value)
                ),
                value="",
            )
        following = value[index + 1]
        if following not in valid:
            return FunctionResult.failure(
                ValueError(
                    f"invalid escape sequence: \\{following} in " + sprintf("%q", value)
                ),
                value="",
            )
        output.append(following)
        index += 2
    return FunctionResult.success("".join(output))


def _shuffle(value: str) -> str:
    runes = list(value)
    random.shuffle(runes)
    return "".join(runes)


def _ellipsis_end(max_width: int, value: str) -> str:
    return _ellipsis(value, 0, max_width)


def _ellipsis_both(offset: int, max_width: int, value: str) -> str:
    return _ellipsis(value, offset, max_width)


def _wrap(wrap_length: int, value: str) -> str:
    return _word_wrap(wrap_length, "", False, value)


def _wrap_with(wrap_length: int, newline: str, value: str) -> str:
    return _word_wrap(wrap_length, newline, True, value)


def _camel_case(value: str) -> str:
    return _transform(_CAMEL, value)


def _kebab_case(value: str) -> str:
    return _transform(_KEBAB, value)


def _pascal_case(value: str) -> str:
    return _transform(_PASCAL, value)


def _dot_case(value: str) -> str:
    return _transform(_DOT, value)


def _path_case(value: str) -> str:
    return _transform(_PATH, value)


def _constant_case(value: str) -> str:
    return _transform(_CONSTANT, value)


def _snake_case(value: str) -> str:
    return _transform(_SNAKE, value)


def _capitalize(value: str) -> str:
    return _swap_first_letter(value, uppercase=True)


def _uncapitalize(value: str) -> str:
    return _swap_first_letter(value, uppercase=False)


def functions() -> dict[str, TemplateFunction]:
    """Return the complete pinned Sprout strings function map."""

    return {
        "nospace": _nospace,
        "trim": _SPRIG["trim"],
        "trimAll": _SPRIG["trimAll"],
        "trimPrefix": _SPRIG["trimPrefix"],
        "trimSuffix": _SPRIG["trimSuffix"],
        "contains": _SPRIG["contains"],
        "hasPrefix": _SPRIG["hasPrefix"],
        "hasSuffix": _SPRIG["hasSuffix"],
        "toLower": _SPRIG["lower"],
        "toUpper": _SPRIG["upper"],
        "replace": _SPRIG["replace"],
        "repeat": _SPRIG["repeat"],
        "join": _join,
        "trunc": _SPRIG["trunc"],
        "shuffle": _shuffle,
        "ellipsis": _ellipsis_end,
        "ellipsisBoth": _ellipsis_both,
        "initials": _initials,
        "plural": _SPRIG["plural"],
        "wrap": _wrap,
        "wrapWith": _wrap_with,
        "quote": _quote,
        "squote": _squote,
        "toCamelCase": _camel_case,
        "toKebabCase": _kebab_case,
        "toPascalCase": _pascal_case,
        "toDotCase": _dot_case,
        "toPathCase": _path_case,
        "toConstantCase": _constant_case,
        "toSnakeCase": _snake_case,
        "toTitleCase": _title,
        "untitle": _untitle,
        "swapCase": _swap_case,
        "capitalize": _capitalize,
        "uncapitalize": _uncapitalize,
        "split": _split,
        "splitn": _splitn,
        "substr": _substring,
        "indent": _SPRIG["indent"],
        "nindent": _SPRIG["nindent"],
        "seq": _seq,
        "escape": _escape,
        "unescape": _unescape,
    }
