"""Sprig regular-expression helpers with Go replacement semantics."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from functools import lru_cache

from ._engine import (
    AtomicPattern,
    LinearMatch,
    LinearPattern,
    compile_pattern,
)
from ._unicode_properties import property_class_contents
from .types import DEFAULT_LIMITS, Limits

_META_CHARACTERS = frozenset(r"\.+*?()|[]{}^$")
_UNSUPPORTED_PATTERNS = ("(?=", "(?!", "(?<=", "(?<!", "(?>", "(?(")
_ASCII_CLASS_CONTENTS = {
    "d": "0-9",
    "D": r"\x00-/:-\U0010ffff",
    "s": r"\t\n\f\r ",
    "S": r"\x00-\x08\x0b\x0e-\x1f!-\U0010ffff",
    "w": "0-9A-Za-z_",
    "W": r"\x00-/:-@[-^`{-\U0010ffff",
}
_POSIX_CLASSES = {
    "alnum": "A-Za-z0-9",
    "alpha": "A-Za-z",
    "ascii": r"\x00-\x7F",
    "blank": r"\t ",
    "cntrl": r"\x00-\x1F\x7F",
    "digit": "0-9",
    "graph": r"\x21-\x7E",
    "lower": "a-z",
    "print": r"\x20-\x7E",
    "punct": r"!-/:-@[-`{-~",
    "space": r"\t\n\v\f\r ",
    "upper": "A-Z",
    "word": "A-Za-z0-9_",
    "xdigit": "A-Fa-f0-9",
}


class RegexpError(ValueError):
    """Report invalid RE2 syntax or an explicit compilation limit."""


@dataclass(frozen=True, slots=True)
class Pattern:
    """Immutable compiled expression for the adopted Go RE2 subset."""

    source: str
    limits: Limits = DEFAULT_LIMITS
    _compiled: AtomicPattern | LinearPattern = field(
        init=False, repr=False, compare=False
    )

    def __post_init__(self) -> None:
        if not isinstance(  # pyright: ignore[reportUnnecessaryIsInstance]
            self.source, str
        ):
            raise TypeError("pattern must be a string")
        if len(self.source) > self.limits.max_pattern_length:
            raise RegexpError("pattern exceeds max_pattern_length")
        try:
            _validate_repeat_counts(
                self.source,
                self.limits.max_repeat_count,
                error_message="pattern exceeds max_repeat_count",
            )
            compiled = compile_pattern(_translate_and_validate(self.source))
        except re.error as error:
            raise RegexpError(str(error)) from error
        instruction_count = (
            compiled.instruction_count if isinstance(compiled, LinearPattern) else 1
        )
        if instruction_count > self.limits.max_program_instructions:
            raise RegexpError("pattern exceeds max_program_instructions")
        capture_count = compiled.groups if isinstance(compiled, LinearPattern) else 0
        if capture_count > self.limits.max_captures:
            raise RegexpError("pattern exceeds max_captures")
        object.__setattr__(self, "_compiled", compiled)

    @property
    def backend(self) -> str:
        """Return the audited execution backend name."""
        return self._compiled.backend

    def matches(self, value: str) -> bool:
        """Return whether the expression occurs in *value*."""
        return self._compiled.search(value) is not None

    def find(self, value: str) -> str:
        """Return the first full match or Go's empty-string sentinel."""
        match = self._compiled.search(value)
        return "" if match is None else match.group(0) or ""

    def find_all(self, value: str, count: int = -1) -> list[str] | None:
        """Return Go full matches, or ``None`` when no match/count is zero."""
        if count == 0:
            return None
        matches = [
            match.group(0) or "" for match in _go_matches(self._compiled, value, count)
        ]
        return matches or None

    def find_groups(self, value: str) -> list[str]:
        """Return the first full match and captures required by Sprout."""

        match = self._compiled.search(value)
        return [] if match is None else _match_groups(match, self._group_count)

    def find_all_groups(self, value: str, count: int = -1) -> list[list[str]]:
        """Return full matches and captures, honoring Go's count convention."""

        if count == 0:
            return []
        return [
            _match_groups(match, self._group_count)
            for match in _go_matches(self._compiled, value, count)
        ]

    def find_named(self, value: str) -> dict[str, str]:
        """Return named captures from the first match required by Sprout."""

        match = self._compiled.search(value)
        return {} if match is None else _match_named(match)

    def find_all_named(self, value: str, count: int = -1) -> list[dict[str, str]]:
        """Return named captures for each match required by Sprout."""

        if count == 0:
            return []
        return [
            _match_named(match) for match in _go_matches(self._compiled, value, count)
        ]

    def replace_all(self, value: str, replacement: str) -> str:
        """Replace matches with Go dollar-expansion semantics."""
        return _replace_matches(
            self._compiled,
            value,
            lambda match: _expand_replacement(match, replacement),
        )

    def replace_all_literal(self, value: str, replacement: str) -> str:
        """Replace matches with literal text."""
        return _replace_matches(self._compiled, value, lambda _match: replacement)

    def split(self, value: str, count: int = -1) -> list[str]:
        """Split without exposing capture groups, following Go count rules."""
        return _split(self._compiled, value, count)

    @property
    def _group_count(self) -> int:
        return self._compiled.groups if isinstance(self._compiled, LinearPattern) else 0


def compile(pattern: str, *, limits: Limits = DEFAULT_LIMITS) -> Pattern:
    """Compile an adopted Go-compatible RE2 expression."""
    return Pattern(pattern, limits)


def quote_meta(value: str) -> str:
    """Escape Go regexp metacharacters in literal text."""
    return regex_quote_meta(value)


def regex_match(pattern: str, value: str) -> bool:
    try:
        return _compile(pattern).search(value) is not None
    except re.error:
        return False


def regex_find_all(pattern: str, value: str, count: int) -> list[str] | None:
    if count == 0:
        return None
    matches = [
        match.group(0) or "" for match in _go_matches(_compile(pattern), value, count)
    ]
    return matches or None


def regex_find(pattern: str, value: str) -> str:
    match = _compile(pattern).search(value)
    return "" if match is None else match.group(0) or ""


def regex_replace_all(pattern: str, value: str, replacement: str) -> str:
    compiled = _compile(pattern)
    return _replace_matches(
        compiled, value, lambda match: _expand_replacement(match, replacement)
    )


def regex_replace_all_literal(pattern: str, value: str, replacement: str) -> str:
    return _replace_matches(_compile(pattern), value, lambda _match: replacement)


def regex_split(pattern: str, value: str, count: int) -> list[str]:
    return _split(_compile(pattern), value, count)


def regex_quote_meta(value: str) -> str:
    return "".join("\\" + char if char in _META_CHARACTERS else char for char in value)


@lru_cache(maxsize=256)
def _compile(pattern: str) -> AtomicPattern | LinearPattern:
    return compile_pattern(_translate_and_validate(pattern))


def _translate_and_validate(pattern: str) -> str:
    if any(token in pattern for token in _UNSUPPORTED_PATTERNS) or re.search(
        r"\\[89Z]", pattern
    ):
        raise re.error("invalid or unsupported Perl syntax")
    _validate_repeat_counts(pattern)
    return _translate_re2(pattern)


def _validate_repeat_counts(
    pattern: str,
    maximum_allowed: int = 1_000,
    *,
    error_message: str = "invalid repeat count",
) -> None:
    in_class = False
    index = 0
    while index < len(pattern):
        character = pattern[index]
        if character == "\\":
            if pattern.startswith(r"\x{", index):
                closing = pattern.find("}", index + 3)
                index = len(pattern) if closing < 0 else closing + 1
                continue
            index += 2
            continue
        if character == "[":
            in_class = True
        elif character == "]":
            in_class = False
        elif character == "{" and not in_class:
            match = re.match(r"\{(\d+)(?:,(\d*))?\}", pattern[index:])
            if match is not None:
                upper_text = match.group(2)
                counts = [int(match.group(1))]
                if upper_text:
                    counts.append(int(upper_text))
                if any(count > maximum_allowed for count in counts):
                    raise re.error(error_message)
                index += len(match.group(0))
                continue
        index += 1


def _translate_re2(pattern: str) -> str:
    for name, characters in _POSIX_CLASSES.items():
        pattern = pattern.replace(f"[[:{name}:]]", f"[{characters}]")
        pattern = pattern.replace(f"[[:^{name}:]]", f"[^{characters}]")
    pattern = _translate_quoted_literals(pattern)
    pattern = _translate_flag_scopes(pattern)
    pattern = _translate_unicode_properties(pattern)
    pattern = pattern.replace("(?<", "(?P<")
    output: list[str] = []
    in_class = False
    index = 0
    while index < len(pattern):
        character = pattern[index]
        if character == "\\" and index + 1 < len(pattern):
            escaped = pattern[index + 1]
            if escaped in _ASCII_CLASS_CONTENTS:
                contents = _ASCII_CLASS_CONTENTS[escaped]
                output.append(contents if in_class else f"[{contents}]")
            elif escaped in {"b", "B"} and not in_class:
                output.append(f"(?a:\\{escaped})")
            elif escaped == "z":
                output.append(r"\Z")
            elif (
                escaped == "x"
                and index + 2 < len(pattern)
                and pattern[index + 2] == "{"
            ):
                end = pattern.find("}", index + 3)
                if end < 0:
                    raise re.error("invalid hexadecimal escape")
                digits = pattern[index + 3 : end]
                if not digits or not all(
                    char in "0123456789abcdefABCDEF" for char in digits
                ):
                    raise re.error("invalid hexadecimal escape")
                codepoint = int(digits, 16)
                if codepoint > 0x10FFFF:
                    raise re.error("invalid hexadecimal escape")
                output.append(re.escape(chr(codepoint)))
                index = end + 1
                continue
            elif escaped in "01234567":
                end = index + 1
                while end < min(index + 4, len(pattern)) and pattern[end] in "01234567":
                    end += 1
                if end != index + 4:
                    raise re.error("invalid escape sequence")
                codepoint = int(pattern[index + 1 : end], 8)
                output.append(re.escape(chr(codepoint)))
                index = end
                continue
            else:
                output.append(character + escaped)
            index += 2
            continue
        if character == "[":
            in_class = True
        elif character == "]" and in_class:
            in_class = False
        output.append(character)
        index += 1
    return "".join(output)


def _translate_flag_scopes(pattern: str) -> str:
    translated, position = _translate_flag_sequence(pattern, 0, frozenset())
    if position != len(pattern):
        raise re.error("unexpected closing parenthesis")
    return translated


def _translate_unicode_properties(pattern: str) -> str:
    output: list[str] = []
    position = 0
    while position < len(pattern):
        if pattern[position] == "[":
            end = _character_class_end(pattern, position)
            output.append(_translate_unicode_class(pattern[position:end]))
            position = end
            continue
        if pattern.startswith((r"\p", r"\P"), position):
            contents, position = _unicode_property_escape(pattern, position)
            output.append(f"[{contents}]" if contents else "(?!)")
            continue
        if pattern[position] == "\\":
            output.append(pattern[position : position + 2])
            position += 2
            continue
        output.append(pattern[position])
        position += 1
    return "".join(output)


def _translate_unicode_class(character_class: str) -> str:
    negated = character_class.startswith("[^")
    body_start = 2 if negated else 1
    body = character_class[body_start:-1]
    output: list[str] = []
    position = 0
    while position < len(body):
        if body.startswith((r"\p", r"\P"), position):
            contents, position = _unicode_property_escape(body, position)
            output.append(contents)
            continue
        output.append(
            body[position : position + 2] if body[position] == "\\" else body[position]
        )
        position += 2 if body[position] == "\\" else 1
    contents = "".join(output)
    if not contents:
        return "[\\u0000-\\U0010ffff]" if negated else "(?!)"
    return f"[{'^' if negated else ''}{contents}]"


def _unicode_property_escape(pattern: str, position: int) -> tuple[str, int]:
    negate = pattern[position + 1] == "P"
    name_start = position + 2
    if name_start >= len(pattern):
        raise re.error("invalid Unicode class")
    if pattern[name_start] == "{":
        end = pattern.find("}", name_start + 1)
        if end < 0:
            raise re.error("invalid Unicode class")
        name = pattern[name_start + 1 : end]
        position = end + 1
    else:
        name = pattern[name_start]
        position = name_start + 1
    if name.startswith("^"):
        negate = not negate
        name = name[1:]
    if not name:
        raise re.error("invalid Unicode class")
    try:
        return property_class_contents(name, negate=negate), position
    except ValueError as error:
        raise re.error(str(error)) from error


def _translate_flag_sequence(
    pattern: str,
    position: int,
    active_flags: frozenset[str],
    *,
    stop_at_close: bool = False,
) -> tuple[str, int]:
    output: list[str] = []
    while position < len(pattern):
        character = pattern[position]
        if character == "\\":
            output.append(pattern[position : position + 2])
            position += 2
            continue
        if character == "[":
            end = _character_class_end(pattern, position)
            output.append(pattern[position:end])
            position = end
            continue
        if character == ")":
            if stop_at_close:
                return "".join(output), position + 1
            return "".join(output), position
        if character == "(":
            group, position = _translate_flag_group(pattern, position, active_flags)
            output.append(group)
            continue
        if character == "$" and "m" not in active_flags:
            output.append(r"\Z")
            position += 1
            continue
        if character in "*+?":
            lazy = position + 1 < len(pattern) and pattern[position + 1] == "?"
            output.append(character)
            if ("U" in active_flags) != lazy:
                output.append("?")
            position += 2 if lazy else 1
            continue
        if character == "{":
            repeat = re.match(r"\{\d+(?:,\d*)?\}", pattern[position:])
            if repeat is not None:
                token = repeat.group(0)
                end = position + len(token)
                lazy = end < len(pattern) and pattern[end] == "?"
                output.append(token)
                if ("U" in active_flags) != lazy:
                    output.append("?")
                position = end + 1 if lazy else end
                continue
        output.append(character)
        position += 1
    if stop_at_close:
        raise re.error("missing closing parenthesis")
    return "".join(output), position


def _translate_flag_group(
    pattern: str,
    position: int,
    active_flags: frozenset[str],
) -> tuple[str, int]:
    if pattern.startswith("(?:", position):
        return _translate_nested_group(pattern, position + 3, "(?:", active_flags)
    for marker in ("(?P<", "(?<"):
        if pattern.startswith(marker, position):
            name_end = pattern.find(">", position + len(marker))
            if name_end < 0:
                raise re.error("invalid named capture")
            prefix = pattern[position : name_end + 1]
            return _translate_nested_group(pattern, name_end + 1, prefix, active_flags)
    flag_match = re.match(r"\(\?([imsU]*)(?:-([imsU]+))?([:)])", pattern[position:])
    if flag_match is not None and (flag_match.group(1) or flag_match.group(2)):
        enabled = flag_match.group(1)
        disabled = flag_match.group(2) or ""
        updated = _updated_flags(active_flags, enabled, disabled)
        body_start = position + len(flag_match.group(0))
        if flag_match.group(3) == ":":
            body, end = _translate_flag_sequence(
                pattern, body_start, updated, stop_at_close=True
            )
            return _python_flag_scope(enabled, disabled, body), end
        body, end = _translate_flag_sequence(
            pattern, body_start, updated, stop_at_close=False
        )
        return _python_flag_remainder(enabled, disabled, body), end
    if pattern.startswith("(?", position):
        raise re.error("invalid or unsupported Perl syntax")
    return _translate_nested_group(pattern, position + 1, "(", active_flags)


def _translate_nested_group(
    pattern: str,
    body_start: int,
    prefix: str,
    active_flags: frozenset[str],
) -> tuple[str, int]:
    body, end = _translate_flag_sequence(
        pattern, body_start, active_flags, stop_at_close=True
    )
    return prefix + body + ")", end


def _updated_flags(
    active: frozenset[str], enabled: str, disabled: str
) -> frozenset[str]:
    result = set(active)
    result.update(enabled)
    result.difference_update(disabled)
    return frozenset(result)


def _python_flag_scope(enabled: str, disabled: str, body: str) -> str:
    python_enabled = enabled.replace("U", "")
    python_disabled = disabled.replace("U", "")
    if not python_enabled and not python_disabled:
        return f"(?:{body})"
    separator = "-" if python_disabled else ""
    return f"(?{python_enabled}{separator}{python_disabled}:{body})"


def _python_flag_remainder(enabled: str, disabled: str, body: str) -> str:
    if enabled == "U" and not disabled:
        return body
    alternatives = _split_top_level_alternatives(body)
    return "|".join(
        _python_flag_scope(enabled, disabled, alternative)
        for alternative in alternatives
    )


def _split_top_level_alternatives(pattern: str) -> list[str]:
    alternatives: list[str] = []
    beginning = 0
    depth = 0
    position = 0
    while position < len(pattern):
        character = pattern[position]
        if character == "\\":
            position += 2
            continue
        if character == "[":
            position = _character_class_end(pattern, position)
            continue
        if character == "(":
            depth += 1
        elif character == ")":
            depth -= 1
        elif character == "|" and depth == 0:
            alternatives.append(pattern[beginning:position])
            beginning = position + 1
        position += 1
    alternatives.append(pattern[beginning:])
    return alternatives


def _character_class_end(pattern: str, position: int) -> int:
    position += 1
    while position < len(pattern):
        if pattern[position] == "\\":
            position += 2
        elif pattern[position] == "]":
            return position + 1
        else:
            position += 1
    raise re.error("missing closing bracket")


def _translate_quoted_literals(pattern: str) -> str:
    output: list[str] = []
    position = 0
    while True:
        start = pattern.find(r"\Q", position)
        if start < 0:
            output.append(pattern[position:])
            return "".join(output)
        end = pattern.find(r"\E", start + 2)
        if end < 0:
            raise re.error("invalid escape sequence")
        output.append(pattern[position:start])
        output.append(re.escape(pattern[start + 2 : end]))
        position = end + 2


def _go_matches(
    compiled: AtomicPattern | LinearPattern, value: str, count: int = -1
) -> list[LinearMatch]:
    matches: list[LinearMatch] = []
    previous_end = -1
    for match in compiled.finditer(value):
        empty = match.start() == match.end()
        if not (empty and match.start() == previous_end):
            matches.append(match)
            if count >= 0 and len(matches) >= count:
                break
        previous_end = match.end()
    return matches


def _match_groups(match: LinearMatch, group_count: int) -> list[str]:
    return [(match.group(index) or "") for index in range(group_count + 1)]


def _match_named(match: LinearMatch) -> dict[str, str]:
    return {
        name: match.group(name) or ""
        for name, _index in sorted(match.group_names.items(), key=lambda item: item[1])
    }


def _replace_matches(
    compiled: AtomicPattern | LinearPattern,
    value: str,
    replacement: Callable[[LinearMatch], str],
) -> str:
    output: list[str] = []
    position = 0
    for match in _go_matches(compiled, value):
        output.append(value[position : match.start()])
        output.append(replacement(match))
        position = match.end()
    output.append(value[position:])
    return "".join(output)


def _split(
    compiled: AtomicPattern | LinearPattern, value: str, count: int
) -> list[str]:
    if count == 0:
        return []
    if count == 1:
        return [value]
    result: list[str] = []
    beginning = 0
    end = 0
    for match in _go_matches(compiled, value, count):
        if count > 0 and len(result) >= count - 1:
            break
        end = match.start()
        if match.end() != 0:
            result.append(value[beginning:end])
        beginning = match.end()
    if end != len(value):
        result.append(value[beginning:])
    return result


def _expand_replacement(match: LinearMatch, replacement: str) -> str:
    output: list[str] = []
    index = 0
    while index < len(replacement):
        if replacement[index] != "$":
            output.append(replacement[index])
            index += 1
            continue
        if index + 1 < len(replacement) and replacement[index + 1] == "$":
            output.append("$")
            index += 2
            continue
        name, end = _replacement_name(replacement, index + 1)
        if name is None:
            output.append("$")
            index += 1
            continue
        try:
            captured = match.group(int(name) if name.isdigit() else name)
        except (IndexError, KeyError):
            captured = ""
        output.append(captured or "")
        index = end
    return "".join(output)


def _replacement_name(value: str, start: int) -> tuple[str | None, int]:
    if start < len(value) and value[start] == "{":
        end = value.find("}", start + 1)
        if end < 0:
            return None, start
        return value[start + 1 : end], end + 1
    end = start
    while end < len(value) and (value[end].isalnum() or value[end] == "_"):
        end += 1
    return (value[start:end], end) if end > start else (None, start)
