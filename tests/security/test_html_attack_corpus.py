from __future__ import annotations

import pytest

import gotpl


@pytest.mark.parametrize("tag", ["div", "script", "style", "textarea", "title"])
def test_complete_dynamic_special_tag_names_remain_text(tag: str) -> None:
    source = "<{{.}}>payload</{{.}}>"

    assert gotpl.render_html(source, tag) == f"&lt;{tag}>payload&lt;/{tag}>"


@pytest.mark.parametrize(
    "name",
    [
        "onload",
        "style",
        "src",
        "srcdoc",
        "srcset",
        "data-href",
        "xmlns:foo",
        "async",
        "challenge",
        "charset",
        "content",
        "crossorigin",
        "defer",
        "enctype",
        "form",
        "formenctype",
        "formmethod",
        "formnovalidate",
        "http-equiv",
        "keytype",
        "language",
        "method",
        "novalidate",
        "pattern",
        "rel",
        "sandbox",
        "type",
        "value",
        "data-type",
        "svg:method",
    ],
)
def test_dynamic_active_attribute_names_are_replaced(name: str) -> None:
    assert gotpl.render_html('<img {{.}}="javascript:evil()">', name) == (
        '<img ZgotmplZ="javascript:evil()">'
    )


@pytest.mark.parametrize(
    "payload",
    [
        "expression(alert(1))",
        "-moz-binding",
        r"-express\69 on(alert(1))",
        r"-exp\000072 ession(alert(1))",
        "</style",
        "/* injected */",
        "[href=javascript:evil()]",
    ],
)
def test_obfuscated_css_active_content_is_replaced(payload: str) -> None:
    assert gotpl.render_html('<p style="width: {{.}}">', payload) == (
        '<p style="width: ZgotmplZ">'
    )


def test_each_srcset_candidate_receives_protocol_filtering() -> None:
    payload = "/safe.png 1x, javascript:evil() 2x, /also-safe.png 3x"

    assert gotpl.render_html('<img srcset="{{.}}">', payload) == (
        '<img srcset="/safe.png 1x,#ZgotmplZ, /also-safe.png 3x">'
    )


@pytest.mark.parametrize("scheme", ["javascript", "vbscript", "data"])
def test_meta_refresh_urls_receive_protocol_filtering(scheme: str) -> None:
    source = '<meta http-equiv="refresh" content="0; url={{.}}">'

    assert gotpl.render_html(source, f"{scheme}:evil()") == (
        '<meta http-equiv="refresh" content="0; url=#ZgotmplZ">'
    )


def test_meta_refresh_tracks_case_whitespace_and_multiple_urls() -> None:
    source = (
        '<meta http-equiv=" REFRESH " '
        'content="start; URL \t= {{.First}}; next; url={{.Second}}">'
    )

    assert gotpl.render_html(
        source,
        {"First": "javascript:evil()", "Second": "vbscript:evil()"},
    ) == (
        '<meta http-equiv=" REFRESH " '
        'content="start; URL \t= #ZgotmplZ; next; url=#ZgotmplZ">'
    )


def test_meta_non_url_content_and_non_refresh_meta_remain_plain_attributes() -> None:
    assert (
        gotpl.render_html(
            '<meta http-equiv="refresh" content="message={{.}}">',
            "javascript:plain-text",
        )
        == '<meta http-equiv="refresh" content="message=javascript:plain-text">'
    )
    assert gotpl.render_html(
        '<meta http-equiv="content-type" content="url={{.}}">',
        "javascript:plain-text",
    ) == ('<meta http-equiv="content-type" content="url=javascript:plain-text">')


def test_meta_refresh_keeps_safe_protocols() -> None:
    source = '<meta http-equiv="refresh" content="0; url={{.}}">'

    assert gotpl.render_html(source, "https://example.com/next?q=1&x=2") == (
        '<meta http-equiv="refresh" '
        'content="0; url=https://example.com/next?q=1&amp;x=2">'
    )


def test_trusted_values_cannot_cross_into_active_contexts() -> None:
    assert (
        gotpl.render_html('<a href="{{.}}">', gotpl.HTML("javascript:evil()"))
        == '<a href="#ZgotmplZ">'
    )
    assert (
        gotpl.render_html("<script>{{.}}</script>", gotpl.URL("alert(1)"))
        == '<script>"alert(1)"</script>'
    )
    assert (
        gotpl.render_html("<style>{{.}}</style>", gotpl.JS("expression(evil())"))
        == "<style>ZgotmplZ</style>"
    )


@pytest.mark.parametrize(
    "element, false_end",
    [
        ("textarea", "</textareaevil>"),
        ("title", "</titlex>"),
    ],
)
def test_rcdata_false_end_prefix_does_not_enable_trusted_html(
    element: str, false_end: str
) -> None:
    source = f"<{element}>before{false_end}{{{{.}}}}</{element}>"

    assert gotpl.render_html(source, gotpl.HTML("<b>unsafe</b>")) == (
        f"<{element}>before{false_end.replace('<', '&lt;')}"
        f"&lt;b&gt;unsafe&lt;/b&gt;</{element}>"
    )
