"""Immutable, source-mapped template syntax nodes."""

from dataclasses import dataclass
from typing import TypeAlias


@dataclass(frozen=True, slots=True)
class TextNode:
    """Literal template text."""

    text: str
    start: int
    end: int


@dataclass(frozen=True, slots=True)
class DotNode:
    """The current template value."""

    start: int
    end: int


@dataclass(frozen=True, slots=True)
class NilNode:
    """The Go untyped nil constant."""

    start: int
    end: int


@dataclass(frozen=True, slots=True)
class BoolNode:
    """A boolean constant."""

    value: bool
    start: int
    end: int


@dataclass(frozen=True, slots=True)
class NumberNode:
    """A numeric or imaginary constant in Go syntax."""

    text: str
    start: int
    end: int


@dataclass(frozen=True, slots=True)
class ComplexNode:
    """A complex constant in Go syntax."""

    text: str
    start: int
    end: int


@dataclass(frozen=True, slots=True)
class StringNode:
    """A quoted or raw string constant."""

    value: str
    quoted: str
    start: int
    end: int


@dataclass(frozen=True, slots=True)
class CharacterNode:
    """A character constant in Go syntax."""

    value: str
    quoted: str
    start: int
    end: int


@dataclass(frozen=True, slots=True)
class IdentifierNode:
    """A template function identifier."""

    name: str
    start: int
    end: int


@dataclass(frozen=True, slots=True)
class FieldNode:
    """A field chain rooted at dot."""

    fields: tuple[str, ...]
    start: int
    end: int


@dataclass(frozen=True, slots=True)
class VariableNode:
    """A variable optionally followed by a field chain."""

    name: str
    fields: tuple[str, ...]
    start: int
    end: int


@dataclass(frozen=True, slots=True)
class ParenthesizedNode:
    """A parenthesized pipeline optionally followed by fields."""

    pipeline: "PipeNode"
    fields: tuple[str, ...]
    start: int
    end: int


TermNode: TypeAlias = (
    DotNode
    | NilNode
    | BoolNode
    | NumberNode
    | ComplexNode
    | StringNode
    | CharacterNode
    | IdentifierNode
    | FieldNode
    | VariableNode
    | ParenthesizedNode
)


@dataclass(frozen=True, slots=True)
class CommandNode:
    """A command containing a function or value and its arguments."""

    arguments: tuple[TermNode, ...]
    start: int
    end: int


@dataclass(frozen=True, slots=True)
class PipeNode:
    """A declaration or assignment followed by piped commands."""

    declarations: tuple[VariableNode, ...]
    is_assignment: bool
    commands: tuple[CommandNode, ...]
    start: int
    end: int


@dataclass(frozen=True, slots=True)
class ActionNode:
    """An output-producing pipeline action."""

    pipeline: PipeNode
    start: int
    end: int


@dataclass(frozen=True, slots=True)
class IfNode:
    """An if branch with an optional else list."""

    pipeline: PipeNode
    body: "ListNode"
    else_body: "ListNode | None"
    start: int
    end: int


@dataclass(frozen=True, slots=True)
class WithNode:
    """A with branch with an optional else list."""

    pipeline: PipeNode
    body: "ListNode"
    else_body: "ListNode | None"
    start: int
    end: int


@dataclass(frozen=True, slots=True)
class RangeNode:
    """A range branch with an optional else list."""

    pipeline: PipeNode
    body: "ListNode"
    else_body: "ListNode | None"
    start: int
    end: int


@dataclass(frozen=True, slots=True)
class BreakNode:
    """A break action inside a range."""

    start: int
    end: int


@dataclass(frozen=True, slots=True)
class ContinueNode:
    """A continue action inside a range."""

    start: int
    end: int


@dataclass(frozen=True, slots=True)
class TemplateCallNode:
    """An invocation of an associated named template."""

    name: str
    pipeline: PipeNode | None
    start: int
    end: int


@dataclass(frozen=True, slots=True)
class BlockNode:
    """A block definition and invocation."""

    name: str
    pipeline: PipeNode
    body: "ListNode"
    start: int
    end: int


TemplateNode: TypeAlias = (
    TextNode
    | ActionNode
    | IfNode
    | WithNode
    | RangeNode
    | BreakNode
    | ContinueNode
    | TemplateCallNode
    | BlockNode
)


@dataclass(frozen=True, slots=True)
class ListNode:
    """An ordered sequence of template nodes."""

    nodes: tuple[TemplateNode, ...]


@dataclass(frozen=True, slots=True)
class DefinitionNode:
    """A named template definition."""

    name: str
    body: ListNode
    start: int
    end: int


@dataclass(frozen=True, slots=True)
class ParsedTemplate:
    """A root template and its associated definitions."""

    name: str
    root: ListNode
    definitions: tuple[DefinitionNode, ...]
