"""Deterministic Sprig string, encoding, digest, and path functions."""

from __future__ import annotations

import base64
import hashlib
import os.path
import posixpath
import unicodedata
import zlib
from typing import cast

from gotpl.runtime import INVALID, UNTYPED_NIL
from gotpl.runtime.gofmt import sprintf


def hello() -> str:
    return "Hello!"


def trim(value: str) -> str:
    start = 0
    end = len(value)
    while start < end and _go_is_space(value[start]):
        start += 1
    while end > start and _go_is_space(value[end - 1]):
        end -= 1
    return value[start:end]


def upper(value: str) -> str:
    return "".join(_go_simple_upper(character) for character in value)


def lower(value: str) -> str:
    return "".join(_go_simple_lower(character) for character in value)


def repeat(count: int, value: str) -> str:
    if count < 0:
        raise ValueError("strings: negative Repeat count")
    return value * count


def trim_all(cutset: str, value: str) -> str:
    return value.strip(cutset)


def trim_suffix(suffix: str, value: str) -> str:
    return value.removesuffix(suffix)


def trim_prefix(prefix: str, value: str) -> str:
    return value.removeprefix(prefix)


def contains(substring: str, value: str) -> bool:
    return substring in value


def has_prefix(prefix: str, value: str) -> bool:
    return value.startswith(prefix)


def has_suffix(suffix: str, value: str) -> bool:
    return value.endswith(suffix)


def indent(spaces: int, value: str) -> str:
    if spaces < 0:
        raise ValueError("strings: negative Repeat count")
    padding = " " * spaces
    return padding + value.replace("\n", "\n" + padding)


def nindent(spaces: int, value: str) -> str:
    return "\n" + indent(spaces, value)


def replace(old: str, new: str, value: str) -> str:
    return value.replace(old, new)


def plural(one: str, many: str, count: int) -> str:
    return one if count == 1 else many


def to_string(value: object) -> str:
    if value is None:
        return "<nil>"
    if isinstance(value, (bytes, bytearray)):
        return bytes(value).decode(errors="replace")
    return sprintf("%v", value)


def to_strings(value: object) -> list[str]:
    if value is None or value is UNTYPED_NIL or value is INVALID:
        return []
    if isinstance(value, (bytes, bytearray, list, tuple)):
        sequence = cast(bytes | bytearray | list[object] | tuple[object, ...], value)
        return [
            to_string(item)
            for item in sequence
            if item is not None and item is not UNTYPED_NIL and item is not INVALID
        ]
    return [to_string(value)]


def join(separator: str, value: object) -> str:
    return separator.join(to_strings(value))


def sort_alpha(value: object) -> list[str]:
    if value is None or value is UNTYPED_NIL or value is INVALID:
        return [to_string(value)]
    return sorted(to_strings(value))


def substring(start: int, end: int, value: str) -> str:
    encoded = value.encode()
    if start < 0:
        if not 0 <= end <= len(encoded):
            raise IndexError("slice bounds out of range")
        selected = encoded[:end]
    elif end < 0 or end > len(encoded):
        if not 0 <= start <= len(encoded):
            raise IndexError("slice bounds out of range")
        selected = encoded[start:]
    else:
        if not 0 <= start <= end:
            raise IndexError("slice bounds out of range")
        selected = encoded[start:end]
    return selected.decode(errors="replace")


def trunc(count: int, value: str) -> str:
    encoded = value.encode()
    if count < 0 and len(encoded) + count > 0:
        encoded = encoded[len(encoded) + count :]
    elif count >= 0 and len(encoded) > count:
        encoded = encoded[:count]
    return encoded.decode(errors="replace")


def quote(*values: object) -> str:
    return " ".join(
        sprintf("%q", to_string(value))
        for value in values
        if value is not None and value is not UNTYPED_NIL and value is not INVALID
    )


def squote(*values: object) -> str:
    return " ".join(
        "'" + sprintf("%v", value) + "'"
        for value in values
        if value is not None and value is not UNTYPED_NIL and value is not INVALID
    )


def cat(*values: object) -> str:
    return " ".join(
        sprintf("%v", value)
        for value in values
        if value is not None and value is not UNTYPED_NIL and value is not INVALID
    )


def split(separator: str, value: str) -> dict[str, str]:
    return {f"_{index}": item for index, item in enumerate(_split(separator, value))}


def splitn(separator: str, count: int, value: str) -> dict[str, str]:
    if count == 0:
        return {}
    return {
        f"_{index}": item
        for index, item in enumerate(_split(separator, value, count=count))
    }


def split_list(separator: str, value: str) -> list[str]:
    return _split(separator, value)


def nospace(value: str) -> str:
    return "".join(
        character for byte in value.encode() if not _go_is_space(character := chr(byte))
    )


def initials(value: str) -> str:
    output: list[str] = []
    last_was_gap = True
    for byte in value.encode():
        character = chr(byte)
        if _go_is_space(character):
            last_was_gap = True
        elif last_was_gap:
            output.append(character)
            last_was_gap = False
    return "".join(output)


def title(value: str) -> str:
    output: list[str] = []
    previous = " "
    for character in value:
        output.append(
            _go_simple_title(character) if _go_title_separator(previous) else character
        )
        previous = character
    return "".join(output)


def untitle(value: str) -> str:
    output: list[str] = []
    uncapitalize_next = True
    for character in value:
        if _go_is_space(character):
            uncapitalize_next = True
            output.append(character)
        elif uncapitalize_next:
            output.append(_go_simple_lower(character))
            uncapitalize_next = False
        else:
            output.append(character)
    return "".join(output)


def swapcase(value: str) -> str:
    output: list[str] = []
    whitespace = True
    for character in value:
        if character.isupper() or character.istitle():
            output.append(_go_simple_lower(character))
            whitespace = False
        elif character.islower():
            output.append(
                _go_simple_title(character)
                if whitespace
                else _go_simple_upper(character)
            )
            whitespace = False
        else:
            output.append(character)
            whitespace = _go_is_space(character)
    return "".join(output)


def _go_simple_upper(character: str) -> str:
    mapped = character.upper()
    if len(mapped) == 1:
        return mapped
    codepoint = ord(character)
    for start in (0x1F80, 0x1F90, 0x1FA0):
        if start <= codepoint <= start + 7:
            return chr(codepoint + 8)
    return {"ᾳ": "ᾼ", "ῃ": "ῌ", "ῳ": "ῼ"}.get(character, character)


def _go_simple_lower(character: str) -> str:
    mapped = character.lower()
    if len(mapped) == 1:
        return mapped
    return "i" if character == "İ" else character


def _go_simple_title(character: str) -> str:
    mapped = character.title()
    return mapped if len(mapped) == 1 else character


def _go_title_separator(character: str) -> bool:
    if ord(character) <= 0x7F:
        return not (character.isascii() and (character.isalnum() or character == "_"))
    if character.isalpha() or character.isdecimal():
        return False
    return _go_is_space(character)


def _go_is_space(character: str) -> bool:
    return character.isspace() and character not in "\x1c\x1d\x1e\x1f"


def snakecase(value: str) -> str:
    return _separated_case(value, "_")


def kebabcase(value: str) -> str:
    return _separated_case(value, "-")


def camelcase(value: str) -> str:
    if not value:
        return ""
    output: list[str] = []
    index = 0
    while index < len(value) and _is_connector(value[index]):
        output.append(value[index])
        index += 1
    if index == len(value):
        output.append(value[-1])
        return "".join(output)
    current = value[index]
    first_rune_upper = current.isupper()
    current = _go_simple_upper(current)
    index += 1
    if index == len(value):
        output.append(current)
        return "".join(output)
    while index < len(value):
        previous = current
        current = value[index]
        index += 1
        if _is_connector(current) and _is_connector(previous):
            output.append(previous)
            continue
        if _is_connector(previous):
            first_rune_upper = current.isupper()
            current = _go_simple_upper(current)
        else:
            if first_rune_upper:
                if current.isupper():
                    current = _go_simple_lower(current)
                else:
                    first_rune_upper = False
            output.append(previous)
    output.append(current)
    return "".join(output)


def abbrev(width: int, value: str) -> str:
    encoded = value.encode()
    if width < 4 or len(encoded) <= width:
        return value
    return (encoded[: width - 3] + b"...").decode(errors="replace")


def abbrevboth(left: int, right: int, value: str) -> str:
    encoded = value.encode()
    if right < 4 or (left > 0 and right < 7) or len(encoded) <= right:
        return value
    if left <= 4:
        return abbrev(right, value)
    if len(encoded) - left < right - 3:
        left = len(encoded) - (right - 3)
    if left + right - 3 < len(encoded):
        tail = abbrev(right - 3, encoded[left:].decode(errors="replace"))
        return "..." + tail
    return (b"..." + encoded[-(right - 3) :]).decode(errors="replace")


def wrap(width: int, value: str) -> str:
    return _wrap(width, "\n", value, break_long_words=False)


def wrap_with(width: int, separator: str, value: str) -> str:
    return _wrap(width, separator or "\n", value, break_long_words=True)


def _split(separator: str, value: str, *, count: int = -1) -> list[str]:
    if separator:
        return value.split(separator, count - 1 if count > 0 else -1)
    characters = list(value)
    if count <= 0 or len(characters) <= count:
        return characters
    return [*characters[: count - 1], "".join(characters[count - 1 :])]


def _separated_case(value: str, separator: str) -> str:
    words = _case_words(value)
    if not words:
        return ""
    output: list[str] = []
    index = 0
    word_type, word = words[index]
    while index + 1 < len(words):
        if word_type != _CONNECTOR_WORD:
            output.append(_lower_case_word(word_type, word, separator))
        previous = word_type
        previous_word = word
        index += 1
        word_type, word = words[index]
        if previous == _NUMBER_WORD:
            while word_type in {_ALPHABET_WORD, _NUMBER_WORD}:
                output.append(_lower_case_word(word_type, word, separator))
                index += 1
                if index >= len(words):
                    return "".join(output)
                word_type, word = words[index]
            if word_type not in {
                _INVALID_WORD,
                _PUNCT_WORD,
                _CONNECTOR_WORD,
            }:
                output.append(separator)
        elif previous == _CONNECTOR_WORD:
            output.append(_lower_case_word(previous, previous_word, separator))
        elif previous != _PUNCT_WORD:
            if word_type != _NUMBER_WORD:
                if word_type not in {_CONNECTOR_WORD, _PUNCT_WORD}:
                    output.append(separator)
                continue
            if index + 1 >= len(words):
                continue
            number_word = word
            index += 1
            word_type, word = words[index]
            if word_type != _ALPHABET_WORD:
                output.append(_lower_case_word(_NUMBER_WORD, number_word, separator))
                if word_type not in {_CONNECTOR_WORD, _PUNCT_WORD}:
                    output.append(separator)
                continue
            output.append(separator)
            output.append(_lower_case_word(_NUMBER_WORD, number_word, separator))
            while word_type in {_ALPHABET_WORD, _NUMBER_WORD}:
                output.append(_lower_case_word(word_type, word, separator))
                index += 1
                if index >= len(words):
                    return "".join(output)
                word_type, word = words[index]
            if word_type not in {
                _INVALID_WORD,
                _CONNECTOR_WORD,
                _PUNCT_WORD,
            }:
                output.append(separator)
    output.append(_lower_case_word(word_type, word, separator))
    return "".join(output)


_INVALID_WORD = 0
_NUMBER_WORD = 1
_UPPER_WORD = 2
_ALPHABET_WORD = 3
_CONNECTOR_WORD = 4
_PUNCT_WORD = 5
_OTHER_WORD = 6


def _case_words(value: str) -> list[tuple[int, str]]:
    words: list[tuple[int, str]] = []
    encoded = value.encode()
    start = 0
    while start < len(encoded):
        character, size = _next_valid_rune(encoded, start, "\ufffd")
        consumed = size
        if _is_connector(character):
            kind = _CONNECTOR_WORD
            while start + consumed < len(encoded):
                following, size = _next_valid_rune(encoded, start + consumed, character)
                if not _is_connector(following):
                    break
                consumed += size
        elif _is_punctuation(character):
            kind = _PUNCT_WORD
            while start + consumed < len(encoded):
                following, size = _next_valid_rune(encoded, start + consumed, character)
                if not _is_punctuation(following):
                    break
                consumed += size
        elif character.isupper():
            kind = _UPPER_WORD
            if start + consumed < len(encoded):
                following, size = _next_valid_rune(encoded, start + consumed, character)
            else:
                following, size = character, 0
            if size and following.isupper():
                previous_size = size
                consumed += size
                while start + consumed < len(encoded):
                    following, size = _next_valid_rune(
                        encoded, start + consumed, following
                    )
                    if not following.isupper():
                        break
                    previous_size = size
                    consumed += size
                if start + consumed < len(encoded) and _is_alphabet(following):
                    consumed -= previous_size
            elif size and _is_alphabet(following):
                consumed += size
                while start + consumed < len(encoded):
                    following, size = _next_valid_rune(
                        encoded, start + consumed, following
                    )
                    if not _is_alphabet(following) or following.isupper():
                        break
                    consumed += size
        elif _is_alphabet(character):
            kind = _ALPHABET_WORD
            while start + consumed < len(encoded):
                following, size = _next_valid_rune(encoded, start + consumed, character)
                if not _is_alphabet(following) or following.isupper():
                    break
                consumed += size
        elif _is_number(character):
            kind = _NUMBER_WORD
            while start + consumed < len(encoded):
                following, size = _next_valid_rune(encoded, start + consumed, character)
                if not _is_number(following):
                    break
                consumed += size
        else:
            kind = _INVALID_WORD if character == "\ufffd" else _OTHER_WORD
            if kind == _OTHER_WORD:
                while start + consumed < len(encoded):
                    following, size = _next_valid_rune(
                        encoded, start + consumed, character
                    )
                    if (
                        _is_connector(following)
                        or _is_alphabet(following)
                        or _is_number(following)
                        or _is_punctuation(following)
                    ):
                        break
                    consumed += size
        end = start + consumed
        words.append((kind, encoded[start:end].decode(errors="replace")))
        start = end
    return words


def _next_valid_rune(encoded: bytes, offset: int, previous: str) -> tuple[str, int]:
    size = 0
    while offset + size < len(encoded):
        first = encoded[offset + size]
        rune_size = (
            1 if first < 0x80 else 2 if first < 0xE0 else 3 if first < 0xF0 else 4
        )
        character = encoded[offset + size : offset + size + rune_size].decode()
        size += rune_size
        if character != "\ufffd":
            return character, size
    return previous, size


def _lower_case_word(kind: int, value: str, separator: str) -> str:
    if kind not in {_UPPER_WORD, _CONNECTOR_WORD}:
        return value
    return "".join(
        separator
        if _is_connector(character)
        else _go_simple_lower(character)
        if character.isupper()
        else character
        for character in value
    )


def _is_connector(character: str) -> bool:
    return character in "-_" or _go_is_space(character)


def _is_punctuation(character: str) -> bool:
    return unicodedata.category(character).startswith("P")


def _is_number(character: str) -> bool:
    return unicodedata.category(character).startswith("N")


def _is_alphabet(character: str) -> bool:
    if not character.isalpha():
        return False
    codepoint = ord(character)
    return not (
        0x4E00 <= codepoint <= 0x9FCC
        or 0x3400 <= codepoint <= 0x4D85
        or 0x20000 <= codepoint <= 0x2B81D
    )


def _wrap(width: int, separator: str, value: str, *, break_long_words: bool) -> str:
    if not value:
        return ""
    width = max(width, 1)
    encoded = value.encode()
    separator_bytes = separator.encode()
    offset = 0
    output = bytearray()
    while len(encoded) - offset > width:
        if encoded[offset] == 0x20:
            offset += 1
            continue
        end = width + offset + 1
        space = encoded.rfind(b" ", offset, end)
        if space >= offset:
            output.extend(encoded[offset:space])
            output.extend(separator_bytes)
            offset = space + 1
            continue
        if break_long_words:
            end = width + offset
            output.extend(encoded[offset:end])
            output.extend(separator_bytes)
            offset += width
            continue
        end = width + offset
        relative_space = encoded.find(b" ", end)
        if relative_space < 0:
            output.extend(encoded[offset:])
            offset = len(encoded)
        else:
            output.extend(encoded[offset:relative_space])
            output.extend(separator_bytes)
            offset = relative_space + 1
    output.extend(encoded[offset:])
    return bytes(output).decode(errors="replace")


def b64enc(value: str) -> str:
    return base64.b64encode(value.encode()).decode()


def b64dec(value: str) -> str:
    encoded = value.encode()
    position = _base64_error_position(encoded)
    if position is not None:
        return f"illegal base64 data at input byte {position}"
    symbols = _encoded_symbols(value)
    normalized = bytes(symbol for symbol, _position in symbols)
    return base64.b64decode(normalized, validate=True).decode(errors="replace")


def b32enc(value: str) -> str:
    return base64.b32encode(value.encode()).decode()


def b32dec(value: str) -> str:
    normalized = value.encode().replace(b"\r", b"").replace(b"\n", b"")
    position = _base32_error_position(normalized)
    if position is not None:
        return f"illegal base32 data at input byte {position}"
    padding = normalized.find(b"=")
    if padding >= 0:
        normalized = normalized[:padding] + b"=" * (8 - padding % 8)
    return base64.b32decode(normalized).decode(errors="replace")


def sha1sum(value: str) -> str:
    return hashlib.sha1(value.encode(), usedforsecurity=False).hexdigest()


def sha256sum(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def sha512sum(value: str) -> str:
    return hashlib.sha512(value.encode()).hexdigest()


def adler32sum(value: str) -> str:
    return str(zlib.adler32(value.encode()))


def path_base(value: str) -> str:
    if not value:
        return "."
    stripped = value.rstrip("/")
    if not stripped:
        return "/"
    return posixpath.basename(stripped)


def path_dir(value: str) -> str:
    separator = value.rfind("/")
    return path_clean(value[: separator + 1] if separator >= 0 else "")


def path_clean(value: str) -> str:
    cleaned = posixpath.normpath(value)
    return cleaned[1:] if cleaned.startswith("//") else cleaned


def path_ext(value: str) -> str:
    component = value[value.rfind("/") + 1 :]
    dot = component.rfind(".")
    return component[dot:] if dot >= 0 else ""


def path_is_abs(value: str) -> bool:
    return posixpath.isabs(value)


def os_path_base(value: str) -> str:
    if os.path.sep == "/":
        return path_base(value)
    if not value:  # pragma: no cover - Windows filepath semantics
        return "."  # pragma: no cover
    return (  # pragma: no cover
        os.path.basename(value.rstrip(os.path.sep)) or os.path.sep
    )


def os_path_dir(value: str) -> str:
    if os.path.sep == "/":
        return path_dir(value)
    return os.path.dirname(value) or "."  # pragma: no cover - Windows only


def os_path_clean(value: str) -> str:
    if os.path.sep == "/":
        return path_clean(value)
    return os.path.normpath(value)  # pragma: no cover - Windows only


def os_path_ext(value: str) -> str:
    if os.path.sep == "/":
        return path_ext(value)
    return os.path.splitext(value)[1]  # pragma: no cover - Windows only


def os_path_is_abs(value: str) -> bool:
    if os.path.sep == "/":
        return path_is_abs(value)
    return os.path.isabs(value)  # pragma: no cover - Windows only


def _encoded_symbols(value: str) -> list[tuple[int, int]]:
    return [
        (symbol, position)
        for position, symbol in enumerate(value.encode())
        if symbol not in {0x0A, 0x0D}
    ]


def _base64_error_position(encoded: bytes) -> int | None:
    alphabet = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
    cursor = 0
    while cursor < len(encoded):
        digit = 0
        while digit < 4:
            if cursor == len(encoded):
                return None if digit == 0 else cursor - digit
            symbol = encoded[cursor]
            cursor += 1
            if symbol in alphabet:
                digit += 1
                continue
            if symbol in {0x0A, 0x0D}:
                continue
            if symbol != ord("="):
                return cursor - 1
            if digit in {0, 1}:
                return cursor - 1
            if digit == 2:
                while cursor < len(encoded) and encoded[cursor] in {0x0A, 0x0D}:
                    cursor += 1
                if cursor == len(encoded):
                    return len(encoded)
                if encoded[cursor] != ord("="):
                    return cursor - 1
                cursor += 1
            while cursor < len(encoded) and encoded[cursor] in {0x0A, 0x0D}:
                cursor += 1
            return cursor if cursor < len(encoded) else None
    return None


def _base32_error_position(encoded: bytes) -> int | None:
    alphabet = b"ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"
    cursor = 0
    total = len(encoded)
    ended = False
    while cursor < total and not ended:
        digit = 0
        while digit < 8:
            if cursor == total:
                return total - digit
            symbol = encoded[cursor]
            cursor += 1
            remaining = total - cursor
            if symbol == ord("=") and digit >= 2 and remaining < 8:
                if remaining + digit < 7:
                    return total
                for offset in range(7 - digit):
                    if remaining > offset and encoded[cursor + offset] != ord("="):
                        return cursor + offset - 1
                if digit in {1, 3, 6}:
                    return cursor - 1
                ended = True
                break
            if symbol not in alphabet:
                return cursor - 1
            digit += 1
    return None
