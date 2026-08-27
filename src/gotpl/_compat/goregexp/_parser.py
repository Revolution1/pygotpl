"""Small owned parser for the translated RE2 syntax consumed by the NFA."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import cast


class Op(Enum):
    LITERAL = auto()
    NOT_LITERAL = auto()
    ANY = auto()
    IN = auto()
    CATEGORY = auto()
    AT = auto()
    SUBPATTERN = auto()
    BRANCH = auto()
    MAX_REPEAT = auto()
    MIN_REPEAT = auto()
    FAILURE = auto()
    ASSERT_NOT = auto()
    NEGATE = auto()
    RANGE = auto()


class Category(Enum):
    DIGIT = auto()
    NOT_DIGIT = auto()
    SPACE = auto()
    NOT_SPACE = auto()
    WORD = auto()
    NOT_WORD = auto()


class Assertion(Enum):
    BEGINNING_STRING = auto()
    BEGINNING = auto()
    BEGINNING_LINE = auto()
    END_STRING = auto()
    END = auto()
    BOUNDARY = auto()
    NON_BOUNDARY = auto()


LITERAL = Op.LITERAL
NOT_LITERAL = Op.NOT_LITERAL
ANY = Op.ANY
IN = Op.IN
CATEGORY = Op.CATEGORY
AT = Op.AT
SUBPATTERN = Op.SUBPATTERN
BRANCH = Op.BRANCH
MAX_REPEAT = Op.MAX_REPEAT
MIN_REPEAT = Op.MIN_REPEAT
FAILURE = Op.FAILURE
ASSERT_NOT = Op.ASSERT_NOT
NEGATE = Op.NEGATE
RANGE = Op.RANGE

CATEGORY_DIGIT = Category.DIGIT
CATEGORY_NOT_DIGIT = Category.NOT_DIGIT
CATEGORY_SPACE = Category.SPACE
CATEGORY_NOT_SPACE = Category.NOT_SPACE
CATEGORY_WORD = Category.WORD
CATEGORY_NOT_WORD = Category.NOT_WORD

AT_BEGINNING_STRING = Assertion.BEGINNING_STRING
AT_BEGINNING = Assertion.BEGINNING
AT_BEGINNING_LINE = Assertion.BEGINNING_LINE
AT_END_STRING = Assertion.END_STRING
AT_END = Assertion.END
AT_BOUNDARY = Assertion.BOUNDARY
AT_NON_BOUNDARY = Assertion.NON_BOUNDARY

SRE_FLAG_IGNORECASE = 2
SRE_FLAG_MULTILINE = 8
SRE_FLAG_DOTALL = 16
SRE_FLAG_ASCII = 256
MAXREPEAT = object()

Node = tuple[Op, object]


@dataclass(slots=True)
class State:
    flags: int = 0
    groups: int = 1
    groupdict: dict[str, int] = field(default_factory=lambda: {})


class Sequence(list[Node]):
    """List-like parsed sequence carrying capture and flag state."""

    def __init__(self, values: list[Node], state: State) -> None:
        super().__init__(values)
        self.state = state


class _Parser:
    def __init__(self, pattern: str, flags: int) -> None:
        self.pattern = pattern
        self.position = 0
        self.state = State(flags=flags)

    def parse(self) -> Sequence:
        result = self._expression(self.state.flags, stop_at_close=False)
        if self.position != len(self.pattern):
            raise re.error("unexpected closing parenthesis")
        return Sequence(result, self.state)

    def _expression(self, flags: int, *, stop_at_close: bool) -> list[Node]:
        alternatives = [self._sequence(flags, stop_at_close=stop_at_close)]
        while self._peek() == "|":
            self.position += 1
            alternatives.append(self._sequence(flags, stop_at_close=stop_at_close))
        if len(alternatives) == 1:
            return alternatives[0]
        return [(BRANCH, (None, alternatives))]

    def _sequence(self, flags: int, *, stop_at_close: bool) -> list[Node]:
        result: list[Node] = []
        while self.position < len(self.pattern):
            character = self._peek()
            if character == "|" or character == ")":
                if character == ")" and not stop_at_close:
                    raise re.error("unexpected closing parenthesis")
                break
            atom = self._atom(flags)
            result.append(self._quantified(atom))
        return result

    def _atom(self, flags: int) -> Node:
        character = self._take()
        if character in "*+?}":
            raise re.error("missing argument to repetition operator")
        if character == ".":
            return ANY, None
        if character == "^":
            return AT, AT_BEGINNING
        if character == "$":
            return AT, AT_END
        if character == "[":
            return IN, tuple(self._character_class(flags))
        if character == "(":
            return self._group(flags)
        if character == "\\":
            return self._escape(flags, in_class=False)
        return LITERAL, ord(character)

    def _group(self, flags: int) -> Node:
        group: int | None
        nested_flags = flags
        if self.pattern.startswith("?!", self.position):
            self.position += 2
            if self._peek() != ")":
                raise re.error("invalid or unsupported Perl syntax")
            self.position += 1
            return FAILURE, None
        if self.pattern.startswith("?:", self.position):
            self.position += 2
            group = None
        elif self.pattern.startswith("?P<", self.position):
            end = self.pattern.find(">", self.position + 3)
            if end < 0:
                raise re.error("invalid named capture")
            name = self.pattern[self.position + 3 : end]
            if not name or not name.isidentifier() or name in self.state.groupdict:
                raise re.error("invalid named capture")
            group = self._new_group()
            self.state.groupdict[name] = group
            self.position = end + 1
        elif self._peek() == "?":
            nested_flags = self._flags(flags)
            group = None
        else:
            group = self._new_group()
        body = self._expression(nested_flags, stop_at_close=True)
        if self._peek() != ")":
            raise re.error("missing closing parenthesis")
        self.position += 1
        added = nested_flags & ~flags
        removed = flags & ~nested_flags
        return SUBPATTERN, (group, added, removed, body)

    def _flags(self, flags: int) -> int:
        self.position += 1
        enabled = 0
        disabled = 0
        target = "enabled"
        values = {
            "i": SRE_FLAG_IGNORECASE,
            "m": SRE_FLAG_MULTILINE,
            "s": SRE_FLAG_DOTALL,
            "a": SRE_FLAG_ASCII,
        }
        while self.position < len(self.pattern):
            character = self._take()
            if character == ":":
                return (flags | enabled) & ~disabled
            if character == "-" and target == "enabled":
                target = "disabled"
                continue
            if character not in values:
                raise re.error("invalid or unsupported Perl syntax")
            if target == "enabled":
                enabled |= values[character]
            else:
                disabled |= values[character]
        raise re.error("missing closing parenthesis")

    def _new_group(self) -> int:
        group = self.state.groups
        self.state.groups += 1
        return group

    def _quantified(self, atom: Node) -> Node:
        if self.position >= len(self.pattern):
            return atom
        character = self._peek()
        minimum: int
        maximum: int | object
        if character == "*":
            minimum, maximum = 0, MAXREPEAT
            self.position += 1
        elif character == "+":
            minimum, maximum = 1, MAXREPEAT
            self.position += 1
        elif character == "?":
            minimum, maximum = 0, 1
            self.position += 1
        elif character == "{":
            parsed = self._repeat_count()
            if parsed is None:
                return atom
            minimum, maximum = parsed
        else:
            return atom
        greedy = True
        if self._peek() == "?":
            greedy = False
            self.position += 1
        return (MAX_REPEAT if greedy else MIN_REPEAT), (minimum, maximum, [atom])

    def _repeat_count(self) -> tuple[int, int | object] | None:
        match = re.match(r"\{(\d+)(?:,(\d*))?\}", self.pattern[self.position :])
        if match is None:
            return None
        minimum = int(match.group(1))
        if match.group(2) is None:
            maximum: int | object = minimum
        elif match.group(2) == "":
            maximum = MAXREPEAT
        else:
            maximum = int(match.group(2))
        if isinstance(maximum, int) and maximum < minimum:
            raise re.error("invalid repeat count")
        self.position += len(match.group(0))
        return minimum, maximum

    def _character_class(self, flags: int) -> list[Node]:
        entries: list[Node] = []
        if self._peek() == "^":
            self.position += 1
            entries.append((NEGATE, None))
        first = True
        while self.position < len(self.pattern):
            if self._peek() == "]" and not first:
                self.position += 1
                return entries
            first = False
            start = self._class_atom(flags)
            if self._peek() == "-" and self._peek(1) not in {"", "]"}:
                self.position += 1
                end = self._class_atom(flags)
                if start[0] is not LITERAL or end[0] is not LITERAL:
                    raise re.error("invalid character class range")
                start_codepoint = cast(int, start[1])
                end_codepoint = cast(int, end[1])
                if start_codepoint > end_codepoint:
                    raise re.error("invalid character class range")
                entries.append((RANGE, (start_codepoint, end_codepoint)))
            else:
                entries.append(start)
        raise re.error("missing closing bracket")

    def _class_atom(self, flags: int) -> Node:
        character = self._take()
        if character == "\\":
            return self._escape(flags, in_class=True)
        return LITERAL, ord(character)

    def _escape(self, flags: int, *, in_class: bool) -> Node:
        if self.position >= len(self.pattern):
            raise re.error("invalid escape sequence")
        character = self._take()
        categories = {
            "d": CATEGORY_DIGIT,
            "D": CATEGORY_NOT_DIGIT,
            "s": CATEGORY_SPACE,
            "S": CATEGORY_NOT_SPACE,
            "w": CATEGORY_WORD,
            "W": CATEGORY_NOT_WORD,
        }
        if character in categories:
            return CATEGORY, categories[character]
        if character in "bB" and not in_class:
            return AT, AT_BOUNDARY if character == "b" else AT_NON_BOUNDARY
        if character == "A" and not in_class:
            return AT, AT_BEGINNING_STRING
        if character == "Z" and not in_class:
            return AT, AT_END_STRING
        if character == "b" and in_class:
            return LITERAL, 8
        lengths = {"x": 2, "u": 4, "U": 8}
        if character in lengths:
            length = lengths[character]
            digits = self.pattern[self.position : self.position + length]
            if len(digits) != length or any(
                item not in "0123456789abcdefABCDEF" for item in digits
            ):
                raise re.error("invalid hexadecimal escape")
            self.position += length
            codepoint = int(digits, 16)
            if codepoint > 0x10FFFF:
                raise re.error("invalid hexadecimal escape")
            return LITERAL, codepoint
        escapes = {"n": "\n", "r": "\r", "t": "\t", "f": "\f", "v": "\v"}
        if character in escapes:
            return LITERAL, ord(escapes[character])
        return LITERAL, ord(character)

    def _peek(self, offset: int = 0) -> str:
        position = self.position + offset
        return "" if position >= len(self.pattern) else self.pattern[position]

    def _take(self) -> str:
        if self.position >= len(self.pattern):
            raise re.error("unexpected end of pattern")
        character = self.pattern[self.position]
        self.position += 1
        return character


def parse(pattern: str, flags: int = 0) -> Sequence:
    """Parse translated RE2 syntax without CPython-private modules."""
    return _Parser(pattern, flags).parse()
