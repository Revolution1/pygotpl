from __future__ import annotations

import pytest

import gotpl


@pytest.mark.parametrize(
    "source",
    [
        "Hello, {{. | urlquery | print}}!",
        "Hello, {{. | html | print}}!",
        "Hello, {{html . | print}}!",
        "<div class={{. | html}}>Hello</div>",
        "Hello, {{. | urlquery | html}}!",
    ],
)
def test_misplaced_predefined_escapers_are_rejected(source: str) -> None:
    with pytest.raises(gotpl.TemplateSyntaxError, match="predefined escaper"):
        gotpl.HTMLTemplate(source)


def test_predefined_html_escaper_is_not_applied_twice() -> None:
    value = "a&< b"

    assert gotpl.render_html("{{. | html}}", value) == "a&amp;&lt; b"
    assert gotpl.render_html("{{html .}}", value) == "a&amp;&lt; b"


def test_direct_predefined_escaper_preserves_go_multi_argument_spacing() -> None:
    assert (
        gotpl.render_html("{{html .A .B .C}}", {"A": 1, "B": 2, "C": "<&"})
        == "1 2&lt;&amp;"
    )


def test_predefined_html_in_javascript_still_receives_js_escaping() -> None:
    assert gotpl.render_html("<script>{{. | html}}</script>", "<&") == (
        '<script>"\\u0026lt;\\u0026amp;"</script>'
    )


@pytest.mark.parametrize(
    "pipeline",
    [". | urlquery", "urlquery ."],
)
def test_url_filter_runs_before_predefined_urlquery(pipeline: str) -> None:
    source = f'<a href="{{{{{pipeline}}}}}">'

    assert gotpl.render_html(source, "javascript:evil() & <") == (
        '<a href="%23ZgotmplZ">'
    )


def test_predefined_html_still_receives_unrelated_url_filtering() -> None:
    assert (
        gotpl.render_html('<a href="{{. | html}}">', "javascript:evil()")
        == '<a href="#ZgotmplZ">'
    )


def test_existing_internal_escaper_is_not_inserted_twice() -> None:
    name = "_html_template_htmlescaper"

    def identity(value: object) -> object:
        return value

    assert (
        gotpl.render_html(
            f"{{{{. | {name}}}}}",
            "a&<",
            functions={name: identity},
        )
        == "a&amp;&lt;"
    )
