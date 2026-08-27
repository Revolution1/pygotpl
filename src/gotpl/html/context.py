"""HTML lexical context tracking for contextual instruction rewriting."""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from enum import Enum, auto

from gotpl.errors import TemplateSyntaxError

from .escapers import decode_css


class ContextKind(Enum):
    """Initial HTML context states implemented by the analyzer."""

    TEXT = auto()
    TAG = auto()
    ATTR_NAME = auto()
    AFTER_NAME = auto()
    BEFORE_VALUE = auto()
    ATTR = auto()
    RCDATA = auto()
    COMMENT = auto()
    JS = auto()
    JS_DQ_STRING = auto()
    JS_SQ_STRING = auto()
    JS_TEMPLATE = auto()
    JS_REGEXP = auto()
    JS_BLOCK_COMMENT = auto()
    JS_LINE_COMMENT = auto()
    CSS = auto()
    CSS_DQ_STRING = auto()
    CSS_SQ_STRING = auto()
    CSS_DQ_URL = auto()
    CSS_SQ_URL = auto()
    CSS_URL = auto()
    CSS_BLOCK_COMMENT = auto()
    CSS_LINE_COMMENT = auto()
    SRCSET = auto()


class EscapeKind(Enum):
    """Escaping operation selected for an action."""

    HTML = auto()
    RCDATA = auto()
    ATTR = auto()
    NOSPACE = auto()
    COMMENT = auto()
    URL_FILTER = auto()
    URL_NORMALIZER = auto()
    URL_ESCAPER = auto()
    JS_VALUE = auto()
    JS_STRING = auto()
    JS_TEMPLATE = auto()
    JS_REGEXP = auto()
    CSS_VALUE = auto()
    CSS_STRING = auto()
    SRCSET = auto()
    HTML_NAME = auto()


class AttributeKind(Enum):
    """Semantic attribute kinds needed by contextual escaping."""

    PLAIN = auto()
    URL = auto()
    JS = auto()
    JS_TYPE = auto()
    CSS = auto()
    SRCSET = auto()
    META_CONTENT = auto()


class URLPart(Enum):
    """Position within a URL attribute value."""

    NONE = auto()
    PRE_QUERY = auto()
    QUERY_OR_FRAGMENT = auto()
    UNKNOWN = auto()


class JSContext(Enum):
    """Whether the next JavaScript slash starts a regexp or division."""

    REGEXP = auto()
    DIVISION = auto()
    UNKNOWN = auto()


@dataclass(slots=True)
class Context:
    """Mutable analysis state propagated across literal instructions."""

    kind: ContextKind = ContextKind.TEXT
    delimiter: str = ""
    element: str = ""
    closing_tag: bool = False
    attribute: AttributeKind = AttributeKind.PLAIN
    url_part: URLPart = URLPart.NONE
    js_context: JSContext = JSContext.REGEXP
    js_brace_depth: tuple[int, ...] = ()
    js_regexp_charset: bool = False
    comment_has_newline: bool = False
    attribute_value: str = ""
    attribute_name: str = ""
    meta_refresh: bool = False

    def escape_kind(self) -> EscapeKind:
        return self.escape_kinds()[-1]

    def escape_kinds(self, position: int = 0) -> tuple[EscapeKind, ...]:
        """Return the ordered escaper pipeline for the current action."""

        if self.kind is ContextKind.COMMENT:
            return (EscapeKind.COMMENT,)
        if self.kind in {ContextKind.TAG, ContextKind.AFTER_NAME}:
            self.kind = ContextKind.ATTR_NAME
            self.attribute = AttributeKind.PLAIN
            self.attribute_name = ""
            return (EscapeKind.HTML_NAME,)
        if self.kind is ContextKind.ATTR_NAME:
            return (EscapeKind.HTML_NAME,)
        if self.kind in {ContextKind.JS_BLOCK_COMMENT, ContextKind.JS_LINE_COMMENT}:
            return self._with_attribute_terminal((EscapeKind.COMMENT,))
        if self.kind in {ContextKind.CSS_BLOCK_COMMENT, ContextKind.CSS_LINE_COMMENT}:
            return self._with_attribute_terminal((EscapeKind.COMMENT,))
        if self.kind is ContextKind.RCDATA:
            return (EscapeKind.RCDATA,)
        if self.kind is ContextKind.BEFORE_VALUE:
            self.kind = (
                ContextKind.JS
                if self.attribute is AttributeKind.JS
                else ContextKind.CSS
                if self.attribute is AttributeKind.CSS
                else ContextKind.SRCSET
                if self.attribute is AttributeKind.SRCSET
                else ContextKind.ATTR
            )
            self.delimiter = ""
        if self.kind is ContextKind.JS:
            self.js_context = JSContext.DIVISION
            return self._with_attribute_terminal((EscapeKind.JS_VALUE,))
        if self.kind in {ContextKind.JS_DQ_STRING, ContextKind.JS_SQ_STRING}:
            return self._with_attribute_terminal((EscapeKind.JS_STRING,))
        if self.kind is ContextKind.JS_TEMPLATE:
            return self._with_attribute_terminal((EscapeKind.JS_TEMPLATE,))
        if self.kind is ContextKind.JS_REGEXP:
            if self.js_regexp_charset:
                raise TemplateSyntaxError(
                    "action cannot appear inside a JavaScript regexp character class",
                    position=position,
                )
            return self._with_attribute_terminal((EscapeKind.JS_REGEXP,))
        if self.kind is ContextKind.CSS:
            return self._with_attribute_terminal((EscapeKind.CSS_VALUE,))
        if self.kind in {ContextKind.CSS_DQ_STRING, ContextKind.CSS_SQ_STRING}:
            return self._css_url_escapers(css_string=True, position=position)
        if self.kind in {
            ContextKind.CSS_DQ_URL,
            ContextKind.CSS_SQ_URL,
            ContextKind.CSS_URL,
        }:
            return self._css_url_escapers(css_string=False, position=position)
        if self.kind is ContextKind.SRCSET:
            return self._with_attribute_terminal((EscapeKind.SRCSET,))
        if self.kind is ContextKind.ATTR:
            terminal = EscapeKind.ATTR if self.delimiter else EscapeKind.NOSPACE
            if self.attribute is AttributeKind.META_CONTENT:
                return (
                    (EscapeKind.URL_FILTER, terminal)
                    if _meta_content_url_active(self.attribute_value)
                    else (terminal,)
                )
            if self.attribute is not AttributeKind.URL:
                return (terminal,)
            if self.url_part is URLPart.NONE:
                return (EscapeKind.URL_FILTER, EscapeKind.URL_NORMALIZER, terminal)
            if self.url_part is URLPart.PRE_QUERY:
                return (EscapeKind.URL_NORMALIZER, terminal)
            if self.url_part is URLPart.QUERY_OR_FRAGMENT:
                return (EscapeKind.URL_ESCAPER, terminal)
            raise TemplateSyntaxError(
                "action appears in an ambiguous context within a URL",
                position=position,
            )
        return (EscapeKind.HTML,)

    def _with_attribute_terminal(
        self, kinds: tuple[EscapeKind, ...]
    ) -> tuple[EscapeKind, ...]:
        if self.attribute not in {
            AttributeKind.JS,
            AttributeKind.CSS,
            AttributeKind.SRCSET,
        }:
            return kinds
        terminal = (
            EscapeKind.ATTR if self.delimiter in {'"', "'"} else EscapeKind.NOSPACE
        )
        return (*kinds, terminal)

    def _css_url_escapers(
        self, *, css_string: bool, position: int
    ) -> tuple[EscapeKind, ...]:
        if self.url_part is URLPart.UNKNOWN:
            raise TemplateSyntaxError(
                "action appears in an ambiguous context within a CSS URL",
                position=position,
            )
        if self.url_part is URLPart.QUERY_OR_FRAGMENT:
            kinds = (EscapeKind.URL_ESCAPER,)
        elif css_string:
            kinds = (
                (EscapeKind.URL_FILTER, EscapeKind.CSS_STRING)
                if self.url_part is URLPart.NONE
                else (EscapeKind.CSS_STRING,)
            )
        else:
            kinds = (
                (EscapeKind.URL_FILTER, EscapeKind.URL_NORMALIZER)
                if self.url_part is URLPart.NONE
                else (EscapeKind.URL_NORMALIZER,)
            )
        return self._with_attribute_terminal(kinds)

    def consume(self, text: str) -> str:
        """Advance through literal HTML and remove HTML comments."""

        output: list[str] = []
        index = 0
        while index < len(text):
            if self.kind is ContextKind.COMMENT:
                end = text.find("-->", index)
                if end < 0:
                    return "".join(output)
                index = end + 3
                self.kind = ContextKind.TEXT
                continue

            if self.kind is ContextKind.TEXT:
                comment = text.find("<!--", index)
                tag = text.find("<", index)
                candidates = [position for position in (comment, tag) if position >= 0]
                if not candidates:
                    output.append(text[index:])
                    break
                boundary = min(candidates)
                output.append(text[index:boundary])
                if comment == boundary:
                    self.kind = ContextKind.COMMENT
                    index = boundary + 4
                    continue
                if _is_doctype_prefix(text, boundary):
                    output.append("<")
                    index = boundary + 1
                    continue
                parsed = self._consume_tag_start(text, boundary, output)
                if parsed == boundary:
                    output.append("&lt;")
                    index = boundary + 1
                else:
                    index = parsed
                continue

            if self.kind is ContextKind.RCDATA:
                marker = f"</{self.element}"
                boundary = _find_special_tag_end(text, index, self.element)
                if boundary < 0:
                    output.append(_escape_rcdata_literal(text[index:]))
                    break
                output.append(_escape_rcdata_literal(text[index:boundary]))
                output.append(text[boundary : boundary + len(marker)])
                index = boundary + len(marker)
                self.kind = ContextKind.TAG
                self.closing_tag = True
                self.element = ""
                continue

            if self.kind in _JS_STATES:
                next_index, rendered = self._advance_js_context(text, index)
                output.append(rendered)
                index = next_index
                continue

            if self.kind in _CSS_STATES:
                next_index, rendered = self._advance_css_context(text, index)
                output.append(rendered)
                index = next_index
                continue

            if self.kind is ContextKind.SRCSET:
                next_index, rendered = self._advance_srcset_context(text, index)
                output.append(rendered)
                index = next_index
                continue

            next_index = self._advance_tag_context(text, index)
            output.append(text[index:next_index])
            index = next_index
        if self.kind is ContextKind.JS_REGEXP and self.js_regexp_charset:
            raise TemplateSyntaxError(
                "unfinished JavaScript regexp character class",
                position=max(len(text) - 1, 0),
            )
        return "".join(output)

    def _consume_tag_start(self, text: str, index: int, output: list[str]) -> int:
        cursor = index + 1
        closing = cursor < len(text) and text[cursor] == "/"
        if closing:
            cursor += 1
        start = cursor
        if cursor < len(text) and _is_ascii_alpha(text[cursor]):
            cursor += 1
            while cursor < len(text):
                character = text[cursor]
                if _is_ascii_alphanumeric(character):
                    cursor += 1
                    continue
                if (
                    character in ":-"
                    and cursor + 1 < len(text)
                    and _is_ascii_alphanumeric(text[cursor + 1])
                ):
                    cursor += 2
                    continue
                break
        if cursor == start:
            return index
        output.append(text[index:cursor])
        name = text[start:cursor].lower()
        self.kind = ContextKind.TAG
        self.closing_tag = closing
        self.element = (
            ""
            if closing
            else name
            if name in {"meta", "script", "style", "textarea", "title"}
            else ""
        )
        self.meta_refresh = False
        self.attribute = AttributeKind.PLAIN
        self.url_part = URLPart.NONE
        return cursor

    def _advance_tag_context(self, text: str, index: int) -> int:
        character = text[index]
        if self.kind is ContextKind.TAG:
            if character.isspace():
                return index + 1
            if character == ">":
                self.kind = self._element_content_kind()
                return index + 1
            if character == "=":
                raise TemplateSyntaxError(
                    "expected an attribute name or end of tag before '='",
                    position=index,
                )
            cursor = index
            while (
                cursor < len(text)
                and not text[cursor].isspace()
                and text[cursor] not in "=>"
            ):
                if text[cursor] in "\"'<":
                    raise TemplateSyntaxError(
                        f"invalid {text[cursor]!r} in attribute name",
                        position=cursor,
                    )
                cursor += 1
            self.attribute_name = text[index:cursor].lower()
            self.attribute = _attribute_kind(self.attribute_name)
            if self.element == "script" and self.attribute_name == "type":
                self.attribute = AttributeKind.JS_TYPE
            elif (
                self.element == "meta"
                and self.attribute_name == "content"
                and self.meta_refresh
            ):
                self.attribute = AttributeKind.META_CONTENT
            self.attribute_value = ""
            self.url_part = URLPart.NONE
            self.kind = (
                ContextKind.ATTR_NAME if cursor == len(text) else ContextKind.AFTER_NAME
            )
            return max(cursor, index + 1)
        if self.kind is ContextKind.ATTR_NAME:
            cursor = index
            while (
                cursor < len(text)
                and not text[cursor].isspace()
                and text[cursor] not in "=>"
            ):
                if text[cursor] in "\"'<":
                    raise TemplateSyntaxError(
                        f"invalid {text[cursor]!r} in attribute name",
                        position=cursor,
                    )
                cursor += 1
            self.attribute_name += text[index:cursor].lower()
            if cursor < len(text):
                self.kind = ContextKind.AFTER_NAME
            return cursor
        if self.kind is ContextKind.AFTER_NAME:
            if character.isspace():
                return index + 1
            if character == "=":
                self.kind = ContextKind.BEFORE_VALUE
                return index + 1
            self.kind = ContextKind.TAG
            self.attribute = AttributeKind.PLAIN
            self.url_part = URLPart.NONE
            return index
        if self.kind is ContextKind.BEFORE_VALUE:
            if character.isspace():
                return index + 1
            if character in {'"', "'"}:
                self.kind = (
                    ContextKind.JS
                    if self.attribute is AttributeKind.JS
                    else ContextKind.CSS
                    if self.attribute is AttributeKind.CSS
                    else ContextKind.SRCSET
                    if self.attribute is AttributeKind.SRCSET
                    else ContextKind.ATTR
                )
                self.delimiter = character
                return index + 1
            if character in "<=`":
                raise TemplateSyntaxError(
                    f"invalid {character!r} in unquoted attribute value",
                    position=index,
                )
            self.kind = (
                ContextKind.JS
                if self.attribute is AttributeKind.JS
                else ContextKind.CSS
                if self.attribute is AttributeKind.CSS
                else ContextKind.SRCSET
                if self.attribute is AttributeKind.SRCSET
                else ContextKind.ATTR
            )
            self.delimiter = ""
            return index
        if self.kind is ContextKind.ATTR:
            if self.delimiter and character == self.delimiter:
                self._finish_attribute()
                return index + 1
            if not self.delimiter and (character.isspace() or character == ">"):
                self._finish_attribute(tag_end=character == ">")
                return index + 1
            if not self.delimiter and character in "\"'<=`":
                raise TemplateSyntaxError(
                    f"invalid {character!r} in unquoted attribute value",
                    position=index,
                )
            if self.attribute in {
                AttributeKind.JS_TYPE,
                AttributeKind.META_CONTENT,
            } or (self.element == "meta" and self.attribute_name == "http-equiv"):
                self.attribute_value += character
            if self.attribute is AttributeKind.URL:
                if character in "?#":
                    self.url_part = URLPart.QUERY_OR_FRAGMENT
                elif self.url_part is URLPart.NONE and not character.isspace():
                    self.url_part = URLPart.PRE_QUERY
            return index + 1
        return index + 1  # pragma: no cover - defensive unknown-state fallback

    def _finish_attribute(self, *, tag_end: bool = False) -> None:
        if self.attribute is AttributeKind.JS_TYPE and not _is_js_type(
            html.unescape(self.attribute_value)
        ):
            self.element = ""
        if self.element == "meta" and self.attribute_name == "http-equiv":
            self.meta_refresh = (
                html.unescape(self.attribute_value).strip().casefold() == "refresh"
            )
        self.kind = self._element_content_kind() if tag_end else ContextKind.TAG
        self.delimiter = ""
        self.attribute = AttributeKind.PLAIN
        self.url_part = URLPart.NONE
        self.attribute_value = ""
        self.attribute_name = ""

    def _element_content_kind(self) -> ContextKind:
        if self.closing_tag:
            self.closing_tag = False
            return ContextKind.TEXT
        if self.element in {"textarea", "title"}:
            return ContextKind.RCDATA
        if self.element == "script":
            self.js_context = JSContext.REGEXP
            return ContextKind.JS
        if self.element == "style":
            return ContextKind.CSS
        return ContextKind.TEXT

    def _advance_js_context(self, text: str, index: int) -> tuple[int, str]:
        character = text[index]
        self._reject_invalid_unquoted_attribute_character(character, index)
        if self._is_attribute_end(character):
            if character == ">":
                self._finish_attribute(tag_end=True)
            else:
                self._finish_attribute()
            return index + 1, character

        if self.attribute is AttributeKind.JS and self.delimiter != "\0":
            boundary = _js_attribute_boundary(text, index, self.delimiter)
            assert boundary > index
            raw = text[index:boundary]
            self._validate_unquoted_attribute_fragment(raw, index)
            decoded = html.unescape(raw)
            delimiter = self.delimiter
            self.delimiter = "\0"
            try:
                rendered = self.consume(decoded)
            finally:
                self.delimiter = delimiter
            return boundary, rendered if decoded == raw else raw

        if self.kind in {ContextKind.JS_BLOCK_COMMENT, ContextKind.JS_LINE_COMMENT}:
            return self._advance_js_comment(text, index)

        special = _special_script_prefix(text, index)
        if self.kind in _JS_LITERAL_STATES and special:
            return index + len(special), r"\x3C" + special[1:]

        if (
            self.kind is ContextKind.JS
            and self.element == "script"
            and _is_script_end(text, index)
        ):
            marker = text[index : index + 8]
            self.kind = ContextKind.TAG
            self.element = ""
            self.closing_tag = True
            return index + 8, marker

        if self.kind is ContextKind.JS:
            return self._advance_js_code(text, index)
        if self.kind in {ContextKind.JS_DQ_STRING, ContextKind.JS_SQ_STRING}:
            quote = '"' if self.kind is ContextKind.JS_DQ_STRING else "'"
            if character == "\\":
                return self._consume_js_escape(text, index)
            if character == quote:
                self.kind = ContextKind.JS
                self.js_context = JSContext.DIVISION
            return index + 1, character
        if self.kind is ContextKind.JS_TEMPLATE:
            if character == "\\":
                return self._consume_js_escape(text, index)
            if character == "`":
                self.kind = ContextKind.JS
                self.js_context = JSContext.DIVISION
                return index + 1, character
            if text.startswith("${", index):
                self.kind = ContextKind.JS
                self.js_brace_depth = (*self.js_brace_depth, 0)
                self.js_context = JSContext.REGEXP
                return index + 2, "${"
            return index + 1, character
        if self.kind is ContextKind.JS_REGEXP:
            if character == "\\":
                return self._consume_js_escape(text, index)
            if character == "[":
                self.js_regexp_charset = True
            elif character == "]":
                self.js_regexp_charset = False
            elif character == "/" and not self.js_regexp_charset:
                self.kind = ContextKind.JS
                self.js_context = JSContext.DIVISION
            return index + 1, character
        return index + 1, character  # pragma: no cover

    def _advance_js_code(self, text: str, index: int) -> tuple[int, str]:
        boundary = _next_js_boundary(text, index, self.delimiter)
        if boundary > index:
            chunk = text[index:boundary]
            self.js_context = _next_js_context(chunk, self.js_context)
            return boundary, chunk
        character = text[index]
        if character == '"':
            self.kind = ContextKind.JS_DQ_STRING
        elif character == "'":
            self.kind = ContextKind.JS_SQ_STRING
        elif character == "`":
            self.kind = ContextKind.JS_TEMPLATE
        elif text.startswith("//", index) or text.startswith("#!", index):
            self.kind = ContextKind.JS_LINE_COMMENT
            return index + 2, "" if not self.delimiter else text[index : index + 2]
        elif text.startswith("/*", index):
            self.kind = ContextKind.JS_BLOCK_COMMENT
            self.comment_has_newline = False
            return index + 2, "" if not self.delimiter else "/*"
        elif text.startswith("<!--", index) or text.startswith("-->", index):
            size = 4 if text.startswith("<!--", index) else 3
            self.kind = ContextKind.JS_LINE_COMMENT
            return index + size, "" if not self.delimiter else text[
                index : index + size
            ]
        elif character == "/":
            if self.js_context is JSContext.UNKNOWN:
                raise TemplateSyntaxError(
                    "'/' could start a division or JavaScript regexp",
                    position=index,
                )
            if self.js_context is JSContext.REGEXP:
                self.kind = ContextKind.JS_REGEXP
                self.js_regexp_charset = False
            else:
                self.js_context = JSContext.REGEXP
        elif character == "{":
            if self.js_brace_depth:
                self.js_brace_depth = (
                    *self.js_brace_depth[:-1],
                    self.js_brace_depth[-1] + 1,
                )
            self.js_context = _next_js_context(character, self.js_context)
        elif character == "}":
            if self.js_brace_depth:
                depth = self.js_brace_depth[-1] - 1
                if depth < 0:
                    self.js_brace_depth = self.js_brace_depth[:-1]
                    self.kind = ContextKind.JS_TEMPLATE
                else:
                    self.js_brace_depth = (*self.js_brace_depth[:-1], depth)
                    self.js_context = _next_js_context(character, self.js_context)
            else:
                self.js_context = _next_js_context(character, self.js_context)
        return index + 1, character

    def _advance_js_comment(self, text: str, index: int) -> tuple[int, str]:
        if self.kind is ContextKind.JS_BLOCK_COMMENT:
            end = text.find("*/", index)
            if end < 0:
                segment = text[index:]
                self.comment_has_newline |= any(c in segment for c in _JS_NEWLINES)
                rendered = (
                    segment
                    if self.delimiter
                    else "\n"
                    if any(c in segment for c in _JS_NEWLINES)
                    else " "
                )
                return len(text), rendered
            segment = text[index : end + 2]
            self.comment_has_newline |= any(c in segment for c in _JS_NEWLINES)
            self.kind = ContextKind.JS
            rendered = (
                segment if self.delimiter else "\n" if self.comment_has_newline else " "
            )
            self.comment_has_newline = False
            return end + 2, rendered
        end = min(
            (
                position
                for position in (text.find(c, index) for c in _JS_NEWLINES)
                if position >= 0
            ),
            default=-1,
        )
        if end < 0:
            return len(text), text[index:] if self.delimiter else ""
        self.kind = ContextKind.JS
        return end + 1, text[index : end + 1] if self.delimiter else text[end : end + 1]

    def _consume_js_escape(self, text: str, index: int) -> tuple[int, str]:
        if index + 1 == len(text):
            raise TemplateSyntaxError(
                "unfinished escape sequence in JavaScript string",
                position=index,
            )
        return index + 2, text[index : index + 2]

    def _is_attribute_end(self, character: str) -> bool:
        if self.attribute is not AttributeKind.JS:
            return False
        if self.delimiter == "\0":
            return False
        if self.delimiter in {'"', "'"}:
            return character == self.delimiter
        return character.isspace() or character == ">"

    def _reject_invalid_unquoted_attribute_character(
        self, character: str, position: int
    ) -> None:
        if (
            self.attribute
            in {
                AttributeKind.JS,
                AttributeKind.CSS,
                AttributeKind.SRCSET,
            }
            and not self.delimiter
            and character in "\"'<=`"
        ):
            raise TemplateSyntaxError(
                f"invalid {character!r} in unquoted attribute value",
                position=position,
            )

    def _validate_unquoted_attribute_fragment(
        self, fragment: str, position: int
    ) -> None:
        if self.delimiter:
            return
        for offset, character in enumerate(fragment):
            self._reject_invalid_unquoted_attribute_character(
                character, position + offset
            )

    def _advance_css_context(self, text: str, index: int) -> tuple[int, str]:
        character = text[index]
        self._reject_invalid_unquoted_attribute_character(character, index)
        if self._is_css_attribute_end(character):
            if character == ">":
                self._finish_attribute(tag_end=True)
            else:
                self._finish_attribute()
            return index + 1, character

        if self.attribute is AttributeKind.CSS and self.delimiter != "\0":
            boundary = _css_attribute_boundary(text, index, self.delimiter)
            assert boundary > index
            raw = text[index:boundary]
            self._validate_unquoted_attribute_fragment(raw, index)
            decoded = html.unescape(raw)
            delimiter = self.delimiter
            self.delimiter = "\0"
            try:
                rendered = self.consume(decoded)
            finally:
                self.delimiter = delimiter
            return boundary, rendered if decoded == raw else raw

        if self.element == "style" and _is_style_end(text, index):
            marker = text[index : index + 7]
            self.kind = ContextKind.TAG
            self.element = ""
            self.closing_tag = True
            return index + 7, marker

        if self.kind in {ContextKind.CSS_BLOCK_COMMENT, ContextKind.CSS_LINE_COMMENT}:
            return self._advance_css_comment(text, index)
        if self.kind is ContextKind.CSS:
            return self._advance_css_code(text, index)
        return self._advance_css_string(text, index)

    def _advance_css_code(self, text: str, index: int) -> tuple[int, str]:
        boundary = _next_css_boundary(text, index, self.delimiter)
        if boundary > index:
            if (
                boundary < len(text)
                and text[boundary] == "("
                and _ends_with_css_keyword(text[index:boundary], "url")
            ):
                cursor = boundary + 1
                while cursor < len(text) and text[cursor] in "\t\n\f\r ":
                    cursor += 1
                if cursor < len(text) and text[cursor] == '"':
                    self.kind = ContextKind.CSS_DQ_URL
                    cursor += 1
                elif cursor < len(text) and text[cursor] == "'":
                    self.kind = ContextKind.CSS_SQ_URL
                    cursor += 1
                else:
                    self.kind = ContextKind.CSS_URL
                return cursor, text[index:cursor]
            return boundary, text[index:boundary]
        character = text[index]
        if text.startswith("/*", index):
            self.kind = ContextKind.CSS_BLOCK_COMMENT
            return index + 2, "" if not self.delimiter else "/*"
        if text.startswith("//", index):
            self.kind = ContextKind.CSS_LINE_COMMENT
            return index + 2, "" if not self.delimiter else "//"
        if character == '"':
            self.kind = ContextKind.CSS_DQ_STRING
        elif character == "'":
            self.kind = ContextKind.CSS_SQ_STRING
        return index + 1, character

    def _advance_css_string(self, text: str, index: int) -> tuple[int, str]:
        character = text[index]
        if character == "\\":
            end = _css_escape_end(text, index)
            if end == index + 1:
                raise TemplateSyntaxError(
                    "unfinished escape sequence in CSS string",
                    position=index,
                )
            fragment = text[index:end]
            self._update_css_url_part(decode_css(fragment))
            return end, fragment

        if self.kind in {ContextKind.CSS_DQ_STRING, ContextKind.CSS_DQ_URL}:
            if character == '"':
                self.kind = ContextKind.CSS
                return index + 1, character
        elif self.kind in {ContextKind.CSS_SQ_STRING, ContextKind.CSS_SQ_URL}:
            if character == "'":
                self.kind = ContextKind.CSS
                return index + 1, character
        elif self.kind is ContextKind.CSS_URL and (
            character in "\t\n\f\r " or character == ")"
        ):
            self.kind = ContextKind.CSS
            return index + 1, character
        self._update_css_url_part(character)
        return index + 1, character

    def _update_css_url_part(self, value: str) -> None:
        if any(character in "?#" for character in value):
            self.url_part = URLPart.QUERY_OR_FRAGMENT
        elif self.url_part is URLPart.NONE and value.strip("\t\n\f\r "):
            self.url_part = URLPart.PRE_QUERY

    def _advance_css_comment(self, text: str, index: int) -> tuple[int, str]:
        if self.kind is ContextKind.CSS_BLOCK_COMMENT:
            end = text.find("*/", index)
            if end < 0:
                return len(text), text[index:] if self.delimiter else " "
            segment = text[index : end + 2]
            self.kind = ContextKind.CSS
            return end + 2, segment if self.delimiter else " "
        end = min(
            (
                position
                for position in (text.find(character, index) for character in "\n\f\r")
                if position >= 0
            ),
            default=-1,
        )
        if end < 0:
            return len(text), text[index:] if self.delimiter else ""
        self.kind = ContextKind.CSS
        return end + 1, text[index : end + 1] if self.delimiter else text[end : end + 1]

    def _is_css_attribute_end(self, character: str) -> bool:
        if self.attribute is not AttributeKind.CSS or self.delimiter == "\0":
            return False
        if self.delimiter in {'"', "'"}:
            return character == self.delimiter
        return character.isspace() or character == ">"

    def _advance_srcset_context(self, text: str, index: int) -> tuple[int, str]:
        character = text[index]
        self._reject_invalid_unquoted_attribute_character(character, index)
        if self.delimiter in {'"', "'"} and character == self.delimiter:
            self._finish_attribute()
        elif not self.delimiter and (character.isspace() or character == ">"):
            self._finish_attribute(tag_end=character == ">")
        return index + 1, character


_URL_ATTRIBUTES = frozenset(
    {
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
)


def _attribute_kind(name: str) -> AttributeKind:
    if name.startswith("data-"):
        name = name[5:]
    elif ":" in name:
        prefix, name = name.split(":", 1)
        if prefix == "xmlns":
            return AttributeKind.URL
    if name.startswith("on"):
        return AttributeKind.JS
    if name == "style":
        return AttributeKind.CSS
    if name == "srcset":
        return AttributeKind.SRCSET
    if name == "srcdoc":
        return AttributeKind.PLAIN
    if name in _URL_ATTRIBUTES:
        return AttributeKind.URL
    if any(part in name for part in ("src", "uri", "url")):
        return AttributeKind.URL
    return AttributeKind.PLAIN


_JS_STATES = frozenset(
    {
        ContextKind.JS,
        ContextKind.JS_DQ_STRING,
        ContextKind.JS_SQ_STRING,
        ContextKind.JS_TEMPLATE,
        ContextKind.JS_REGEXP,
        ContextKind.JS_BLOCK_COMMENT,
        ContextKind.JS_LINE_COMMENT,
    }
)
_JS_LITERAL_STATES = frozenset(
    {
        ContextKind.JS_DQ_STRING,
        ContextKind.JS_SQ_STRING,
        ContextKind.JS_TEMPLATE,
        ContextKind.JS_REGEXP,
    }
)
_CSS_STATES = frozenset(
    {
        ContextKind.CSS,
        ContextKind.CSS_DQ_STRING,
        ContextKind.CSS_SQ_STRING,
        ContextKind.CSS_DQ_URL,
        ContextKind.CSS_SQ_URL,
        ContextKind.CSS_URL,
        ContextKind.CSS_BLOCK_COMMENT,
        ContextKind.CSS_LINE_COMMENT,
    }
)
_JS_NEWLINES = "\n\r\u2028\u2029"
_JS_WHITESPACE = (
    "\f\n\r\t\v \u00a0\u1680\u2000\u2001\u2002\u2003\u2004\u2005"
    "\u2006\u2007\u2008\u2009\u200a\u2028\u2029\u202f\u205f\u3000\ufeff"
)
_REGEXP_PRECEDER_KEYWORDS = frozenset(
    {
        "break",
        "case",
        "continue",
        "delete",
        "do",
        "else",
        "finally",
        "in",
        "instanceof",
        "return",
        "throw",
        "try",
        "typeof",
        "void",
    }
)
_JS_MIME_TYPES = frozenset(
    {
        "",
        "application/ecmascript",
        "application/javascript",
        "application/json",
        "application/ld+json",
        "application/x-ecmascript",
        "application/x-javascript",
        "module",
        "text/ecmascript",
        "text/javascript",
        "text/javascript1.0",
        "text/javascript1.1",
        "text/javascript1.2",
        "text/javascript1.3",
        "text/javascript1.4",
        "text/javascript1.5",
        "text/jscript",
        "text/livescript",
        "text/x-ecmascript",
        "text/x-javascript",
    }
)


def _next_js_boundary(text: str, index: int, delimiter: str) -> int:
    specials = "\"`'/{}<-#"
    if delimiter:
        specials += delimiter
    for cursor in range(index, len(text)):
        character = text[cursor]
        if character in specials or (not delimiter and character.isspace()):
            return cursor
    return len(text)


def _js_attribute_boundary(text: str, index: int, delimiter: str) -> int:
    if delimiter in {'"', "'"}:
        boundary = text.find(delimiter, index)
        return len(text) if boundary < 0 else boundary
    for cursor in range(index, len(text)):
        if text[cursor].isspace() or text[cursor] == ">":
            return cursor
    return len(text)


def _next_css_boundary(text: str, index: int, delimiter: str) -> int:
    specials = "(\"'/<"
    if delimiter:
        specials += delimiter
    for cursor in range(index, len(text)):
        character = text[cursor]
        if character in specials or (not delimiter and character.isspace()):
            return cursor
    return len(text)


def _css_attribute_boundary(text: str, index: int, delimiter: str) -> int:
    return _js_attribute_boundary(text, index, delimiter)


def _ends_with_css_keyword(value: str, keyword: str) -> bool:
    value = value.rstrip("\t\n\f\r ")
    if len(value) < len(keyword):
        return False
    start = len(value) - len(keyword)
    if start and _is_css_name_character(value[start - 1]):
        return False
    return value[start:].casefold() == keyword


def _is_css_name_character(character: str) -> bool:
    codepoint = ord(character)
    return (
        (character.isascii() and (character.isalnum() or character in "-_"))
        or 0x80 <= codepoint <= 0xD7FF
        or 0xE000 <= codepoint <= 0xFFFD
        or 0x10000 <= codepoint <= 0x10FFFF
    )


def _is_style_end(text: str, index: int) -> bool:
    if not text[index:].casefold().startswith("</style"):
        return False
    following = index + len("</style")
    return following < len(text) and text[following] in "> \t\n\f/"


def _find_special_tag_end(text: str, index: int, element: str) -> int:
    marker = f"</{element}"
    cursor = index
    while (boundary := text.find("</", cursor)) >= 0:
        following = boundary + len(marker)
        if (
            _ascii_equal_fold(text[boundary:following], marker)
            and following < len(text)
            and text[following] in "> \t\n\f/"
        ):
            return boundary
        cursor = boundary + 2
    return -1


def _escape_rcdata_literal(value: str) -> str:
    output: list[str] = []
    cursor = 0
    while (boundary := value.find("<", cursor)) >= 0:
        output.append(value[cursor:boundary])
        output.append("<" if _is_doctype_prefix(value, boundary) else "&lt;")
        cursor = boundary + 1
    output.append(value[cursor:])
    return "".join(output)


def _ascii_equal_fold(left: str, right: str) -> bool:
    if len(left) != len(right):
        return False
    return all(
        (character.lower() if character.isascii() else character)
        == (expected.lower() if expected.isascii() else expected)
        for character, expected in zip(left, right, strict=True)
    )


def _is_doctype_prefix(text: str, index: int) -> bool:
    marker = "<!DOCTYPE"
    return _ascii_equal_fold(text[index : index + len(marker)], marker)


def _meta_content_url_active(value: str) -> bool:
    return re.search(r"(?:^|[;,\s])url\s*=\s*$", value, re.IGNORECASE) is not None


def _css_escape_end(text: str, index: int) -> int:
    if index + 1 == len(text):
        return index + 1
    cursor = index + 1
    if text[cursor] not in "0123456789abcdefABCDEF":
        return cursor + 1
    cursor += 1
    while (
        cursor < len(text)
        and cursor < index + 7
        and text[cursor] in "0123456789abcdefABCDEF"
    ):
        cursor += 1
    if cursor < len(text) and text[cursor] in "\t\n\f ":
        cursor += 1
    elif cursor < len(text) and text[cursor] == "\r":
        cursor += 2 if cursor + 1 < len(text) and text[cursor + 1] == "\n" else 1
    return cursor


def _next_js_context(value: str, preceding: JSContext) -> JSContext:
    value = value.rstrip(_JS_WHITESPACE)
    if not value:
        return preceding
    final = value[-1]
    if final in "+-":
        start = len(value) - 1
        while start > 0 and value[start - 1] == final:
            start -= 1
        return JSContext.REGEXP if (len(value) - start) % 2 else JSContext.DIVISION
    if final == ".":
        return (
            JSContext.DIVISION
            if len(value) > 1 and value[-2].isdigit()
            else JSContext.REGEXP
        )
    if final in ",<>=*%&|^?!~([{;:":
        return JSContext.REGEXP
    if final == "}":
        return JSContext.REGEXP
    cursor = len(value)
    while cursor > 0 and _is_js_identifier_part(value[cursor - 1]):
        cursor -= 1
    if value[cursor:] in _REGEXP_PRECEDER_KEYWORDS:
        return JSContext.REGEXP
    return JSContext.DIVISION


def _is_js_identifier_part(character: str) -> bool:
    return (
        character == "$"
        or character == "_"
        or (character.isascii() and character.isalnum())
    )


def _is_ascii_alpha(character: str) -> bool:
    return character.isascii() and character.isalpha()


def _is_ascii_alphanumeric(character: str) -> bool:
    return character.isascii() and character.isalnum()


def _special_script_prefix(text: str, index: int) -> str:
    lowered = text[index:].casefold()
    for marker in ("</script", "<script", "<!--"):
        if lowered.startswith(marker):
            return text[index : index + len(marker)]
    return ""


def _is_script_end(text: str, index: int) -> bool:
    if not text[index:].casefold().startswith("</script"):
        return False
    following = index + len("</script")
    return following < len(text) and text[following] in "> \t\n\f/"


def _is_js_type(value: str) -> bool:
    mime_type = value.partition(";")[0].strip().casefold()
    return mime_type in _JS_MIME_TYPES
