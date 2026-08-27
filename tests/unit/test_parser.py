import pytest

from gotpl.errors import TemplateSyntaxError
from gotpl.parse import (
    ActionNode,
    BoolNode,
    CharacterNode,
    ComplexNode,
    FieldNode,
    IdentifierNode,
    NilNode,
    NumberNode,
    ParenthesizedNode,
    RangeNode,
    StringNode,
    VariableNode,
    parse,
)


def only_action(source: str) -> ActionNode:
    root = parse(source)
    assert len(root.nodes) == 1
    action = root.nodes[0]
    assert isinstance(action, ActionNode)
    return action


def test_parser_builds_declaration_and_pipeline_commands() -> None:
    action = only_action('{{$result := .User.Name | printf "%s"}}')
    pipeline = action.pipeline
    assert pipeline.is_assignment is False
    assert pipeline.declarations == (VariableNode("$result", (), 2, 9),)
    assert len(pipeline.commands) == 2
    assert pipeline.commands[0].arguments == (FieldNode(("User", "Name"), 13, 23),)
    assert pipeline.commands[1].arguments == (
        IdentifierNode("printf", 26, 32),
        StringNode("%s", '"%s"', 33, 37),
    )


def test_parser_builds_range_assignment_with_multiple_variables() -> None:
    root = parse("{{$key := .}}{{$value := .}}{{range $key, $value = .}}{{end}}")
    loop = root.nodes[2]
    assert isinstance(loop, RangeNode)
    assert loop.pipeline.is_assignment is True
    assert [node.name for node in loop.pipeline.declarations] == ["$key", "$value"]


def test_parser_builds_literal_arguments() -> None:
    action = only_action("{{call true false nil 42 -7.2i 1+2i \"text\" `raw` 'x'}}")
    arguments = action.pipeline.commands[0].arguments
    assert isinstance(arguments[0], IdentifierNode)
    assert arguments[1:4] == (
        BoolNode(True, 7, 11),
        BoolNode(False, 12, 17),
        NilNode(18, 21),
    )
    assert isinstance(arguments[4], NumberNode)
    assert isinstance(arguments[5], NumberNode)
    assert isinstance(arguments[6], ComplexNode)
    assert arguments[7] == StringNode("text", '"text"', 36, 42)
    assert arguments[8] == StringNode("raw", "`raw`", 43, 48)
    assert arguments[9] == CharacterNode("x", "'x'", 49, 52)


def test_parser_builds_variable_fields_and_parenthesized_pipeline() -> None:
    root = parse(
        "{{$user := .}}{{printf $user.Name (.User | render).Value}}",
        functions={"render"},
    )
    action = root.nodes[1]
    assert isinstance(action, ActionNode)
    arguments = action.pipeline.commands[0].arguments
    assert arguments[1] == VariableNode("$user", ("Name",), 23, 33)
    grouped = arguments[2]
    assert isinstance(grouped, ParenthesizedNode)
    assert grouped.fields == ("Value",)
    assert len(grouped.pipeline.commands) == 2


@pytest.mark.parametrize(
    "source",
    [
        "{{| printf}}",
        "{{$x :=}}",
        "{{printf || upper}}",
        "{{()}}",
    ],
)
def test_parser_rejects_malformed_pipelines(source: str) -> None:
    with pytest.raises(TemplateSyntaxError):
        parse(source)


@pytest.mark.parametrize(
    "source",
    [
        "{{. | 1}}",
        "{{$item, := .}}",
        "{{printf break}}",
        "{{if .}}{{end trailing}}",
        '{{"\\q"}}',
        "{{'ab'}}",
    ],
)
def test_parser_rejects_additional_invalid_command_forms(source: str) -> None:
    with pytest.raises(TemplateSyntaxError):
        parse(source)


def test_parser_distinguishes_a_variable_value_from_a_declaration() -> None:
    root = parse("{{$value := .}}{{$value}}")
    action = root.nodes[1]
    assert isinstance(action, ActionNode)
    assert action.pipeline.declarations == ()
    assert action.pipeline.commands[0].arguments == (
        VariableNode("$value", (), 17, 23),
    )


def test_parser_accepts_a_pipeline_that_ends_after_a_second_command() -> None:
    action = only_action("{{. | printf}}")
    assert len(action.pipeline.commands) == 2


def test_parser_accepts_a_trailing_pipeline_separator() -> None:
    action = only_action("{{printf |}}")
    assert len(action.pipeline.commands) == 1


def test_parser_decodes_go_string_escape_forms() -> None:
    action = only_action(r"""{{"\a\b\f\n\r\t\v\\\"\141\x62\u754c\U0001F600"}}""")
    value = action.pipeline.commands[0].arguments[0]
    assert isinstance(value, StringNode)
    assert value.value == '\a\b\f\n\r\t\v\\"ab\u754c\U0001f600'


@pytest.mark.parametrize(
    "source",
    [
        r"""{{"\1"}}""",
        r"""{{"\x1"}}""",
        r"""{{"\uD800"}}""",
        r"""{{"\U00110000"}}""",
        r"""{{"\'"}}""",
    ],
)
def test_parser_rejects_invalid_go_string_escapes(source: str) -> None:
    with pytest.raises(TemplateSyntaxError, match="invalid quoted literal"):
        parse(source)
