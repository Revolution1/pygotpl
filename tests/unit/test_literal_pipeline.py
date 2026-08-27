from dataclasses import FrozenInstanceError

import pytest

from gotpl.compile import Instruction, OpCode, Program, compile_template
from gotpl.errors import TemplateSyntaxError
from gotpl.parse import (
    ActionNode,
    CommandNode,
    DotNode,
    ListNode,
    PipeNode,
    TextNode,
    Token,
    TokenKind,
    lex,
    parse,
)
from gotpl.runtime import render_program


def test_lexer_emits_literal_text_and_eof() -> None:
    assert list(lex("hello")) == [
        Token(TokenKind.TEXT, "hello", 0, 5),
        Token(TokenKind.EOF, "", 5, 5),
    ]


def test_lexer_emits_only_eof_for_empty_source() -> None:
    assert list(lex("")) == [Token(TokenKind.EOF, "", 0, 0)]


def test_lexer_rejects_lone_surrogates_with_a_controlled_error() -> None:
    with pytest.raises(TemplateSyntaxError, match="invalid Unicode"):
        list(lex("valid\ud800tail"))


def test_invalid_action_retains_preceding_text_and_reports_position() -> None:
    tokens = lex("hello {{\x01}}")
    assert next(tokens) == Token(TokenKind.TEXT, "hello ", 0, 6)
    assert next(tokens) == Token(TokenKind.LEFT_DELIMITER, "{{", 6, 8)
    with pytest.raises(TemplateSyntaxError, match="template:1:9") as error:
        next(tokens)
    assert error.value.position == 8


def test_lexer_emits_a_dot_action_with_spaces() -> None:
    assert list(lex("{{  . }}")) == [
        Token(TokenKind.LEFT_DELIMITER, "{{", 0, 2),
        Token(TokenKind.SPACE, "  ", 2, 4),
        Token(TokenKind.DOT, ".", 4, 5),
        Token(TokenKind.SPACE, " ", 5, 6),
        Token(TokenKind.RIGHT_DELIMITER, "}}", 6, 8),
        Token(TokenKind.EOF, "", 8, 8),
    ]


def test_lexer_rejects_an_unclosed_action() -> None:
    tokens = lex("{{.")
    assert next(tokens).kind is TokenKind.LEFT_DELIMITER
    assert next(tokens).kind is TokenKind.DOT
    with pytest.raises(TemplateSyntaxError, match="unclosed action"):
        next(tokens)


def test_lexer_can_emit_or_skip_a_comment() -> None:
    source = "a{{/* note */}}b"
    assert [token.kind for token in lex(source)] == [
        TokenKind.TEXT,
        TokenKind.TEXT,
        TokenKind.EOF,
    ]
    assert [token.kind for token in lex(source, emit_comments=True)] == [
        TokenKind.TEXT,
        TokenKind.COMMENT,
        TokenKind.TEXT,
        TokenKind.EOF,
    ]


def test_lexer_trims_whitespace_around_a_comment() -> None:
    tokens = list(lex("a \n{{- /* note */ -}} \nb", emit_comments=True))
    assert [(token.kind, token.value) for token in tokens] == [
        (TokenKind.TEXT, "a"),
        (TokenKind.COMMENT, "/* note */"),
        (TokenKind.TEXT, "b"),
        (TokenKind.EOF, ""),
    ]


@pytest.mark.parametrize(
    ("source", "message"),
    [
        ("{{/* open", "unclosed comment"),
        ("{{/* closed */ }}", "comment ends before closing delimiter"),
    ],
)
def test_lexer_rejects_malformed_comments(source: str, message: str) -> None:
    with pytest.raises(TemplateSyntaxError, match=message):
        list(lex(source))


@pytest.mark.parametrize("delimiters", [("", "}}"), ("{{", "")])
def test_lexer_rejects_empty_delimiters(delimiters: tuple[str, str]) -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        list(
            lex(
                "source",
                left_delimiter=delimiters[0],
                right_delimiter=delimiters[1],
            )
        )


def test_lexer_supports_custom_unicode_delimiters() -> None:
    tokens = list(lex("a[[.]\u307ab", left_delimiter="[[", right_delimiter="]\u307a"))
    assert [token.kind for token in tokens] == [
        TokenKind.TEXT,
        TokenKind.LEFT_DELIMITER,
        TokenKind.DOT,
        TokenKind.RIGHT_DELIMITER,
        TokenKind.TEXT,
        TokenKind.EOF,
    ]


def test_lexer_applies_ascii_whitespace_trim_markers() -> None:
    tokens = list(lex("left \n{{- . -}} \nright"))
    assert [(token.kind, token.value) for token in tokens] == [
        (TokenKind.TEXT, "left"),
        (TokenKind.LEFT_DELIMITER, "{{"),
        (TokenKind.DOT, "."),
        (TokenKind.RIGHT_DELIMITER, "}}"),
        (TokenKind.TEXT, "right"),
        (TokenKind.EOF, ""),
    ]


def test_left_trim_can_remove_the_entire_preceding_text_node() -> None:
    assert [token.kind for token in lex(" \n{{- .}}")][:2] == [
        TokenKind.LEFT_DELIMITER,
        TokenKind.DOT,
    ]


def test_lexer_emits_pipeline_names_fields_variables_and_keywords() -> None:
    tokens = list(lex("{{range $item := .Items.Name | render}}"))
    assert [(token.kind, token.value) for token in tokens] == [
        (TokenKind.LEFT_DELIMITER, "{{"),
        (TokenKind.RANGE, "range"),
        (TokenKind.SPACE, " "),
        (TokenKind.VARIABLE, "$item"),
        (TokenKind.SPACE, " "),
        (TokenKind.DECLARE, ":="),
        (TokenKind.SPACE, " "),
        (TokenKind.FIELD, ".Items"),
        (TokenKind.FIELD, ".Name"),
        (TokenKind.SPACE, " "),
        (TokenKind.PIPE, "|"),
        (TokenKind.SPACE, " "),
        (TokenKind.IDENTIFIER, "render"),
        (TokenKind.RIGHT_DELIMITER, "}}"),
        (TokenKind.EOF, ""),
    ]


def test_lexer_emits_parentheses_assignments_and_scalar_keywords() -> None:
    tokens = list(lex("{{($ = true) false nil break continue}}"))
    assert [(token.kind, token.value) for token in tokens] == [
        (TokenKind.LEFT_DELIMITER, "{{"),
        (TokenKind.LEFT_PAREN, "("),
        (TokenKind.VARIABLE, "$"),
        (TokenKind.SPACE, " "),
        (TokenKind.ASSIGN, "="),
        (TokenKind.SPACE, " "),
        (TokenKind.BOOL, "true"),
        (TokenKind.RIGHT_PAREN, ")"),
        (TokenKind.SPACE, " "),
        (TokenKind.BOOL, "false"),
        (TokenKind.SPACE, " "),
        (TokenKind.NIL, "nil"),
        (TokenKind.SPACE, " "),
        (TokenKind.BREAK, "break"),
        (TokenKind.SPACE, " "),
        (TokenKind.CONTINUE, "continue"),
        (TokenKind.RIGHT_DELIMITER, "}}"),
        (TokenKind.EOF, ""),
    ]


def test_lexer_emits_every_control_keyword_and_punctuation_token() -> None:
    tokens = list(
        lex("{{block break continue define else end if range template with ,@%}}")
    )
    assert [token.kind for token in tokens] == [
        TokenKind.LEFT_DELIMITER,
        TokenKind.BLOCK,
        TokenKind.SPACE,
        TokenKind.BREAK,
        TokenKind.SPACE,
        TokenKind.CONTINUE,
        TokenKind.SPACE,
        TokenKind.DEFINE,
        TokenKind.SPACE,
        TokenKind.ELSE,
        TokenKind.SPACE,
        TokenKind.END,
        TokenKind.SPACE,
        TokenKind.IF,
        TokenKind.SPACE,
        TokenKind.RANGE,
        TokenKind.SPACE,
        TokenKind.TEMPLATE,
        TokenKind.SPACE,
        TokenKind.WITH,
        TokenKind.SPACE,
        TokenKind.CHAR,
        TokenKind.CHAR,
        TokenKind.CHAR,
        TokenKind.RIGHT_DELIMITER,
        TokenKind.EOF,
    ]


@pytest.mark.parametrize(
    ("source", "message"),
    [
        ("{{( .}}", "unclosed left paren"),
        ("{{.)}}", "unexpected right paren"),
        ("{{\x01}}", "unrecognized character"),
    ],
)
def test_lexer_rejects_invalid_action_structure(source: str, message: str) -> None:
    with pytest.raises(TemplateSyntaxError, match=message):
        list(lex(source))


def test_lexer_emits_string_character_and_raw_string_literals() -> None:
    source = '{{"line\\n\\"" \'\u754c\' `raw\\ntext`}}'
    tokens = list(lex(source))
    assert [(token.kind, token.value) for token in tokens] == [
        (TokenKind.LEFT_DELIMITER, "{{"),
        (TokenKind.STRING, '"line\\n\\""'),
        (TokenKind.SPACE, " "),
        (TokenKind.CHAR_CONSTANT, "'\u754c'"),
        (TokenKind.SPACE, " "),
        (TokenKind.RAW_STRING, "`raw\\ntext`"),
        (TokenKind.RIGHT_DELIMITER, "}}"),
        (TokenKind.EOF, ""),
    ]


@pytest.mark.parametrize(
    ("source", "message"),
    [
        ('{{"open}}', "unterminated quoted string"),
        ('{{"line\nbreak"}}', "unterminated quoted string"),
        ("{{`open}}", "unterminated raw quoted string"),
        ("{{'open}}", "unterminated character constant"),
    ],
)
def test_lexer_rejects_unterminated_quoted_literals(source: str, message: str) -> None:
    with pytest.raises(TemplateSyntaxError, match=message):
        list(lex(source))


def test_lexer_emits_go_numeric_forms() -> None:
    source = "{{1 02 0x14 -7.2i 1e3 +1.2e-4 .5 1+2i 1_2 0x1.e_fp4}}"
    tokens = [token for token in lex(source) if token.kind is not TokenKind.SPACE]
    assert [(token.kind, token.value) for token in tokens] == [
        (TokenKind.LEFT_DELIMITER, "{{"),
        (TokenKind.NUMBER, "1"),
        (TokenKind.NUMBER, "02"),
        (TokenKind.NUMBER, "0x14"),
        (TokenKind.NUMBER, "-7.2i"),
        (TokenKind.NUMBER, "1e3"),
        (TokenKind.NUMBER, "+1.2e-4"),
        (TokenKind.NUMBER, ".5"),
        (TokenKind.COMPLEX, "1+2i"),
        (TokenKind.NUMBER, "1_2"),
        (TokenKind.NUMBER, "0x1.e_fp4"),
        (TokenKind.RIGHT_DELIMITER, "}}"),
        (TokenKind.EOF, ""),
    ]


def test_lexer_rejects_bad_number_syntax() -> None:
    with pytest.raises(TemplateSyntaxError, match="bad number syntax"):
        list(lex("{{3k}}"))


def test_right_delimiter_inside_raw_string_does_not_close_action() -> None:
    tokens = list(lex("{{`inside }} raw`}}"))
    assert [(token.kind, token.value) for token in tokens] == [
        (TokenKind.LEFT_DELIMITER, "{{"),
        (TokenKind.RAW_STRING, "`inside }} raw`"),
        (TokenKind.RIGHT_DELIMITER, "}}"),
        (TokenKind.EOF, ""),
    ]


def test_tokens_use_utf8_byte_offsets_and_track_lines() -> None:
    tokens = list(lex("\u00e9\n{{.}}"))
    assert tokens[0] == Token(TokenKind.TEXT, "\u00e9\n", 0, 3, line=1)
    assert tokens[1] == Token(TokenKind.LEFT_DELIMITER, "{{", 3, 5, line=2)
    assert tokens[2] == Token(TokenKind.DOT, ".", 5, 6, line=2)
    assert tokens[3] == Token(TokenKind.RIGHT_DELIMITER, "}}", 6, 8, line=2)
    assert tokens[4] == Token(TokenKind.EOF, "", 8, 8, line=2)


def test_parser_builds_an_immutable_literal_tree() -> None:
    root = parse("hello")
    assert root == ListNode((TextNode("hello", 0, 5),))
    with pytest.raises(FrozenInstanceError):
        root.__setattr__("nodes", ())


def test_parser_builds_an_empty_list_for_empty_source() -> None:
    assert parse("") == ListNode(())


def test_parser_builds_a_dot_action_between_text_nodes() -> None:
    pipeline = PipeNode((), False, (CommandNode((DotNode(3, 4),), 3, 4),), 3, 4)
    assert parse("a{{.}}b") == ListNode(
        (
            TextNode("a", 0, 1),
            ActionNode(pipeline, 1, 6),
            TextNode("b", 6, 7),
        )
    )


def test_parser_ignores_spaces_around_dot() -> None:
    pipeline = PipeNode((), False, (CommandNode((DotNode(3, 4),), 3, 4),), 3, 4)
    assert parse("{{ . }}") == ListNode((ActionNode(pipeline, 0, 7),))


@pytest.mark.parametrize("source", ["{{}}", "{{  }}", "{{..}}"])
def test_parser_rejects_invalid_dot_actions(source: str) -> None:
    with pytest.raises(TemplateSyntaxError):
        parse(source)


def test_compiler_emits_source_mapped_write_instruction() -> None:
    root = ListNode((TextNode("hello", 3, 8),))
    assert compile_template(root) == Program(
        (Instruction(OpCode.WRITE_TEXT, "hello", 3),)
    )


def test_compiler_emits_a_dot_write_instruction() -> None:
    pipeline = PipeNode((), False, (CommandNode((DotNode(2, 3),), 2, 3),), 2, 3)
    root = ListNode((ActionNode(pipeline, 0, 5),))
    assert compile_template(root) == Program((Instruction(OpCode.WRITE_DOT, None, 0),))


def test_sync_vm_renders_literal_program_and_ignores_data() -> None:
    program = Program((Instruction(OpCode.WRITE_TEXT, "hello", 0),))
    assert render_program(program, {"unused": True}) == "hello"


def test_sync_vm_renders_empty_program() -> None:
    assert render_program(Program(())) == ""


def test_sync_vm_ignores_an_invalid_text_argument() -> None:
    program = Program((Instruction(OpCode.WRITE_TEXT, None, 0),))
    assert render_program(program) == ""


@pytest.mark.parametrize(
    ("value", "expected"),
    [("Gopher", "Gopher"), (None, "<no value>"), (True, "true"), (False, "false")],
)
def test_sync_vm_formats_basic_dot_values(value: object, expected: str) -> None:
    program = Program((Instruction(OpCode.WRITE_DOT, None, 0),))
    assert render_program(program, value) == expected
