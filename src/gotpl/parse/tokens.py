"""Source-mapped lexer tokens."""

from dataclasses import dataclass
from enum import Enum, auto


class TokenKind(Enum):
    """Kinds emitted by the template lexer."""

    TEXT = auto()
    LEFT_DELIMITER = auto()
    RIGHT_DELIMITER = auto()
    SPACE = auto()
    DOT = auto()
    COMMENT = auto()
    BOOL = auto()
    CHAR = auto()
    CHAR_CONSTANT = auto()
    COMPLEX = auto()
    ASSIGN = auto()
    DECLARE = auto()
    FIELD = auto()
    IDENTIFIER = auto()
    LEFT_PAREN = auto()
    NUMBER = auto()
    PIPE = auto()
    RAW_STRING = auto()
    RIGHT_PAREN = auto()
    STRING = auto()
    VARIABLE = auto()
    BLOCK = auto()
    BREAK = auto()
    CONTINUE = auto()
    DEFINE = auto()
    ELSE = auto()
    END = auto()
    IF = auto()
    NIL = auto()
    RANGE = auto()
    TEMPLATE = auto()
    WITH = auto()
    EOF = auto()


@dataclass(frozen=True, slots=True)
class Token:
    """A token and its half-open source range."""

    kind: TokenKind
    value: str
    start: int
    end: int
    line: int = 1
