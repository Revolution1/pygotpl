from io import StringIO

import pytest

import gotpl


def test_execution_error_exposes_utf8_position_line_column_and_names() -> None:
    source = "first\n\u00e9 {{.missing}}"
    output = StringIO()
    template = gotpl.Template(source, name="location", missing_key="error")

    with pytest.raises(gotpl.TemplateExecutionError) as caught:
        template.render_to(output, {})

    error = caught.value
    assert output.getvalue() == "first\n\u00e9 "
    assert error.position == len("first\n\u00e9 {{".encode())
    assert (error.line, error.column) == (2, 5)
    assert error.source_name == "location"
    assert error.template_name == "location"
    assert str(error).startswith(
        'template: location:2:5: executing "location": missing key'
    )


def test_nested_template_error_keeps_the_callee_location() -> None:
    failure = RuntimeError("inner failed")

    def fail() -> None:
        raise failure

    source = '{{define "inner"}}line1\n{{fail}}{{end}}{{template "inner"}}'
    template = gotpl.Template(source, name="outer", functions={"fail": fail})

    with pytest.raises(gotpl.TemplateExecutionError) as caught:
        template.render()

    error = caught.value
    assert (error.line, error.column) == (2, 3)
    assert error.source_name == "outer"
    assert error.template_name == "inner"
    assert error.__cause__ is failure


def test_top_level_render_accepts_a_diagnostic_template_name() -> None:
    with pytest.raises(gotpl.TemplateExecutionError) as caught:
        gotpl.render("{{.missing}}", {}, name="request", missing_key="error")

    assert caught.value.source_name == "request"
    assert 'template: request:1:3: executing "request"' in str(caught.value)


def test_execution_error_keeps_the_first_attached_location() -> None:
    error = gotpl.TemplateExecutionError("failed")
    error.attach_location("first", 1, source_name="first", template_name="one")
    error.attach_location("second", 2, source_name="second", template_name="two")

    assert error.source_name == "first"
    assert error.template_name == "one"
    assert error.position == 1
