import pytest

from gotpl.errors import TemplateSyntaxError
from gotpl.parse import parse, parse_template


@pytest.mark.parametrize(
    "source",
    [
        "{{$missing}}",
        "{{$missing = .}}",
        "{{if .}}{{$local := .}}{{end}}{{$local}}",
        '{{define "item"}}{{$outer}}{{end}}{{$outer := .}}',
    ],
)
def test_semantic_analysis_rejects_undefined_variables(source: str) -> None:
    with pytest.raises(TemplateSyntaxError, match="undefined variable"):
        parse_template(source)


def test_semantic_analysis_tracks_sequential_and_branch_scopes() -> None:
    parse("{{$value := .}}{{$value}}")
    parse("{{if $value := .}}{{$value}}{{else}}{{$value}}{{end}}")
    parse("{{range $key, $value := .}}{{$key}}{{$value}}{{end}}")
    parse("{{if .}}{{$branch := .}}{{else}}{{$branch}}{{end}}")


@pytest.mark.parametrize(
    "source",
    [
        "{{$a, $b := .}}",
        "{{if $a, $b := .}}{{end}}",
        "{{with $a, $b := .}}{{end}}",
        "{{range $a, $b, $c := .}}{{end}}",
    ],
)
def test_semantic_analysis_enforces_declaration_counts(source: str) -> None:
    with pytest.raises(TemplateSyntaxError, match="too many declarations"):
        parse(source)


@pytest.mark.parametrize(
    "source",
    [
        '{{template "item" $value := .}}',
        "{{printf ($value := .)}}",
    ],
)
def test_semantic_analysis_rejects_declarations_in_value_pipelines(
    source: str,
) -> None:
    with pytest.raises(TemplateSyntaxError, match="declaration"):
        parse(source)


def test_root_variable_is_always_defined() -> None:
    parse("{{$}}")


def test_semantic_analysis_accepts_builtins_and_registered_functions() -> None:
    parse('{{printf "%s" .}}')
    parse("{{custom .}}", functions={"custom"})


def test_semantic_analysis_rejects_an_unknown_function() -> None:
    with pytest.raises(TemplateSyntaxError, match=r"function.*not defined"):
        parse("{{unknown .}}")


@pytest.mark.parametrize("name", ["break", "continue"])
def test_registered_functions_override_loop_control_keywords(name: str) -> None:
    parse(f"{{{{range .}}}}{{{{{name} 20}}}}{{{{end}}}}", functions={name})
