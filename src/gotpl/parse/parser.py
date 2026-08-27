"""Recursive-descent parser for Go template source."""

import math
from collections.abc import Collection, Iterable
from dataclasses import dataclass

from gotpl.errors import TemplateSyntaxError

from .lexer import lex, utf8_size
from .nodes import (
    ActionNode,
    BlockNode,
    BoolNode,
    BreakNode,
    CharacterNode,
    CommandNode,
    ComplexNode,
    ContinueNode,
    DefinitionNode,
    DotNode,
    FieldNode,
    IdentifierNode,
    IfNode,
    ListNode,
    NilNode,
    NumberNode,
    ParenthesizedNode,
    ParsedTemplate,
    PipeNode,
    RangeNode,
    StringNode,
    TemplateCallNode,
    TemplateNode,
    TermNode,
    TextNode,
    VariableNode,
    WithNode,
)
from .semantic import validate_template
from .tokens import Token, TokenKind


@dataclass(frozen=True, slots=True)
class ParserLimits:
    """Resource limits applied before and during parsing."""

    max_source_bytes: int = 10_000_000
    max_tokens: int = 1_000_000
    max_nesting: int = 100

    def __post_init__(self) -> None:
        if min(self.max_source_bytes, self.max_tokens, self.max_nesting) < 1:
            raise ValueError("parser limits must be positive")


DEFAULT_LIMITS = ParserLimits()


def parse(
    source: str,
    *,
    left_delimiter: str = "{{",
    right_delimiter: str = "}}",
    limits: ParserLimits = DEFAULT_LIMITS,
    functions: Collection[str] = (),
) -> ListNode:
    """Parse template source and return its root syntax list."""

    return parse_template(
        source,
        left_delimiter=left_delimiter,
        right_delimiter=right_delimiter,
        limits=limits,
        functions=functions,
    ).root


def parse_template(
    source: str,
    *,
    name: str = "",
    left_delimiter: str = "{{",
    right_delimiter: str = "}}",
    limits: ParserLimits = DEFAULT_LIMITS,
    functions: Collection[str] = (),
) -> ParsedTemplate:
    """Parse a root template and all associated definitions."""

    source_size = utf8_size(source)
    if source_size > limits.max_source_bytes:
        raise TemplateSyntaxError(
            "template source size limit exceeded", position=0, line=1, column=1
        )
    tokens: list[Token] = []
    for token in lex(
        source,
        left_delimiter=left_delimiter,
        right_delimiter=right_delimiter,
        functions=functions,
    ):
        tokens.append(token)
        if len(tokens) > limits.max_tokens:
            raise TemplateSyntaxError(
                "template token limit exceeded",
                position=token.start,
                line=token.line,
                column=1,
            )
    template = _Parser(source, tuple(tokens), name, limits).parse_document()
    validate_template(source, template, functions=functions)
    return template


class _Parser:
    def __init__(
        self,
        source: str,
        tokens: tuple[Token, ...],
        name: str,
        limits: ParserLimits,
    ) -> None:
        self.source = source
        self.tokens = tokens
        self.name = name
        self.limits = limits
        self.index = 0
        self.range_depth = 0
        self.expression_depth = 0
        self.definitions: list[DefinitionNode] = []

    def parse_document(self) -> ParsedTemplate:
        root, _ = self.parse_list(set(), depth=0, top_level=True)
        self.expect(TokenKind.EOF)
        return ParsedTemplate(self.name, root, tuple(self.definitions))

    def parse_list(
        self, stop_kinds: set[TokenKind], *, depth: int, top_level: bool
    ) -> tuple[ListNode, TokenKind | None]:
        nodes: list[TemplateNode] = []
        while True:
            token = self.peek()
            if token.kind is TokenKind.EOF:
                if stop_kinds:
                    raise self.error(token, "unexpected EOF")
                return ListNode(tuple(nodes)), None
            if token.kind is TokenKind.TEXT:
                self.advance()
                nodes.append(TextNode(token.value, token.start, token.end))
                continue
            keyword = self.action_keyword()
            if keyword in stop_kinds:
                return ListNode(tuple(nodes)), keyword
            if keyword in {TokenKind.ELSE, TokenKind.END}:
                raise self.error(self.peek(), f"unexpected {keyword.name.lower()}")
            if keyword in {TokenKind.IF, TokenKind.WITH, TokenKind.RANGE}:
                nodes.append(self.parse_branch(keyword, depth))
            elif keyword is TokenKind.BREAK:
                nodes.append(self.parse_loop_control(is_break=True))
            elif keyword is TokenKind.CONTINUE:
                nodes.append(self.parse_loop_control(is_break=False))
            elif keyword is TokenKind.DEFINE:
                if not top_level:
                    raise self.error(self.peek(), "unexpected define in control body")
                self.parse_definition(depth)
            elif keyword is TokenKind.TEMPLATE:
                nodes.append(self.parse_template_call())
            elif keyword is TokenKind.BLOCK:
                nodes.append(self.parse_block(depth))
            else:
                nodes.append(self.parse_action())

    def action_keyword(self) -> TokenKind | None:
        index = self.index + 1
        while self.tokens[index].kind is TokenKind.SPACE:
            index += 1
        kind = self.tokens[index].kind
        if kind in {
            TokenKind.IF,
            TokenKind.WITH,
            TokenKind.RANGE,
            TokenKind.BREAK,
            TokenKind.CONTINUE,
            TokenKind.DEFINE,
            TokenKind.TEMPLATE,
            TokenKind.BLOCK,
            TokenKind.ELSE,
            TokenKind.END,
        }:
            return kind
        return None

    def parse_action(self) -> ActionNode:
        left = self.expect(TokenKind.LEFT_DELIMITER)
        self.skip_spaces()
        pipeline = self.parse_pipeline({TokenKind.RIGHT_DELIMITER})
        self.skip_spaces()
        right = self.expect(TokenKind.RIGHT_DELIMITER)
        return ActionNode(pipeline, left.start, right.end)

    def parse_branch(self, kind: TokenKind, depth: int) -> TemplateNode:
        if depth >= self.limits.max_nesting:
            raise self.error(self.peek(), "template nesting limit exceeded")
        left = self.expect(TokenKind.LEFT_DELIMITER)
        self.skip_spaces()
        self.expect(kind)
        return self.parse_branch_contents(kind, left.start, depth)

    def parse_branch_contents(
        self, kind: TokenKind, start: int, depth: int
    ) -> TemplateNode:
        self.skip_spaces()
        pipeline = self.parse_pipeline({TokenKind.RIGHT_DELIMITER})
        self.skip_spaces()
        self.expect(TokenKind.RIGHT_DELIMITER)

        if kind is TokenKind.RANGE:
            self.range_depth += 1
        body, stop = self.parse_list(
            {TokenKind.ELSE, TokenKind.END}, depth=depth + 1, top_level=False
        )
        if kind is TokenKind.RANGE:
            self.range_depth -= 1

        else_body: ListNode | None = None
        if stop is TokenKind.ELSE:
            else_body, end = self.parse_else(kind, depth)
        else:
            end = self.parse_end()

        node_type = {
            TokenKind.IF: IfNode,
            TokenKind.WITH: WithNode,
            TokenKind.RANGE: RangeNode,
        }[kind]
        return node_type(pipeline, body, else_body, start, end)

    def parse_else(self, branch_kind: TokenKind, depth: int) -> tuple[ListNode, int]:
        left = self.expect(TokenKind.LEFT_DELIMITER)
        self.skip_spaces()
        self.expect(TokenKind.ELSE)
        self.skip_spaces()
        next_kind = self.peek().kind
        matching_nested = (
            branch_kind is TokenKind.IF and next_kind is TokenKind.IF
        ) or (branch_kind is TokenKind.WITH and next_kind is TokenKind.WITH)
        if matching_nested:
            self.advance()
            nested = self.parse_branch_contents(next_kind, left.start, depth)
            return ListNode((nested,)), nested.end

        self.expect(TokenKind.RIGHT_DELIMITER)
        body, _ = self.parse_list({TokenKind.END}, depth=depth + 1, top_level=False)
        return body, self.parse_end()

    def parse_end(self) -> int:
        self.expect(TokenKind.LEFT_DELIMITER)
        self.skip_spaces()
        self.expect(TokenKind.END)
        self.skip_spaces()
        return self.expect(TokenKind.RIGHT_DELIMITER).end

    def parse_loop_control(self, *, is_break: bool) -> TemplateNode:
        left = self.expect(TokenKind.LEFT_DELIMITER)
        self.skip_spaces()
        kind = TokenKind.BREAK if is_break else TokenKind.CONTINUE
        keyword = self.expect(kind)
        if self.range_depth == 0:
            raise self.error(keyword, f"{keyword.value} outside range")
        self.skip_spaces()
        right = self.expect(TokenKind.RIGHT_DELIMITER)
        if is_break:
            return BreakNode(left.start, right.end)
        return ContinueNode(left.start, right.end)

    def parse_definition(self, depth: int) -> None:
        left = self.expect(TokenKind.LEFT_DELIMITER)
        self.skip_spaces()
        self.expect(TokenKind.DEFINE)
        self.skip_spaces()
        name = self.parse_template_name()
        self.skip_spaces()
        self.expect(TokenKind.RIGHT_DELIMITER)
        body, _ = self.parse_list({TokenKind.END}, depth=depth + 1, top_level=False)
        end = self.parse_end()
        self.add_definition(DefinitionNode(name, body, left.start, end))

    def parse_template_call(self) -> TemplateCallNode:
        left = self.expect(TokenKind.LEFT_DELIMITER)
        self.skip_spaces()
        self.expect(TokenKind.TEMPLATE)
        self.skip_spaces()
        name = self.parse_template_name()
        self.skip_spaces()
        if self.peek().kind is TokenKind.RIGHT_DELIMITER:
            pipeline = None
        else:
            pipeline = self.parse_pipeline({TokenKind.RIGHT_DELIMITER})
            self.skip_spaces()
        right = self.expect(TokenKind.RIGHT_DELIMITER)
        return TemplateCallNode(name, pipeline, left.start, right.end)

    def parse_block(self, depth: int) -> BlockNode:
        if depth >= self.limits.max_nesting:
            raise self.error(self.peek(), "template nesting limit exceeded")
        left = self.expect(TokenKind.LEFT_DELIMITER)
        self.skip_spaces()
        self.expect(TokenKind.BLOCK)
        self.skip_spaces()
        name = self.parse_template_name()
        self.skip_spaces()
        pipeline = self.parse_pipeline({TokenKind.RIGHT_DELIMITER})
        self.skip_spaces()
        self.expect(TokenKind.RIGHT_DELIMITER)
        body, _ = self.parse_list({TokenKind.END}, depth=depth + 1, top_level=False)
        end = self.parse_end()
        self.add_definition(DefinitionNode(name, body, left.start, end))
        return BlockNode(name, pipeline, body, left.start, end)

    def parse_template_name(self) -> str:
        token = self.peek()
        if token.kind not in {TokenKind.STRING, TokenKind.RAW_STRING}:
            raise self.error(token, "expected quoted template name")
        self.advance()
        return self.unquote(token)

    def add_definition(self, definition: DefinitionNode) -> None:
        for index, existing in enumerate(self.definitions):
            if existing.name == definition.name:
                if _is_empty_list(definition.body):
                    return
                if _is_empty_list(existing.body):
                    self.definitions[index] = definition
                    return
                raise self.error(
                    self.peek(), f"multiple definition of {definition.name}"
                )
        self.definitions.append(definition)

    def parse_pipeline(self, stop: set[TokenKind]) -> PipeNode:
        self.skip_spaces()
        start_token = self.peek()
        declarations, is_assignment = self.parse_declarations()
        commands: list[CommandNode] = []
        while True:
            self.skip_spaces()
            token = self.peek()
            if token.kind in stop:
                raise self.error(token, "missing value for command")
            if token.kind is TokenKind.PIPE:
                raise self.error(token, "unexpected pipe")
            commands.append(self.parse_command(stop | {TokenKind.PIPE}))
            self.skip_spaces()
            if self.peek().kind is not TokenKind.PIPE:
                break
            pipe = self.advance()
            self.skip_spaces()
            if self.peek().kind is TokenKind.PIPE:
                raise self.error(pipe, "empty command after pipe")
            if self.peek().kind in stop:
                break

        self.validate_pipeline(commands)
        return PipeNode(
            tuple(declarations),
            is_assignment,
            tuple(commands),
            start_token.start,
            commands[-1].end,
        )

    def validate_pipeline(self, commands: list[CommandNode]) -> None:
        non_executable = (
            DotNode,
            NilNode,
            BoolNode,
            NumberNode,
            ComplexNode,
            StringNode,
            CharacterNode,
        )
        for stage, command in enumerate(commands[1:], start=2):
            if isinstance(command.arguments[0], non_executable):
                raise self.error(
                    self.peek(), f"non executable command in pipeline stage {stage}"
                )

    def parse_declarations(self) -> tuple[list[VariableNode], bool]:
        checkpoint = self.index
        token = self.peek()
        if token.kind is not TokenKind.VARIABLE:
            return [], False

        declarations: list[VariableNode] = []
        while True:
            variable = self.advance()
            declarations.append(
                VariableNode(variable.value, (), variable.start, variable.end)
            )
            self.skip_spaces()
            token = self.peek()
            if token.kind is TokenKind.CHAR and token.value == ",":
                self.advance()
                self.skip_spaces()
                if self.peek().kind is not TokenKind.VARIABLE:
                    raise self.error(self.peek(), "expected variable after comma")
                continue
            if token.kind in {TokenKind.DECLARE, TokenKind.ASSIGN}:
                self.advance()
                return declarations, token.kind is TokenKind.ASSIGN
            self.index = checkpoint
            return [], False

    def parse_command(self, stop: set[TokenKind]) -> CommandNode:
        self.skip_spaces()
        start = self.peek().start
        arguments: list[TermNode] = []
        separated = True
        while self.peek().kind not in stop:
            if arguments and not separated:
                raise self.unexpected(self.peek())
            arguments.append(self.parse_term())
            separated = self.skip_spaces()
        return CommandNode(tuple(arguments), start, arguments[-1].end)

    def parse_term(self) -> TermNode:
        token = self.advance()
        if token.kind is TokenKind.DOT:
            return DotNode(token.start, token.end)
        if token.kind is TokenKind.NIL:
            return NilNode(token.start, token.end)
        if token.kind is TokenKind.BOOL:
            return BoolNode(token.value == "true", token.start, token.end)
        if token.kind is TokenKind.NUMBER:
            self.validate_number(token, is_complex=False)
            return NumberNode(token.value, token.start, token.end)
        if token.kind is TokenKind.COMPLEX:
            self.validate_number(token, is_complex=True)
            return ComplexNode(token.value, token.start, token.end)
        if token.kind in {TokenKind.STRING, TokenKind.RAW_STRING}:
            return StringNode(self.unquote(token), token.value, token.start, token.end)
        if token.kind is TokenKind.CHAR_CONSTANT:
            value = self.unquote(token)
            if len(value) != 1:
                raise self.error(token, "invalid character constant")
            return CharacterNode(value, token.value, token.start, token.end)
        if token.kind is TokenKind.IDENTIFIER:
            return IdentifierNode(token.value, token.start, token.end)
        if token.kind is TokenKind.FIELD:
            fields, end = self.collect_fields(token)
            return FieldNode(fields, token.start, end)
        if token.kind is TokenKind.VARIABLE:
            fields, end = self.collect_following_fields(token.end)
            return VariableNode(token.value, fields, token.start, end)
        if token.kind is TokenKind.LEFT_PAREN:
            if self.expression_depth >= self.limits.max_nesting:
                raise self.error(token, "template nesting limit exceeded")
            self.expression_depth += 1
            try:
                self.skip_spaces()
                pipeline = self.parse_pipeline({TokenKind.RIGHT_PAREN})
                self.skip_spaces()
                right = self.expect(TokenKind.RIGHT_PAREN)
            finally:
                self.expression_depth -= 1
            fields, end = self.collect_following_fields(right.end)
            return ParenthesizedNode(pipeline, fields, token.start, end)
        raise self.unexpected(token)

    def collect_fields(self, first: Token) -> tuple[tuple[str, ...], int]:
        fields = [first.value[1:]]
        return self.collect_following_fields(first.end, fields)

    def collect_following_fields(
        self, end: int, fields: list[str] | None = None
    ) -> tuple[tuple[str, ...], int]:
        collected = [] if fields is None else fields
        while self.peek().kind is TokenKind.FIELD:
            field = self.advance()
            collected.append(field.value[1:])
            end = field.end
        return tuple(collected), end

    def unquote(self, token: Token) -> str:
        if token.kind is TokenKind.RAW_STRING:
            return token.value[1:-1].replace("\r", "")
        return self.unquote_go(token)

    def validate_number(self, token: Token, *, is_complex: bool) -> None:
        text = token.value.replace("_", "")
        if is_complex:
            separator = _complex_separator(text)
            parts = (text[:separator], text[separator:-1])
            if not all(_finite_float(part) for part in parts):
                raise self.error(token, "invalid numeric literal")
            return
        if text.endswith("i"):
            if not _finite_float(text[:-1]):
                raise self.error(token, "invalid numeric literal")
            return
        if any(marker in text for marker in ".eEpP"):
            if not _finite_float(text):
                raise self.error(token, "invalid numeric literal")
            return
        value = _parse_integer(text)
        if value < -(1 << 63) or value > (1 << 64) - 1:
            raise self.error(token, "invalid numeric literal")

    def unquote_go(self, token: Token) -> str:
        quote = token.value[0]
        inner = token.value[1:-1]
        decoded: list[str] = []
        index = 0
        simple = {
            "a": "\a",
            "b": "\b",
            "f": "\f",
            "n": "\n",
            "r": "\r",
            "t": "\t",
            "v": "\v",
            "\\": "\\",
            quote: quote,
        }
        while index < len(inner):
            character = inner[index]
            index += 1
            if character != "\\":
                decoded.append(character)
                continue
            escape = inner[index]
            index += 1
            if escape in simple:
                decoded.append(simple[escape])
                continue
            if escape in "01234567":
                digits = escape + inner[index : index + 2]
                if len(digits) != 3 or any(item not in "01234567" for item in digits):
                    raise self.error(token, "invalid quoted literal")
                index += 2
                value = int(digits, 8)
                if value > 0xFF:
                    raise self.error(token, "invalid quoted literal")
                decoded.append(chr(value))
                continue
            widths = {"x": 2, "u": 4, "U": 8}
            width = widths.get(escape)
            if width is None:
                raise self.error(token, "invalid quoted literal")
            digits = inner[index : index + width]
            if len(digits) != width or any(
                item not in "0123456789abcdefABCDEF" for item in digits
            ):
                raise self.error(token, "invalid quoted literal")
            index += width
            value = int(digits, 16)
            if value > 0x10FFFF or 0xD800 <= value <= 0xDFFF:
                raise self.error(token, "invalid quoted literal")
            decoded.append(chr(value))
        return "".join(decoded)

    def skip_spaces(self) -> bool:
        start = self.index
        while self.peek().kind is TokenKind.SPACE:
            self.index += 1
        return self.index != start

    def peek(self) -> Token:
        return self.tokens[self.index]

    def advance(self) -> Token:
        token = self.peek()
        self.index += 1
        return token

    def expect(self, kinds: TokenKind | Iterable[TokenKind]) -> Token:
        expected = {kinds} if isinstance(kinds, TokenKind) else set(kinds)
        token = self.peek()
        if token.kind not in expected:
            raise self.unexpected(token)
        return self.advance()

    def unexpected(self, token: Token) -> TemplateSyntaxError:
        value = token.value or token.kind.name.lower()
        return self.error(token, f"unexpected {value!r}")

    def error(self, token: Token, message: str) -> TemplateSyntaxError:
        encoded = self.source.encode("utf-8")
        line_start = encoded.rfind(b"\n", 0, token.start) + 1
        return TemplateSyntaxError(
            message,
            position=token.start,
            line=token.line,
            column=token.start - line_start + 1,
        )


def _is_empty_list(root: ListNode) -> bool:
    return all(
        isinstance(node, TextNode) and node.text.isspace() for node in root.nodes
    )


def _complex_separator(text: str) -> int:
    return next(
        index
        for index in range(1, len(text))
        if text[index] in "+-" and text[index - 1] not in "eEpP"
    )


def _finite_float(text: str) -> bool:
    try:
        value = float.fromhex(text) if "0x" in text.lower() else float(text)
    except (OverflowError, ValueError):
        return False
    return math.isfinite(value)


def _parse_integer(text: str) -> int:
    sign = -1 if text.startswith("-") else 1
    unsigned = text.lstrip("+-")
    if unsigned.lower().startswith(("0b", "0o", "0x")):
        value = int(unsigned, 0)
    elif len(unsigned) > 1 and unsigned.startswith("0"):
        value = int(unsigned, 8)
    else:
        value = int(unsigned, 10)
    return sign * value
