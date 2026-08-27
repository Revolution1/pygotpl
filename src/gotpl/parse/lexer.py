"""Lexer for Go template source."""

import re
from collections.abc import Collection, Generator, Iterator
from dataclasses import dataclass

from gotpl.errors import TemplateSyntaxError

from .tokens import Token, TokenKind

_SPACE_CHARS = " \t\r\n"
_KEYWORDS = {
    "block": TokenKind.BLOCK,
    "break": TokenKind.BREAK,
    "continue": TokenKind.CONTINUE,
    "define": TokenKind.DEFINE,
    "else": TokenKind.ELSE,
    "end": TokenKind.END,
    "if": TokenKind.IF,
    "nil": TokenKind.NIL,
    "range": TokenKind.RANGE,
    "template": TokenKind.TEMPLATE,
    "with": TokenKind.WITH,
}
_DIGITS = r"[0-9](?:_?[0-9])*"
_BINARY_DIGITS = r"[01](?:_?[01])*"
_OCTAL_DIGITS = r"[0-7](?:_?[0-7])*"
_HEX_DIGITS = r"[0-9a-fA-F](?:_?[0-9a-fA-F])*"
_EXPONENT = rf"[eE][+-]?{_DIGITS}"
_BINARY_INTEGER = rf"0[bB]_?{_BINARY_DIGITS}"
_EXPLICIT_OCTAL_INTEGER = rf"0[oO]_?{_OCTAL_DIGITS}"
_HEX_INTEGER = rf"0[xX]_?{_HEX_DIGITS}"
_LEGACY_OCTAL_INTEGER = rf"0(?:_?{_OCTAL_DIGITS})+"
_DECIMAL_INTEGER = r"(?:0|[1-9](?:_?[0-9])*)"
_INTEGER_ATOM = (
    rf"(?:{_BINARY_INTEGER}|{_EXPLICIT_OCTAL_INTEGER}|{_HEX_INTEGER}|"
    rf"{_LEGACY_OCTAL_INTEGER}|{_DECIMAL_INTEGER})"
)
_DECIMAL_FLOAT = (
    rf"(?:(?:{_DIGITS}\.(?:{_DIGITS})?|\.{_DIGITS})(?:{_EXPONENT})?"
    rf"|{_DIGITS}{_EXPONENT})"
)
_HEX_MANTISSA = rf"(?:{_HEX_DIGITS}(?:\.(?:{_HEX_DIGITS})?)?|\.{_HEX_DIGITS})"
_HEX_FLOAT = rf"0[xX]_?{_HEX_MANTISSA}[pP][+-]?{_DIGITS}"
_ATOM = rf"(?:{_HEX_FLOAT}|{_DECIMAL_FLOAT}|{_INTEGER_ATOM})"
_NUMBER_PATTERN = re.compile(rf"[+-]?{_ATOM}i?")
_COMPLEX_PATTERN = re.compile(rf"[+-]?{_ATOM}[+-]{_ATOM}i")


@dataclass(frozen=True, slots=True)
class _SourceMap:
    byte_offsets: tuple[int, ...]
    lines: tuple[int, ...]

    @classmethod
    def build(cls, source: str) -> "_SourceMap":
        byte_offsets = [0]
        lines = [1]
        byte_offset = 0
        line = 1
        for character in source:
            byte_offset += len(character.encode("utf-8"))
            if character == "\n":
                line += 1
            byte_offsets.append(byte_offset)
            lines.append(line)
        return cls(tuple(byte_offsets), tuple(lines))

    def token(
        self, kind: TokenKind, value: str, character_start: int, character_end: int
    ) -> Token:
        return Token(
            kind,
            value,
            self.byte_offsets[character_start],
            self.byte_offsets[character_end],
            self.lines[character_start],
        )


def lex(
    source: str,
    *,
    left_delimiter: str = "{{",
    right_delimiter: str = "}}",
    emit_comments: bool = False,
    functions: Collection[str] = (),
) -> Iterator[Token]:
    """Yield source-mapped tokens for a Go template."""

    if not left_delimiter or not right_delimiter:
        raise ValueError("template delimiters must not be empty")
    utf8_size(source)
    source_map = _SourceMap.build(source)
    cursor = 0
    while cursor < len(source):
        action_start = source.find(left_delimiter, cursor)
        if action_start < 0:
            yield source_map.token(TokenKind.TEXT, source[cursor:], cursor, len(source))
            cursor = len(source)
            break

        action_content = action_start + len(left_delimiter)
        left_trim = _has_left_trim(source, action_content)
        if action_start > cursor:
            text_end = action_start
            if left_trim:
                while text_end > cursor and source[text_end - 1] in _SPACE_CHARS:
                    text_end -= 1
            if text_end > cursor:
                yield source_map.token(
                    TokenKind.TEXT,
                    source[cursor:text_end],
                    cursor,
                    text_end,
                )
        if left_trim:
            action_content += 2

        if source.startswith("/*", action_content):
            cursor = yield from _lex_comment(
                source,
                source_map,
                action_content,
                right_delimiter,
                emit_comments,
            )
            continue

        yield source_map.token(
            TokenKind.LEFT_DELIMITER,
            left_delimiter,
            action_start,
            action_start + len(left_delimiter),
        )
        cursor = yield from _lex_action(
            source,
            source_map,
            action_start,
            action_content,
            right_delimiter,
            functions,
        )

    yield source_map.token(TokenKind.EOF, "", len(source), len(source))


def _lex_comment(
    source: str,
    source_map: _SourceMap,
    comment_start: int,
    right_delimiter: str,
    emit_comments: bool,
) -> Generator[Token, None, int]:
    comment_end = source.find("*/", comment_start + 2)
    if comment_end < 0:
        raise _syntax_error(source, "unclosed comment", comment_start)
    comment_end += 2
    right_start, right_trim = _comment_right_delimiter(
        source, comment_end, right_delimiter
    )
    if right_start < 0:
        raise _syntax_error(
            source, "comment ends before closing delimiter", comment_end
        )
    if emit_comments:
        yield source_map.token(
            TokenKind.COMMENT,
            source[comment_start:comment_end],
            comment_start,
            comment_end,
        )
    cursor = right_start + len(right_delimiter)
    if right_trim:
        cursor = _skip_space(source, cursor)
    return cursor


def _lex_action(
    source: str,
    source_map: _SourceMap,
    action_start: int,
    position: int,
    right_delimiter: str,
    functions: Collection[str],
) -> Generator[Token, None, int]:
    paren_depth = 0
    while position < len(source):
        if source.startswith(right_delimiter, position):
            if paren_depth:
                raise _syntax_error(source, "unclosed left paren", position)
            cursor = position + len(right_delimiter)
            yield source_map.token(
                TokenKind.RIGHT_DELIMITER,
                right_delimiter,
                position,
                cursor,
            )
            return cursor

        character = source[position]
        if character in _SPACE_CHARS:
            space_end = position + 1
            while space_end < len(source) and source[space_end] in _SPACE_CHARS:
                space_end += 1
            if (
                paren_depth == 0
                and space_end < len(source)
                and source[space_end] == "-"
                and source.startswith(right_delimiter, space_end + 1)
            ):
                right_start = space_end + 1
                cursor = right_start + len(right_delimiter)
                yield source_map.token(
                    TokenKind.RIGHT_DELIMITER,
                    right_delimiter,
                    right_start,
                    cursor,
                )
                return _skip_space(source, cursor)
            yield source_map.token(
                TokenKind.SPACE,
                source[position:space_end],
                position,
                space_end,
            )
            position = space_end
        elif character == "." and _next_is_digit(source, position):
            number_end = _scan_number(source, position)
            yield _number_token(source, source_map, position, number_end)
            position = number_end
        elif character == ".":
            field_end = position + 1
            while field_end < len(source) and _is_alphanumeric(source[field_end]):
                field_end += 1
            kind = TokenKind.DOT if field_end == position + 1 else TokenKind.FIELD
            yield source_map.token(
                kind, source[position:field_end], position, field_end
            )
            position = field_end
        elif character == "$":
            variable_end = position + 1
            while variable_end < len(source) and _is_alphanumeric(source[variable_end]):
                variable_end += 1
            yield source_map.token(
                TokenKind.VARIABLE,
                source[position:variable_end],
                position,
                variable_end,
            )
            position = variable_end
        elif character in {'"', "'", "`"}:
            literal_end = _scan_quoted(source, position, character)
            kind = {
                '"': TokenKind.STRING,
                "'": TokenKind.CHAR_CONSTANT,
                "`": TokenKind.RAW_STRING,
            }[character]
            yield source_map.token(
                kind,
                source[position:literal_end],
                position,
                literal_end,
            )
            position = literal_end
        elif character.isdigit() or _starts_signed_number(source, position):
            number_end = _scan_number(source, position)
            yield _number_token(source, source_map, position, number_end)
            position = number_end
        elif character.isalpha() or character == "_":
            identifier_end = position + 1
            while identifier_end < len(source) and _is_alphanumeric(
                source[identifier_end]
            ):
                identifier_end += 1
            value = source[position:identifier_end]
            if value in {"true", "false"}:
                kind = TokenKind.BOOL
            elif value in {"break", "continue"} and value in functions:
                kind = TokenKind.IDENTIFIER
            else:
                kind = _KEYWORDS.get(value, TokenKind.IDENTIFIER)
            yield source_map.token(kind, value, position, identifier_end)
            position = identifier_end
        elif source.startswith(":=", position):
            yield source_map.token(TokenKind.DECLARE, ":=", position, position + 2)
            position += 2
        elif character == "=":
            yield source_map.token(TokenKind.ASSIGN, "=", position, position + 1)
            position += 1
        elif character == "|":
            yield source_map.token(TokenKind.PIPE, "|", position, position + 1)
            position += 1
        elif character == "(":
            paren_depth += 1
            yield source_map.token(TokenKind.LEFT_PAREN, "(", position, position + 1)
            position += 1
        elif character == ")":
            if paren_depth == 0:
                raise _syntax_error(source, "unexpected right paren", position)
            paren_depth -= 1
            yield source_map.token(TokenKind.RIGHT_PAREN, ")", position, position + 1)
            position += 1
        elif character.isprintable():
            yield source_map.token(TokenKind.CHAR, character, position, position + 1)
            position += 1
        else:
            raise _syntax_error(
                source, f"unrecognized character {character!r}", position
            )

    message = "unclosed left paren" if paren_depth else "unclosed action"
    raise _syntax_error(source, message, action_start)


def _has_left_trim(source: str, content_start: int) -> bool:
    return (
        content_start + 1 < len(source)
        and source[content_start] == "-"
        and source[content_start + 1] in _SPACE_CHARS
    )


def _is_alphanumeric(character: str) -> bool:
    return character == "_" or character.isalpha() or character.isdecimal()


def _next_is_digit(source: str, position: int) -> bool:
    return position + 1 < len(source) and source[position + 1].isdigit()


def _starts_signed_number(source: str, position: int) -> bool:
    return (
        source[position] in "+-"
        and position + 1 < len(source)
        and (source[position + 1].isdigit() or source[position + 1] == ".")
    )


def _scan_quoted(source: str, start: int, quote: str) -> int:
    if quote == "`":
        closing = source.find("`", start + 1)
        if closing < 0:
            raise _syntax_error(source, "unterminated raw quoted string", start)
        return closing + 1

    position = start + 1
    while position < len(source):
        character = source[position]
        if character == quote:
            return position + 1
        if character == "\n":
            break
        if character == "\\":
            position += 2
        else:
            position += 1
    label = "character constant" if quote == "'" else "quoted string"
    raise _syntax_error(source, f"unterminated {label}", start)


def _scan_number(source: str, start: int) -> int:
    position = start
    while position < len(source):
        character = source[position]
        if not (character.isalnum() or character in ".+-_"):
            break
        position += 1
    return position


def _number_token(source: str, source_map: _SourceMap, start: int, end: int) -> Token:
    value = source[start:end]
    if _COMPLEX_PATTERN.fullmatch(value):
        kind = TokenKind.COMPLEX
    elif _NUMBER_PATTERN.fullmatch(value):
        kind = TokenKind.NUMBER
    else:
        raise _syntax_error(source, f"bad number syntax: {value!r}", start)
    return source_map.token(kind, value, start, end)


def _skip_space(source: str, position: int) -> int:
    while position < len(source) and source[position] in _SPACE_CHARS:
        position += 1
    return position


def _comment_right_delimiter(
    source: str, comment_end: int, right_delimiter: str
) -> tuple[int, bool]:
    if source.startswith(right_delimiter, comment_end):
        return comment_end, False
    marker_end = comment_end + 2
    if (
        marker_end <= len(source)
        and source[comment_end] in _SPACE_CHARS
        and source[comment_end + 1] == "-"
        and source.startswith(right_delimiter, marker_end)
    ):
        return marker_end, True
    return -1, False


def _syntax_error(
    source: str, message: str, character_position: int
) -> TemplateSyntaxError:
    prefix = source[:character_position]
    line = prefix.count("\n") + 1
    line_start = prefix.rfind("\n") + 1
    column = len(source[line_start:character_position].encode("utf-8")) + 1
    position = len(prefix.encode("utf-8"))
    return TemplateSyntaxError(
        message,
        position=position,
        line=line,
        column=column,
    )


def utf8_size(source: str) -> int:
    try:
        return len(source.encode("utf-8"))
    except UnicodeEncodeError as error:
        raise _syntax_error(source, "invalid Unicode surrogate", error.start) from error
