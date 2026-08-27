"""Go-compatible escapers for the initial HTML context families."""

from __future__ import annotations

import base64
import json
import math
from collections.abc import Mapping, Sequence
from decimal import Decimal
from html.parser import HTMLParser
from typing import cast

from gotpl.runtime import INVALID, UNTYPED_NIL, FormatMode
from gotpl.runtime.sync_vm import format_value

from .content import ContentKind, classify

_HTML_REPLACEMENTS = {
    "\x00": "\ufffd",
    '"': "&#34;",
    "&": "&amp;",
    "'": "&#39;",
    "+": "&#43;",
    "<": "&lt;",
    ">": "&gt;",
}
_HTML_NORMAL_REPLACEMENTS = {
    key: value for key, value in _HTML_REPLACEMENTS.items() if key != "&"
}
_NOSPACE_REPLACEMENTS = {
    "\x00": "&#xfffd;",
    "\t": "&#9;",
    "\n": "&#10;",
    "\v": "&#11;",
    "\f": "&#12;",
    "\r": "&#13;",
    " ": "&#32;",
    '"': "&#34;",
    "&": "&amp;",
    "'": "&#39;",
    "+": "&#43;",
    "<": "&lt;",
    "=": "&#61;",
    ">": "&gt;",
    "`": "&#96;",
}
_NOSPACE_NORMAL_REPLACEMENTS = {
    key: value for key, value in _NOSPACE_REPLACEMENTS.items() if key != "&"
}
_JS_STRING_REPLACEMENTS = {
    '"': r"\u0022",
    "'": r"\u0027",
    "`": r"\u0060",
    "&": r"\u0026",
    "+": r"\u002b",
    "/": r"\/",
    "<": r"\u003c",
    ">": r"\u003e",
    "\\": r"\\",
}
_JS_STRING_NORMAL_REPLACEMENTS = {
    key: value for key, value in _JS_STRING_REPLACEMENTS.items() if key != "\\"
}
_JS_TEMPLATE_REPLACEMENTS = {
    **_JS_STRING_REPLACEMENTS,
    "$": r"\u0024",
    "{": r"\u007b",
    "}": r"\u007d",
}
_JS_REGEXP_REPLACEMENTS = {
    **_JS_STRING_REPLACEMENTS,
    "$": r"\$",
    "(": r"\(",
    ")": r"\)",
    "*": r"\*",
    "-": r"\-",
    ".": r"\.",
    "?": r"\?",
    "[": r"\[",
    "]": r"\]",
    "^": r"\^",
    "{": r"\{",
    "|": r"\|",
    "}": r"\}",
}
_CSS_REPLACEMENTS = {
    "\x00": r"\0",
    "\t": r"\9",
    "\n": r"\a",
    "\f": r"\c",
    "\r": r"\d",
    '"': r"\22",
    "&": r"\26",
    "'": r"\27",
    "(": r"\28",
    ")": r"\29",
    "+": r"\2b",
    "/": r"\2f",
    ":": r"\3a",
    ";": r"\3b",
    "<": r"\3c",
    ">": r"\3e",
    "\\": r"\\",
    "{": r"\7b",
    "}": r"\7d",
}
_CSS_FORBIDDEN = frozenset("\x00\"'()/;@[\\]`{}<>")


def html_escaper(value: object, *, format_mode: FormatMode = "go") -> str:
    """Escape an ordinary value in HTML text context."""

    text, kind = _stringify_with_kind(value, format_mode)
    return text if kind is ContentKind.HTML else _replace(text, _HTML_REPLACEMENTS)


def rcdata_escaper(value: object, *, format_mode: FormatMode = "go") -> str:
    """Escape an ordinary value in title or textarea content."""

    text, kind = _stringify_with_kind(value, format_mode)
    replacements = (
        _HTML_NORMAL_REPLACEMENTS if kind is ContentKind.HTML else _HTML_REPLACEMENTS
    )
    return _replace(text, replacements)


def attr_escaper(value: object, *, format_mode: FormatMode = "go") -> str:
    """Escape an ordinary value in a quoted HTML attribute."""

    text, kind = _stringify_with_kind(value, format_mode)
    if kind is ContentKind.HTML:
        return _replace(_strip_tags(text), _HTML_NORMAL_REPLACEMENTS)
    return _replace(text, _HTML_REPLACEMENTS)


def nospace_escaper(value: object, *, format_mode: FormatMode = "go") -> str:
    """Escape an ordinary value in an unquoted HTML attribute."""

    text, kind = _stringify_with_kind(value, format_mode)
    if not text:
        return "ZgotmplZ"
    if kind is ContentKind.HTML:
        return _replace(_strip_tags(text), _NOSPACE_NORMAL_REPLACEMENTS)
    return _replace(text, _NOSPACE_REPLACEMENTS)


def comment_escaper(_value: object) -> str:
    """Elide dynamic content inside an HTML comment."""

    return ""


def js_value_escaper(value: object) -> str:
    """Encode an ordinary value as a side-effect-free JavaScript expression."""

    if value is INVALID or value is UNTYPED_NIL:
        value = None
    kind = classify(value)
    if kind is ContentKind.JS:
        return str(value)
    if kind is ContentKind.JS_STRING:
        return '"' + str(value) + '"'
    try:
        encoded = _json_encode(value, seen=set())
    except (TypeError, ValueError) as error:
        message = str(error)
        message = message.replace("*/", "* /").replace("<!--", r"\x3C!--")
        message = _escape_script_names(message)
        return f" /* {message} */null "
    if _is_js_identifier_part(encoded[0]) or _is_js_identifier_part(encoded[-1]):
        return f" {encoded} "
    return encoded


def js_string_escaper(value: object, *, format_mode: FormatMode = "go") -> str:
    """Escape a value for a quoted JavaScript string body."""

    text, kind = _stringify_with_kind(value, format_mode)
    replacements = (
        _JS_STRING_NORMAL_REPLACEMENTS
        if kind is ContentKind.JS_STRING
        else _JS_STRING_REPLACEMENTS
    )
    return _js_replace(text, replacements)


def js_template_escaper(value: object, *, format_mode: FormatMode = "go") -> str:
    """Escape a value for a JavaScript template-literal body."""

    return _js_replace(_stringify(value, format_mode), _JS_TEMPLATE_REPLACEMENTS)


def js_regexp_escaper(value: object, *, format_mode: FormatMode = "go") -> str:
    """Escape a value as literal text inside a JavaScript regular expression."""

    result = _js_replace(_stringify(value, format_mode), _JS_REGEXP_REPLACEMENTS)
    return result or "(?:)"


def css_escaper(value: object, *, format_mode: FormatMode = "go") -> str:
    """Escape a value for a quoted CSS string body."""

    text = _stringify(value, format_mode)
    output: list[str] = []
    for index, character in enumerate(text):
        replacement = _CSS_REPLACEMENTS.get(character)
        if replacement is None:
            output.append(character)
            continue
        output.append(replacement)
        if replacement != r"\\" and (
            index + 1 == len(text)
            or text[index + 1] in "0123456789abcdefABCDEF\t\n\f\r "
        ):
            output.append(" ")
    return "".join(output)


def css_value_filter(value: object, *, format_mode: FormatMode = "go") -> str:
    """Allow inert CSS tokens and replace active or boundary-breaking values."""

    text, kind = _stringify_with_kind(value, format_mode)
    if kind is ContentKind.CSS:
        return text
    decoded = decode_css(text)
    identifier: list[str] = []
    for index, character in enumerate(decoded):
        if character in _CSS_FORBIDDEN:
            return "ZgotmplZ"
        if character == "-":
            if index and decoded[index - 1] == "-":
                return "ZgotmplZ"
            continue
        if _is_css_name_character(character):
            identifier.append(character)
    normalized = "".join(identifier).casefold()
    if "expression" in normalized or "mozbinding" in normalized:
        return "ZgotmplZ"
    return decoded


def srcset_escaper(value: object, *, format_mode: FormatMode = "go") -> str:
    """Filter and normalize each candidate in an HTML srcset value."""

    text, kind = _stringify_with_kind(value, format_mode)
    if kind is ContentKind.SRCSET:
        return text
    if kind is ContentKind.URL:
        return url_normalizer(text).replace(",", "%2c")
    output: list[str] = []
    left = 0
    for index, character in enumerate(text):
        if character == ",":
            output.append(_filter_srcset_candidate(text[left:index]))
            output.append(",")
            left = index + 1
    output.append(_filter_srcset_candidate(text[left:]))
    return "".join(output)


def url_filter(value: object, *, format_mode: FormatMode = "go") -> str:
    """Replace unsafe URL schemes with Go's innocuous failsafe fragment."""

    text, kind = _stringify_with_kind(value, format_mode)
    if kind is ContentKind.URL:
        return text
    protocol, separator, _rest = text.partition(":")
    if (
        separator
        and "/" not in protocol
        and protocol.casefold()
        not in {
            "http",
            "https",
            "mailto",
        }
    ):
        return "#ZgotmplZ"
    return text


def url_normalizer(value: object, *, format_mode: FormatMode = "go") -> str:
    """Normalize a value embedded before a URL query or fragment."""

    return _url_processor(_stringify(value, format_mode), normalize=True)


def url_escaper(value: object, *, format_mode: FormatMode = "go") -> str:
    """Percent-encode a value embedded in a URL query or fragment."""

    text, kind = _stringify_with_kind(value, format_mode)
    return _url_processor(text, normalize=kind is ContentKind.URL)


def html_name_filter(value: object, *, format_mode: FormatMode = "go") -> str:
    """Allow a trusted attribute fragment or a conservative plain name."""

    text, kind = _stringify_with_kind(value, format_mode)
    if kind is ContentKind.HTML_ATTR:
        return text
    lowered = text.casefold()
    if (
        not lowered
        or _attribute_name_is_active(lowered)
        or any(
            not (character.isascii() and character.isalnum()) for character in lowered
        )
    ):
        return "ZgotmplZ"
    return lowered


def _stringify(value: object, format_mode: FormatMode) -> str:
    return _stringify_with_kind(value, format_mode)[0]


def _stringify_with_kind(
    value: object, format_mode: FormatMode
) -> tuple[str, ContentKind]:
    kind = classify(value)
    if value is None or value is UNTYPED_NIL:
        return "", ContentKind.PLAIN
    if value is INVALID:
        return "<no value>", ContentKind.PLAIN
    if kind is not ContentKind.PLAIN:
        return str(value), kind
    return format_value(value, format_mode), kind


def _replace(value: str, replacements: dict[str, str]) -> str:
    result = value
    ampersand = replacements.get("&")
    if ampersand is not None:
        result = result.replace("&", ampersand)
    for character, replacement in replacements.items():
        if character != "&":
            result = result.replace(character, replacement)
    return result


def _url_processor(value: str, *, normalize: bool) -> str:
    data = value.encode("utf-8")
    output: list[str] = []
    normalized_safe = b"!#$&*+,-./:;=?@[]"
    unreserved = b"-._~"
    index = 0
    while index < len(data):
        byte = data[index]
        is_alphanumeric = (
            ord("a") <= byte <= ord("z")
            or ord("A") <= byte <= ord("Z")
            or ord("0") <= byte <= ord("9")
        )
        if (
            is_alphanumeric
            or byte in unreserved
            or (normalize and byte in normalized_safe)
        ):
            output.append(chr(byte))
        elif (
            normalize
            and byte == ord("%")
            and index + 2 < len(data)
            and _is_hex(data[index + 1])
            and _is_hex(data[index + 2])
        ):
            output.append("%")
        else:
            output.append(f"%{byte:02x}")
        index += 1
    return "".join(output)


def _is_hex(byte: int) -> bool:
    return (
        ord("0") <= byte <= ord("9")
        or ord("a") <= byte <= ord("f")
        or ord("A") <= byte <= ord("F")
    )


def _js_replace(value: str, replacements: dict[str, str]) -> str:
    output: list[str] = []
    for character in value:
        codepoint = ord(character)
        replacement = replacements.get(character)
        if replacement is not None:
            output.append(replacement)
        elif codepoint < 0x20:
            output.append(
                {8: r"\b", 9: r"\t", 10: r"\n", 12: r"\f", 13: r"\r"}.get(
                    codepoint, f"\\u{codepoint:04x}"
                )
            )
        elif codepoint in {0x2028, 0x2029}:
            output.append(f"\\u{codepoint:04x}")
        else:
            output.append(character)
    return "".join(output)


def _json_encode(value: object, *, seen: set[int]) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return _json_float(value)
    if isinstance(value, str):
        return _json_string(value)
    if isinstance(value, (bytes, bytearray)):
        return _json_string(base64.b64encode(bytes(value)).decode())
    if isinstance(value, Mapping):
        mapping = cast(Mapping[object, object], value)
        identity = id(mapping)
        if identity in seen:
            raise ValueError("encountered a cycle")
        entries: list[tuple[str, object]] = []
        for key, item in mapping.items():
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
            return (
                "{"
                + ",".join(
                    _json_string(key) + ":" + _json_encode(item, seen=seen)
                    for key, item in entries
                )
                + "}"
            )
        finally:
            seen.remove(identity)
    if isinstance(value, Sequence):
        sequence = cast(Sequence[object], value)
        identity = id(sequence)
        if identity in seen:
            raise ValueError("encountered a cycle")
        seen.add(identity)
        try:
            return (
                "[" + ",".join(_json_encode(item, seen=seen) for item in sequence) + "]"
            )
        finally:
            seen.remove(identity)
    raise TypeError(f"unsupported type: {type(value).__name__}")


def _json_string(value: str) -> str:
    return (
        json.encoder.encode_basestring(value)
        .replace("&", r"\u0026")
        .replace("<", r"\u003c")
        .replace(">", r"\u003e")
        .replace("\u2028", r"\u2028")
        .replace("\u2029", r"\u2029")
    )


def _json_float(value: float) -> str:
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


def _is_js_identifier_part(character: str) -> bool:
    return (
        character == "$"
        or character == "_"
        or (character.isascii() and character.isalnum())
    )


def _escape_script_names(value: str) -> str:
    lower = value.casefold()
    output: list[str] = []
    index = 0
    while index < len(value):
        if lower.startswith("<script", index) or lower.startswith("</script", index):
            output.append(r"\x3C")
            index += 1
        else:
            output.append(value[index])
            index += 1
    return "".join(output)


def decode_css(value: str) -> str:
    if "\\" not in value:
        return value
    output: list[str] = []
    index = 0
    while index < len(value):
        if value[index] != "\\":
            output.append(value[index])
            index += 1
            continue
        if index + 1 == len(value):
            break
        cursor = index + 1
        if value[cursor] in "0123456789abcdefABCDEF":
            end = cursor
            while (
                end < len(value)
                and end < cursor + 6
                and value[end] in "0123456789abcdefABCDEF"
            ):
                end += 1
            codepoint = int(value[cursor:end], 16)
            if codepoint > 0x10FFFF:
                codepoint //= 16
                end -= 1
            if 0xD800 <= codepoint <= 0xDFFF:
                codepoint = 0xFFFD
            output.append(chr(codepoint))
            if end < len(value) and value[end] in "\t\n\f ":
                end += 1
            elif end < len(value) and value[end] == "\r":
                end += 2 if end + 1 < len(value) and value[end + 1] == "\n" else 1
            index = end
            continue
        output.append(value[cursor])
        index = cursor + 1
    return "".join(output)


def _is_css_name_character(character: str) -> bool:
    codepoint = ord(character)
    return (
        (character.isascii() and (character.isalnum() or character in "-_"))
        or 0x80 <= codepoint <= 0xD7FF
        or 0xE000 <= codepoint <= 0xFFFD
        or 0x10000 <= codepoint <= 0x10FFFF
    )


def _filter_srcset_candidate(candidate: str) -> str:
    start = 0
    while start < len(candidate) and candidate[start] in "\t\n\f\r ":
        start += 1
    end = start
    while end < len(candidate) and candidate[end] not in "\t\n\f\r ":
        end += 1
    url = candidate[start:end]
    metadata = candidate[end:]
    metadata_is_safe = all(
        character in "\t\n\f\r " or (character.isascii() and character.isalnum())
        for character in metadata
    )
    if url_filter(url) == url and metadata_is_safe:
        return candidate[:start] + url_normalizer(url) + metadata
    return "#ZgotmplZ"


def _attribute_name_is_active(name: str) -> bool:
    if name.startswith("data-"):
        name = name[5:]
    elif ":" in name:
        prefix, name = name.split(":", 1)
        if prefix == "xmlns":
            return True
    return (
        name in _UNSAFE_ATTRIBUTE_NAMES
        or name in {"srcdoc", "srcset", "style"}
        or name.startswith("on")
        or name
        in {
            "action",
            "archive",
            "background",
            "cite",
            "classid",
            "codebase",
            "data",
            "formaction",
            "href",
            "icon",
            "longdesc",
            "manifest",
            "poster",
            "profile",
            "src",
            "usemap",
            "xmlns",
        }
        or any(part in name for part in ("src", "uri", "url"))
    )


_UNSAFE_ATTRIBUTE_NAMES = frozenset(
    {
        "accept-charset",
        "async",
        "challenge",
        "charset",
        "content",
        "crossorigin",
        "defer",
        "enctype",
        "form",
        "formenctype",
        "formmethod",
        "formnovalidate",
        "http-equiv",
        "keytype",
        "language",
        "method",
        "novalidate",
        "pattern",
        "rel",
        "sandbox",
        "type",
        "value",
    }
)


class _TagStripper(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.output: list[str] = []
        self.suppressed = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
        if tag.casefold() in {"script", "style"}:
            self.suppressed += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() in {"script", "style"} and self.suppressed:
            self.suppressed -= 1

    def handle_data(self, data: str) -> None:
        if not self.suppressed:
            self.output.append(data)

    def handle_entityref(self, name: str) -> None:
        if not self.suppressed:
            self.output.append(f"&{name};")

    def handle_charref(self, name: str) -> None:
        if not self.suppressed:
            self.output.append(f"&#{name};")


def _strip_tags(value: str) -> str:
    parser = _TagStripper()
    parser.feed(value)
    parser.close()
    return "".join(parser.output)
