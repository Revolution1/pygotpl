from __future__ import annotations

import pytest

import gotpl
from gotpl.html.escapers import (
    _TagStripper,  # pyright: ignore[reportPrivateUsage]
    js_value_escaper,
)


def test_trusted_html_bypasses_only_html_text_context() -> None:
    value = gotpl.HTML("Hello, <b>World</b> &amp;!<script>discard()</script>")

    assert gotpl.render_html("{{.}}", value) == value
    assert gotpl.render_html("<textarea>{{.}}</textarea>", value) == (
        "<textarea>Hello, &lt;b&gt;World&lt;/b&gt; &amp;!"
        "&lt;script&gt;discard()&lt;/script&gt;</textarea>"
    )
    assert gotpl.render_html("<a title='{{.}}'>", value) == (
        "<a title='Hello, World &amp;!'>"
    )
    assert gotpl.render_html("<a title={{.}}>", value) == (
        "<a title=Hello,&#32;World&#32;&amp;!>"
    )
    assert gotpl.render_html("<script>{{.}}</script>", value) == (
        '<script>"Hello, \\u003cb\\u003eWorld\\u003c/b\\u003e '
        '\\u0026amp;!\\u003cscript\\u003ediscard()\\u003c/script\\u003e"'
        "</script>"
    )


def test_each_trusted_type_bypasses_only_its_matching_context() -> None:
    assert (
        gotpl.render_html("<style>{{.}}</style>", gotpl.CSS("expression(trusted())"))
        == "<style>expression(trusted())</style>"
    )
    assert (
        gotpl.render_html("<style>{{.}}</style>", gotpl.JS("expression(untrusted())"))
        == "<style>ZgotmplZ</style>"
    )
    assert (
        gotpl.render_html("<script>{{.}}</script>", gotpl.JS('x && alert("ok")'))
        == '<script>x && alert("ok")</script>'
    )
    assert (
        gotpl.render_html('<script>"{{.}}"</script>', gotpl.JSStr(r"line\u0021"))
        == r'<script>"line\u0021"</script>'
    )
    assert js_value_escaper(gotpl.JSStr(r"line\u0021")) == r'"line\u0021"'
    assert (
        gotpl.render_html("<a href='{{.}}'>", gotpl.URL("javascript:trusted()"))
        == "<a href='javascript:trusted%28%29'>"
    )
    assert (
        gotpl.render_html("<a href='?q={{.}}'>", gotpl.URL("x&y"))
        == "<a href='?q=x&amp;y'>"
    )
    assert (
        gotpl.render_html(
            "<img srcset='{{.}}'>",
            gotpl.Srcset("javascript:trusted() 2x, /safe 1x"),
        )
        == "<img srcset='javascript:trusted() 2x, /safe 1x'>"
    )
    assert (
        gotpl.render_html("<img srcset='{{.}}'>", gotpl.URL(",foo/,"))
        == "<img srcset='%2cfoo/%2c'>"
    )


def test_trusted_html_attribute_and_plain_dynamic_names_preserve_structure() -> None:
    assert (
        gotpl.render_html("<a{{.}}>x</a>", gotpl.HTMLAttr(' dir="ltr"'))
        == '<a dir="ltr">x</a>'
    )
    assert gotpl.render_html("<a {{.}}=value>", "TITLE") == ("<a title=value>")
    assert gotpl.render_html("<a {{.}}=value>", "onclick") == ("<a ZgotmplZ=value>")
    assert gotpl.render_html("<a {{.}}=value>", "bad-name") == ("<a ZgotmplZ=value>")
    assert gotpl.render_html("<a {{.}}=value>", "data-href") == ("<a ZgotmplZ=value>")
    assert gotpl.render_html("<a {{.}}=value>", "xmlns:foo") == ("<a ZgotmplZ=value>")
    assert gotpl.render_html("<a {{.}}=value>", "svg:title") == ("<a ZgotmplZ=value>")
    assert gotpl.render_html("<h{{.}}>x</h{{.}}>", 3) == "<h3>x</h3>"


def test_trusted_types_remain_immutable_string_values() -> None:
    values = [
        gotpl.CSS("css"),
        gotpl.HTML("html"),
        gotpl.HTMLAttr("attr"),
        gotpl.JS("js"),
        gotpl.JSStr("js-string"),
        gotpl.URL("url"),
        gotpl.Srcset("srcset"),
    ]

    assert all(isinstance(value, str) for value in values)
    assert len(set(values)) == len(values)


def test_trusted_html_tag_stripping_preserves_entities_outside_active_content() -> None:
    value = gotpl.HTML("A&amp;&#65;<script>&amp;&#65;</script>")

    assert gotpl.render_html("<a title='{{.}}'>", value) == ("<a title='A&amp;&#65;'>")


def test_tag_stripper_suppresses_entity_callbacks_in_active_content() -> None:
    parser = _TagStripper()
    parser.suppressed = 1

    parser.handle_entityref("amp")
    parser.handle_charref("65")

    assert parser.output == []


@pytest.mark.asyncio
async def test_async_function_can_return_trusted_html() -> None:
    async def fragment() -> gotpl.HTML:
        return gotpl.HTML("<strong>trusted</strong>")

    template = gotpl.HTMLTemplate(
        "<section>{{fragment}}</section>", functions={"fragment": fragment}
    )

    assert await template.render_async() == (
        "<section><strong>trusted</strong></section>"
    )
