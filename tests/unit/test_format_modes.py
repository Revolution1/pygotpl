from io import StringIO

import pytest

import gotpl

DATA = {
    "List": [1, True, None],
    "Map": {"a": 1},
}


def test_go_formatting_remains_the_default() -> None:
    template = gotpl.Template('{{.List}}|{{printf "%T|%v|%#v" .List .List .Map}}')

    assert template.render(DATA) == (
        '[1 true <nil>]|[]interface {}|[1 true <nil>]|map[string]interface {}{"a":1}'
    )


def test_python_formatting_is_an_explicit_template_option() -> None:
    template = gotpl.Template(
        '{{.List}}|{{printf "%T|%v|%#v" .List .List .Map}}',
        format_mode="python",
    )

    assert template.render(DATA) == ("[1, True, None]|list|[1, True, None]|{'a': 1}")


def test_python_formatting_flows_through_named_template_calls() -> None:
    template = gotpl.Template(
        '{{define "item"}}{{.}}/{{printf "%T" .}}{{end}}{{template "item" .}}',
        format_mode="python",
    )

    assert template.render([1, True]) == "[1, True]/list"


def test_render_and_render_to_accept_python_formatting() -> None:
    assert gotpl.render("{{.}}", {"a": True}, format_mode="python") == ("{'a': True}")
    destination = StringIO()
    gotpl.render_to("{{.}}", destination, None, format_mode="python")
    assert destination.getvalue() == "None"


def test_python_formatting_is_shared_by_print_and_escaping_builtins() -> None:
    template = gotpl.Template(
        "{{print .}}|{{println .}}end|{{html .}}|{{urlquery .}}|{{js .}}",
        format_mode="python",
    )
    assert template.render(True) == "True|True\nend|True|True|True"


def test_template_rejects_an_unknown_format_mode() -> None:
    with pytest.raises(ValueError, match="format_mode"):
        gotpl.Template("stable", format_mode="native")  # type: ignore[arg-type]
