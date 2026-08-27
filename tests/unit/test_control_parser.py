import pytest

from gotpl.errors import TemplateSyntaxError
from gotpl.parse import (
    BlockNode,
    BreakNode,
    ContinueNode,
    IfNode,
    ParserLimits,
    RangeNode,
    TemplateCallNode,
    TextNode,
    WithNode,
    parse,
    parse_template,
)


def test_parser_builds_if_else_and_nested_with() -> None:
    root = parse("{{if .Ready}}yes{{else}}{{with .Fallback}}maybe{{end}}{{end}}")
    branch = root.nodes[0]
    assert isinstance(branch, IfNode)
    assert branch.body.nodes == (TextNode("yes", 13, 16),)
    assert branch.else_body is not None
    nested = branch.else_body.nodes[0]
    assert isinstance(nested, WithNode)
    nested_text = nested.body.nodes[0]
    assert isinstance(nested_text, TextNode)
    assert nested_text.text == "maybe"


def test_parser_builds_else_if_as_nested_branch() -> None:
    root = parse("{{if .A}}a{{else if .B}}b{{else}}c{{end}}")
    first = root.nodes[0]
    assert isinstance(first, IfNode)
    assert first.else_body is not None
    second = first.else_body.nodes[0]
    assert isinstance(second, IfNode)
    assert second.else_body is not None


def test_parser_builds_range_break_continue_and_else() -> None:
    root = parse(
        "{{range .Items}}{{if .Stop}}{{break}}{{end}}{{continue}}{{else}}empty{{end}}"
    )
    loop = root.nodes[0]
    assert isinstance(loop, RangeNode)
    nested = loop.body.nodes[0]
    assert isinstance(nested, IfNode)
    assert isinstance(nested.body.nodes[0], BreakNode)
    assert isinstance(loop.body.nodes[1], ContinueNode)
    assert loop.else_body is not None
    empty = loop.else_body.nodes[0]
    assert isinstance(empty, TextNode)
    assert empty.text == "empty"


def test_parser_collects_definitions_template_calls_and_blocks() -> None:
    parsed = parse_template(
        '{{define "item"}}item{{end}}{{template "item" .}}'
        '{{block "footer" .}}foot{{end}}',
        name="root",
    )
    assert parsed.name == "root"
    assert [definition.name for definition in parsed.definitions] == ["item", "footer"]
    assert isinstance(parsed.root.nodes[0], TemplateCallNode)
    assert isinstance(parsed.root.nodes[1], BlockNode)


@pytest.mark.parametrize("source", ["{{break}}", "{{continue}}"])
def test_parser_rejects_loop_control_outside_range(source: str) -> None:
    with pytest.raises(TemplateSyntaxError, match="outside range"):
        parse(source)


@pytest.mark.parametrize(
    "source",
    [
        "{{if .}}missing end",
        "{{else}}",
        "{{end}}",
        '{{define "x"}}unterminated',
        "{{template 42}}",
        '{{block "x"}}body{{end}}',
    ],
)
def test_parser_rejects_malformed_control_actions(source: str) -> None:
    with pytest.raises(TemplateSyntaxError):
        parse_template(source)


def test_parser_enforces_source_size_token_and_nesting_limits() -> None:
    with pytest.raises(TemplateSyntaxError, match="source size limit"):
        parse("text", limits=ParserLimits(max_source_bytes=3))
    with pytest.raises(TemplateSyntaxError, match="token limit"):
        parse("a{{.}}", limits=ParserLimits(max_tokens=2))
    with pytest.raises(TemplateSyntaxError, match="nesting limit"):
        parse("{{if .}}{{if .}}{{end}}{{end}}", limits=ParserLimits(max_nesting=1))
    with pytest.raises(TemplateSyntaxError, match="nesting limit"):
        parse("{{((.))}}", limits=ParserLimits(max_nesting=1))
    with pytest.raises(TemplateSyntaxError, match="nesting limit"):
        parse_template(
            '{{if .}}{{block "x" .}}x{{end}}{{end}}',
            limits=ParserLimits(max_nesting=1),
        )


def test_parser_limits_must_be_positive() -> None:
    with pytest.raises(ValueError, match="must be positive"):
        ParserLimits(max_tokens=0)


def test_parser_rejects_definitions_in_control_bodies() -> None:
    with pytest.raises(TemplateSyntaxError, match="control body"):
        parse_template('{{if .}}{{define "x"}}x{{end}}{{end}}')


def test_parser_accepts_blocks_in_control_bodies() -> None:
    parsed = parse_template('{{if .}}{{block "x" .}}x{{end}}{{end}}')
    assert [definition.name for definition in parsed.definitions] == ["x"]


def test_parser_rejects_duplicate_definitions() -> None:
    with pytest.raises(TemplateSyntaxError, match="multiple definition"):
        parse_template('{{define "x"}}a{{end}}{{define "x"}}b{{end}}')


def test_parser_replaces_or_ignores_empty_duplicate_definitions() -> None:
    replaced = parse_template(
        '{{define "x"}}{{end}}{{define "x"}}body{{end}}'
    ).definitions
    ignored = parse_template(
        '{{define "x"}}body{{end}}{{define "x"}} \n {{end}}'
    ).definitions
    assert len(replaced) == len(ignored) == 1
    for definition in (*replaced, *ignored):
        body = definition.body.nodes[0]
        assert isinstance(body, TextNode)
        assert body.text == "body"


def test_parser_supports_template_calls_without_a_pipeline() -> None:
    call = parse('{{template "item"}}').nodes[0]
    assert isinstance(call, TemplateCallNode)
    assert call.pipeline is None
