from __future__ import annotations

import pytest

import gotpl
from gotpl.html import context as html_context
from gotpl.html import escapers as html_escapers
from gotpl.html.context import (
    AttributeKind,
    Context,
    ContextKind,
    EscapeKind,
    JSContext,
    URLPart,
)
from gotpl.html.escapers import (
    attr_escaper,
    comment_escaper,
    css_escaper,
    css_value_filter,
    html_escaper,
    js_regexp_escaper,
    js_string_escaper,
    js_template_escaper,
    js_value_escaper,
    nospace_escaper,
    rcdata_escaper,
    srcset_escaper,
    url_escaper,
    url_filter,
    url_normalizer,
)
from gotpl.runtime import INVALID, UNTYPED_NIL


def test_initial_html_escapers_cover_nil_missing_and_control_values() -> None:
    assert html_escaper(None) == ""
    assert rcdata_escaper(UNTYPED_NIL) == ""
    assert attr_escaper(INVALID) == "&lt;no value&gt;"
    assert html_escaper("\x00<&\"'+>") == "�&lt;&amp;&#34;&#39;&#43;&gt;"
    assert nospace_escaper("") == "ZgotmplZ"
    assert nospace_escaper("\x00\t\n\v\f\r \"&'+<=>`") == (
        "&#xfffd;&#9;&#10;&#11;&#12;&#13;&#32;&#34;&amp;&#39;&#43;&lt;&#61;&gt;&#96;"
    )
    assert comment_escaper("not emitted") == ""


def test_context_removes_comments_across_chunks_and_treats_less_than_as_text() -> None:
    context = Context()

    assert context.consume("before<!-- open") == "before"
    assert context.kind is ContextKind.COMMENT
    assert context.escape_kind() is EscapeKind.COMMENT
    assert context.consume(" hidden -->after < 3") == "after &lt; 3"
    assert context.kind is ContextKind.TEXT

    assert gotpl.render_html("I <3 Ponies!") == "I &lt;3 Ponies!"
    assert gotpl.render_html("Unicode <é> stays text") == ("Unicode &lt;é> stays text")
    assert gotpl.render_html("<x-y>custom</x-y>") == "<x-y>custom</x-y>"
    assert gotpl.render_html("<!doCtYPE htMl>Hello") == ("<!doCtYPE htMl>Hello")
    assert gotpl.render_html("<![CDATA[x]]>") == "&lt;![CDATA[x]]>"


def test_context_tracks_rcdata_and_case_insensitive_closing_tags() -> None:
    context = Context()

    assert context.consume("<TITLE>body") == "<TITLE>body"
    assert context.kind is ContextKind.RCDATA
    assert context.escape_kind() is EscapeKind.RCDATA
    assert context.consume(" and more") == " and more"
    assert context.consume("</TiTlE >tail") == "</TiTlE >tail"

    assert gotpl.render_html("<textarea>Straße</textarea>") == (
        "<textarea>Straße</textarea>"
    )
    assert gotpl.render_html("<textarea><!doCtYPE html></textarea>") == (
        "<textarea><!doCtYPE html></textarea>"
    )
    assert context.kind is ContextKind.TEXT


def test_context_tracks_attribute_spacing_delimiters_and_valueless_names() -> None:
    context = Context()
    source = "<input disabled checked = bare single = 'x' double=\"y\">"

    assert context.consume(source) == source
    assert context.kind is ContextKind.TEXT

    context.consume("<p title = '")
    assert context.kind is ContextKind.ATTR
    assert context.escape_kind() is EscapeKind.ATTR
    context.consume("x' data=")
    assert context.kind is ContextKind.BEFORE_VALUE
    assert context.escape_kind() is EscapeKind.NOSPACE
    assert context.kind is ContextKind.ATTR
    assert context.consume("x >") == "x >"
    assert context.kind is ContextKind.TEXT

    partial = Context()
    assert partial.consume("<button on") == "<button on"
    assert partial.kind is ContextKind.ATTR_NAME
    assert partial.attribute is AttributeKind.JS
    assert partial.consume("click") == "click"
    assert partial.kind is ContextKind.ATTR_NAME
    assert partial.consume('="') == '="'
    assert partial.kind is ContextKind.JS


def test_url_filter_and_processors_match_go_utf8_and_percent_rules() -> None:
    assert url_filter("javascript:alert(1)") == "#ZgotmplZ"
    assert url_filter("HTTPS://example.test/a") == "HTTPS://example.test/a"
    assert url_filter("/javascript:80/path") == "/javascript:80/path"
    assert url_normalizer("/foo|bar/%5cሴ") == "/foo%7cbar/%5c%e1%88%b4"
    assert url_normalizer("%2 %z") == "%252%20%25z"
    assert url_escaper("<'a b'>&") == "%3c%27a%20b%27%3e%26"


def test_url_context_normalizes_path_continuations_and_namespaced_href() -> None:
    assert gotpl.render_html("<a href='http://{{.}}'>", "host/a b") == (
        "<a href='http://host/a%20b'>"
    )
    assert gotpl.render_html("<a xlink:href='{{.}}'>", "javascript:bad()") == (
        "<a xlink:href='#ZgotmplZ'>"
    )


def test_javascript_escapers_cover_values_strings_templates_and_regexps() -> None:
    assert js_value_escaper(None) == " null "
    assert js_value_escaper(42) == " 42 "
    assert js_value_escaper(-0.5) == " -0.5 "
    assert js_value_escaper({"z": "</script>", "a": [True, None]}) == (
        '{"a":[true,null],"z":"\\u003c/script\\u003e"}'
    )
    assert js_value_escaper(b"Go!") == '"R28h"'
    assert js_string_escaper("\x00\t\n\v\f\r\"'`&+/<>") == (
        r"\u0000\t\n\u000b\f\r\u0022\u0027\u0060\u0026\u002b\/\u003c\u003e"
    )
    assert js_template_escaper("${value}") == r"\u0024\u007bvalue\u007d"
    assert js_regexp_escaper("") == "(?:)"
    assert js_regexp_escaper("a+b[c](d)?") == r"a\u002bb\[c\]\(d\)\?"


def test_javascript_context_tracks_slashes_literals_and_template_interpolation() -> (
    None
):
    context = Context()

    assert context.consume("<script>const value=") == "<script>const value="
    assert context.kind is ContextKind.JS
    assert context.escape_kind() is EscapeKind.JS_VALUE
    assert context.js_context is JSContext.DIVISION
    assert context.consume("/2;const pattern=/") == "/2;const pattern=/"
    assert context.kind is ContextKind.JS_REGEXP
    assert context.escape_kind() is EscapeKind.JS_REGEXP
    assert context.consume('x+/;const message="') == 'x+/;const message="'
    assert context.escape_kind() is EscapeKind.JS_STRING
    assert context.consume('done";const template=`') == 'done";const template=`'
    assert context.escape_kind() is EscapeKind.JS_TEMPLATE
    assert context.consume("${{value: 1}}}tail`") == "${{value: 1}}}tail`"
    assert context.kind is ContextKind.JS


def test_event_attribute_entities_select_javascript_string_escaping() -> None:
    source = '<button onclick="alert(&quot;{{.}}&quot;)">x</button>'

    assert gotpl.render_html(source, "</script>") == (
        '<button onclick="alert(&quot;\\u003c\\/script\\u003e&quot;)">x</button>'
    )
    assert gotpl.render_html("<button onclick=alert({{.}})>", "<x>") == (
        "<button onclick=alert(&#34;\\u003cx\\u003e&#34;)>"
    )
    assert gotpl.render_html(
        "<button onclick='const x=\"<script><!--</script>\"'>x</button>"
    ) == ("<button onclick='const x=\"\\x3Cscript>\\x3C!--\\x3C/script>\"'>x</button>")


def test_javascript_value_errors_are_emitted_as_safe_null_comments() -> None:
    cyclic: list[object] = []
    cyclic.append(cyclic)

    rendered = js_value_escaper(cyclic)

    assert rendered.startswith(" /* ")
    assert "encountered a cycle" in rendered
    assert rendered.endswith(" */null ")


def test_javascript_value_encoder_covers_go_json_boundaries() -> None:
    mapping: dict[object, object] = {2: "two", "1": "one"}
    mapping["self"] = mapping

    assert "encountered a cycle" in js_value_escaper(mapping)
    assert "unsupported map key type" in js_value_escaper({object(): "value"})
    assert "unsupported type" in js_value_escaper(object())
    assert "unsupported float value" in js_value_escaper(float("inf"))
    assert js_value_escaper(1e21) == " 1e+21 "
    assert js_value_escaper(1e-7) == " 1e-7 "
    assert js_value_escaper(1e-6) == " 0.000001 "
    assert js_value_escaper(INVALID) == " null "

    class ExplodingMapping(dict[object, object]):
        def items(self) -> object:  # type: ignore[override]
            raise ValueError("</script> */ <!--")

    error = js_value_escaper(ExplodingMapping())
    assert r"\x3C/script> * / \x3C!--" in error


def test_javascript_lexer_covers_escapes_comments_and_regexp_charsets() -> None:
    context = Context()

    assert context.consume(r"<script>const t=`a\`b`;const r=/a\/b[x]/;") == (
        r"<script>const t=`a\`b`;const r=/a\/b[x]/;"
    )
    assert context.kind is ContextKind.JS
    assert context.consume("before--> hidden\nnext<!-- hidden\nend") == (
        "before\nnext\nend"
    )

    regexp = Context(
        kind=ContextKind.JS_REGEXP,
        js_regexp_charset=True,
    )
    with pytest.raises(gotpl.TemplateSyntaxError, match="character class"):
        regexp.escape_kinds()


def test_next_javascript_context_matches_upstream_token_heuristic() -> None:
    next_context = html_context._next_js_context  # pyright: ignore[reportPrivateUsage]

    assert next_context("   ", JSContext.REGEXP) is JSContext.REGEXP
    assert next_context("x++", JSContext.REGEXP) is JSContext.DIVISION
    assert next_context("x---", JSContext.DIVISION) is JSContext.REGEXP
    assert next_context("42.", JSContext.REGEXP) is JSContext.DIVISION
    assert next_context(".", JSContext.DIVISION) is JSContext.REGEXP
    assert next_context("=", JSContext.DIVISION) is JSContext.REGEXP
    assert next_context("}", JSContext.DIVISION) is JSContext.REGEXP
    assert next_context("return", JSContext.DIVISION) is JSContext.REGEXP
    assert next_context("value", JSContext.REGEXP) is JSContext.DIVISION


def test_javascript_braces_update_regexp_context() -> None:
    context = Context(kind=ContextKind.JS, js_context=JSContext.DIVISION)

    assert context.consume("if(true){") == "if(true){"
    assert context.js_context is JSContext.REGEXP
    assert context.consume("/pattern/") == "/pattern/"
    assert context.kind is ContextKind.JS

    context.js_context = JSContext.DIVISION
    assert context.consume("}") == "}"
    assert context.js_context is JSContext.REGEXP

    interpolation = Context(kind=ContextKind.JS_TEMPLATE)
    assert interpolation.consume("${function(){") == "${function(){"
    assert interpolation.js_brace_depth == (1,)
    assert interpolation.js_context is JSContext.REGEXP
    assert interpolation.consume("}/pattern/}") == "}/pattern/}"
    assert interpolation.kind is ContextKind.JS_TEMPLATE


def test_css_escaper_and_decoder_cover_upstream_escape_boundaries() -> None:
    decode = html_escapers.decode_css

    assert css_escaper("\x00\t\n\f\r\"&'()+/:;<>{}\\A") == (
        r"\0 \9 \a \c \d\22\26\27\28\29\2b\2f\3a\3b\3c\3e\7b\7d\\A"
    )
    assert decode("foo\\") == "foo"
    assert decode(r"\A") == "\n"
    assert decode(r"\1234 5") == "\u12345"
    assert decode("\\1234\r\n5") == "\u12345"
    assert decode(r"\110000") == "\U000110000"
    assert decode(r"\D800") == "\ufffd"
    assert decode(r"\.") == "."


@pytest.mark.parametrize(
    "value",
    [
        "foo",
        "0",
        "-5px",
        "+.33em",
        "100%",
        ".class",
        "#123456",
        "color: red",
        "U+00-FF, U+980-9FF",
    ],
)
def test_css_value_filter_allows_inert_values(value: str) -> None:
    assert css_value_filter(value) == value


@pytest.mark.parametrize(
    "value",
    [
        "<!--",
        "-->",
        "</style",
        '"',
        "'",
        "`",
        "\x00",
        "/* comment */",
        "//",
        "[href=~",
        "expression(alert(1))",
        r"-express\69 on(alert(1))",
        "-moz-binding",
        "@import evil.css",
    ],
)
def test_css_value_filter_rejects_active_or_boundary_breaking_values(
    value: str,
) -> None:
    assert css_value_filter(value) == "ZgotmplZ"


def test_css_context_tracks_strings_urls_comments_and_entities() -> None:
    context = Context()

    source = '<style>/* hidden */p{background:url("/img?q='
    assert context.consume(source) == '<style> p{background:url("/img?q='
    assert context.kind is ContextKind.CSS_DQ_URL
    assert context.escape_kind() is EscapeKind.URL_ESCAPER
    assert context.consume("\");font-family:'") == "\");font-family:'"
    assert context.kind is ContextKind.CSS_SQ_STRING
    assert context.escape_kind() is EscapeKind.URL_ESCAPER
    assert context.consume("x'}</style>") == "x'}</style>"
    assert context.kind is ContextKind.TEXT

    assert (
        gotpl.render_html('<p style="font-family: &quot;{{.}}&quot;">x</p>', 'A"B &')
        == '<p style="font-family: &quot;A\\22 B \\26 &quot;">x</p>'
    )
    assert gotpl.render_html("<p style=color:{{.}}>", "#fff") == (
        "<p style=color:#fff>"
    )


def test_css_lexer_covers_url_spacing_escapes_and_comment_boundaries() -> None:
    context = Context()

    assert context.consume('<style>x{a:url(  "/img') == '<style>x{a:url(  "/img'
    assert context.kind is ContextKind.CSS_DQ_URL
    assert context.consume(r"\41 b\.") == r"\41 b\."
    assert context.url_part is URLPart.PRE_QUERY
    with pytest.raises(gotpl.TemplateSyntaxError, match="unfinished escape"):
        context.consume("\\")

    block = Context()
    assert block.consume("<style>/* open") == "<style> "
    assert block.kind is ContextKind.CSS_BLOCK_COMMENT
    line = Context()
    assert line.consume("<style>// open") == "<style>"
    assert line.kind is ContextKind.CSS_LINE_COMMENT

    assert gotpl.render_html("<p style='/* keep */color:red'>x</p>") == (
        "<p style='/* keep */color:red'>x</p>"
    )
    assert Context().consume("<style>x{a:calc(1<2)}</style>") == (
        "<style>x{a:calc(1<2)}</style>"
    )


def test_css_lexer_helpers_match_upstream_keyword_and_escape_rules() -> None:
    ends_with = html_context._ends_with_css_keyword  # pyright: ignore[reportPrivateUsage]
    escape_end = html_context._css_escape_end  # pyright: ignore[reportPrivateUsage]

    assert not ends_with("", "url")
    assert not ends_with("imageurl", "url")
    assert ends_with("image URL", "url")
    assert escape_end(r"\.", 0) == 2
    assert escape_end("\\1234 rest", 0) == 6
    assert escape_end("\\A\r\nrest", 0) == 4
    assert escape_end(r"\1234567", 0) == 7


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("http://example.com/img.png", "http://example.com/img.png"),
        (" /img.png 200w", " /img.png 200w"),
        ("javascript:alert(1) 200w", "#ZgotmplZ"),
        ("foo.png, bar.png", "foo.png, bar.png"),
        ("javascript:alert(1), /foo.png", "#ZgotmplZ, /foo.png"),
        ("/bogus#, javascript:alert(1)", "/bogus#,#ZgotmplZ"),
        ("/image(1).png 2x", "/image%281%29.png 2x"),
        ("/image.png 1.5x", "#ZgotmplZ"),
        (",,,,,", ",,,,,"),
    ],
)
def test_srcset_escaper_filters_each_candidate(value: str, expected: str) -> None:
    assert srcset_escaper(value) == expected


def test_srcset_context_applies_quoted_and_unquoted_attribute_escaping() -> None:
    context = Context()

    assert context.consume('<img srcset="') == '<img srcset="'
    assert context.kind is ContextKind.SRCSET
    assert context.escape_kinds() == (EscapeKind.SRCSET, EscapeKind.ATTR)
    assert context.consume('literal 2x">') == 'literal 2x">'
    assert context.kind is ContextKind.TEXT

    assert gotpl.render_html("<img srcset={{.}}>", None) == ("<img srcset=ZgotmplZ>")
