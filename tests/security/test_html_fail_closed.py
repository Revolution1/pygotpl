from __future__ import annotations

import pytest

import gotpl


def test_branch_paths_that_end_in_different_html_states_fail_closed() -> None:
    with pytest.raises(
        gotpl.TemplateSyntaxError, match="branches end in different HTML contexts"
    ):
        gotpl.HTMLTemplate("{{if .T}}<a href='{{else}}plain{{end}}{{.}}")


def test_nudged_branch_paths_still_reject_incompatible_attribute_states() -> None:
    with pytest.raises(
        gotpl.TemplateSyntaxError, match="branches end in different HTML contexts"
    ):
        gotpl.HTMLTemplate("<a {{if .T}}href={{end}}>")


@pytest.mark.parametrize(
    "source, message",
    [
        ("<script>const value='unterminated\\", "unfinished escape sequence"),
        ("<script>const pattern=/[{{.}}]/</script>", "regexp character class"),
    ],
)
def test_unsupported_javascript_boundaries_fail_closed(
    source: str, message: str
) -> None:
    with pytest.raises(gotpl.TemplateSyntaxError, match=message):
        gotpl.HTMLTemplate(source)


def test_ambiguous_javascript_slash_fails_closed_for_the_specific_reason() -> None:
    source = "<script>{{if .T}}x={{else}}x{{end}}/{{.V}}/</script>"

    with pytest.raises(
        gotpl.TemplateSyntaxError,
        match="could start a division or JavaScript regexp",
    ):
        gotpl.HTMLTemplate(source)


def test_ambiguous_css_url_fails_closed_for_the_specific_reason() -> None:
    source = '<p style="background:url({{if .T}}/img/{{else}}/img?q={{end}}{{.}})">'

    with pytest.raises(gotpl.TemplateSyntaxError, match="ambiguous context"):
        gotpl.HTMLTemplate(source)


def test_unfinished_css_escape_fails_closed() -> None:
    with pytest.raises(gotpl.TemplateSyntaxError, match="unfinished escape"):
        gotpl.HTMLTemplate("<style>p{font-family:'unfinished\\")


def test_srcset_filters_unsafe_protocols_and_invalid_descriptors_independently() -> (
    None
):
    source = '<img srcset="{{.}}">'
    value = "javascript:alert(1) 2x, /safe.png 2x, /other.png 1.5x"

    assert gotpl.render_html(source, value) == (
        '<img srcset="#ZgotmplZ, /safe.png 2x,#ZgotmplZ">'
    )


def test_trusted_content_types_do_not_bypass_unrelated_contexts() -> None:
    assert gotpl.render_html("{{.}}", gotpl.JS("<script>evil()</script>")) == (
        "&lt;script&gt;evil()&lt;/script&gt;"
    )
    assert (
        gotpl.render_html("<style>{{.}}</style>", gotpl.HTML("expression(evil())"))
        == "<style>ZgotmplZ</style>"
    )
    assert (
        gotpl.render_html("<script>{{.}}</script>", gotpl.CSS("alert(1)"))
        == '<script>"alert(1)"</script>'
    )


@pytest.mark.parametrize(
    "source",
    [
        "<input type=button value=onclick=>",
        "<a class=`foo>",
        "<a style=font:'Arial'>",
        "<a onclick=foo'bar>",
        "<img srcset=foo`bar>",
        "<a=foo>",
    ],
)
def test_malformed_static_unquoted_attributes_fail_closed(source: str) -> None:
    with pytest.raises(gotpl.TemplateSyntaxError, match=r"unquoted|attribute"):
        gotpl.HTMLTemplate(source)


@pytest.mark.parametrize(
    "source",
    [
        "<script>foo();",
        "<textarea>foo",
        "<a b=1 c={{.}}",
    ],
)
def test_templates_ending_in_non_text_contexts_fail_closed(source: str) -> None:
    with pytest.raises(gotpl.TemplateSyntaxError, match="non-text context"):
        gotpl.HTMLTemplate(source)


@pytest.mark.parametrize(
    "source",
    [
        '<a foo"bar=x>',
        "<a foo'bar=x>",
        "<a foo<bar=x>",
        '<a foo{{.}}"bar=x>',
    ],
)
def test_malformed_static_attribute_names_fail_closed(source: str) -> None:
    with pytest.raises(gotpl.TemplateSyntaxError, match="attribute name"):
        gotpl.HTMLTemplate(source)
