from io import StringIO
from typing import cast

import pytest

import gotpl


def shout(value: object) -> str:
    return str(value).upper()


def surround(value: object) -> str:
    return f"<{value}>"


def test_render_returns_literal_text() -> None:
    assert gotpl.render("Hello, Gopher!", None) == "Hello, Gopher!"


def test_root_variable_assignment_works_without_materialized_scopes() -> None:
    assert gotpl.render('{{$ = "changed"}}{{$}}', "root") == "changed"


def test_compiled_template_is_reusable() -> None:
    template = gotpl.Template("stable")
    assert template.render({"first": True}) == "stable"
    assert template.render({"second": True}) == "stable"


def test_template_can_render_an_associated_named_template() -> None:
    template = gotpl.Template(
        'root{{define "leaf"}}{{.}}{{end}}'
        '{{define "middle"}}[{{template "leaf" .}}]{{end}}',
        name="root",
    )

    assert template.render_template("middle", "value") == "[value]"
    destination = StringIO()
    result = template.render_template_to("leaf", destination, "written")

    assert result is None
    assert destination.getvalue() == "written"


def test_template_from_sources_builds_one_immutable_association_namespace() -> None:
    template = gotpl.Template.from_sources(
        {
            "helpers.tpl": '{{define "label"}}first={{.}}{{end}}',
            "manifest.yaml": '{{template "label" .}}',
        }
    )

    assert template.render_template("manifest.yaml", "value") == "first=value"
    assert template.render_template("label", "other") == "first=other"


def test_template_from_sources_uses_later_nonempty_definitions() -> None:
    template = gotpl.Template.from_sources(
        {
            "child.tpl": '{{define "label"}}child{{end}}',
            "parent.tpl": '{{define "label"}}parent{{end}}{{template "label"}}',
        }
    )

    assert template.render_template("parent.tpl") == "parent"


def test_template_from_sources_requires_at_least_one_source() -> None:
    with pytest.raises(ValueError, match="at least one source"):
        gotpl.Template.from_sources({})


def test_render_source_inherits_associated_templates_without_mutating_parent() -> None:
    template = gotpl.Template.from_sources(
        {
            "base.tpl": '{{define "label"}}base:{{.}}{{end}}',
            "main.tpl": '{{template "label" .}}',
        }
    )

    assert (
        template.render_source(
            '{{define "label"}}dynamic:{{.}}{{end}}{{template "label" .}}',
            "value",
            name="dynamic.tpl",
        )
        == "dynamic:value"
    )
    assert template.render_template("main.tpl", "value") == "base:value"


def test_with_source_returns_a_reusable_immutable_template_association() -> None:
    parent = gotpl.Template.from_sources(
        {"helpers.tpl": '{{define "label"}}label:{{.}}{{end}}'}
    )

    derived = parent.with_source('{{template "label" .}}', name="main.tpl")

    assert derived.render("one") == "label:one"
    assert derived.render_template("main.tpl", "two") == "label:two"
    with pytest.raises(gotpl.TemplateExecutionError, match="not defined"):
        parent.render_template("main.tpl", "three")


def test_template_rejects_an_unknown_named_template() -> None:
    template = gotpl.Template("root", name="root")

    with pytest.raises(gotpl.TemplateExecutionError, match="not defined"):
        template.render_template("absent")


def test_render_writes_the_current_string_value() -> None:
    assert gotpl.render("Hello, {{.}}!", "Gopher") == "Hello, Gopher!"


def test_render_omits_comments() -> None:
    assert gotpl.render("left{{/* note */}}right") == "leftright"


def test_render_applies_whitespace_trim_markers() -> None:
    assert gotpl.render("left \n{{- . -}} \nright", "center") == "leftcenterright"


def test_render_supports_custom_delimiters() -> None:
    assert (
        gotpl.render("Hello, [[.]\u307a", "Gopher", delimiters=("[[", "]\u307a"))
        == "Hello, Gopher"
    )


def test_template_accepts_reusable_caller_functions() -> None:
    template = gotpl.Template("{{shout .}}", functions={"shout": shout})
    assert template.render("hello") == "HELLO"
    assert template.render("world") == "WORLD"


def test_render_accepts_caller_functions() -> None:
    assert (
        gotpl.render(
            "{{surround .}}",
            "value",
            functions={"surround": surround},
        )
        == "<value>"
    )


def test_missing_key_modes_are_explicit() -> None:
    assert gotpl.render("{{.missing}}", {}) == "<no value>"
    assert gotpl.render("{{.missing}}", {}, missing_key="zero") == "<no value>"
    with pytest.raises(gotpl.TemplateExecutionError, match="missing"):
        gotpl.render("{{.missing}}", {}, missing_key="error")


def test_template_rejects_an_unknown_missing_key_mode() -> None:
    with pytest.raises(ValueError, match="missing_key"):
        gotpl.Template("stable", missing_key="unknown")  # type: ignore[arg-type]


def test_template_can_render_to_a_text_writer() -> None:
    destination = StringIO()
    template = gotpl.Template("Hello, {{.}}!")

    result = template.render_to(destination, "writer")

    assert result is None
    assert destination.getvalue() == "Hello, writer!"


def test_render_to_accepts_the_same_options_as_render() -> None:
    destination = StringIO()

    gotpl.render_to(
        "[[shout .]]",
        destination,
        "hello",
        delimiters=("[[", "]]"),
        functions={"shout": shout},
        missing_key="error",
    )

    assert destination.getvalue() == "HELLO"


@pytest.mark.parametrize("name", ["", "1bad", "has-dash", "combining\u0301"])
def test_template_rejects_invalid_function_names(name: str) -> None:
    with pytest.raises(ValueError, match="function name"):
        gotpl.Template("stable", functions={name: shout})


@pytest.mark.parametrize("name", ["_", "valid2", "\u00c9clair"])
def test_template_accepts_go_style_function_names(name: str) -> None:
    assert gotpl.Template("stable", functions={name: shout}).render() == "stable"


def test_template_rejects_non_callable_function_values() -> None:
    functions = cast(dict[str, object], {"invalid": 1})
    with pytest.raises(TypeError, match="callable"):
        gotpl.Template("stable", functions=functions)  # type: ignore[arg-type]


@pytest.mark.parametrize("delimiters", [("", "}}"), ("{{", "")])
def test_template_rejects_empty_delimiters(delimiters: tuple[str, str]) -> None:
    with pytest.raises(ValueError, match="delimiter"):
        gotpl.Template("stable", delimiters=delimiters)


def test_writer_errors_propagate_after_partial_output() -> None:
    class FailingWriter(StringIO):
        def write(self, text: str) -> int:
            if text == "value":
                raise OSError("destination failed")
            return super().write(text)

    destination = FailingWriter()
    template = gotpl.Template("before/{{.}}/after")

    with pytest.raises(OSError, match="destination failed"):
        template.render_to(destination, "value")

    assert destination.getvalue() == "before/"


def test_writer_short_writes_are_rejected() -> None:
    class ShortWriter(StringIO):
        def write(self, text: str) -> int:
            super().write(text[:1])
            return min(1, len(text))

    destination = ShortWriter()

    with pytest.raises(OSError, match="short write"):
        gotpl.render_to("literal", destination)

    assert destination.getvalue() == "l"
