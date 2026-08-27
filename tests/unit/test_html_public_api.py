from __future__ import annotations

from io import StringIO

import pytest

import gotpl


def test_html_template_has_sync_writer_and_convenience_apis() -> None:
    template = gotpl.HTMLTemplate("<p>{{.}}</p>")
    output = StringIO()

    template.render_to(output, "<b>unsafe</b>")

    assert output.getvalue() == "<p>&lt;b&gt;unsafe&lt;/b&gt;</p>"
    assert template.render("Tom & Jerry") == "<p>Tom &amp; Jerry</p>"
    assert gotpl.render_html("{{.}}", "'quoted'") == "&#39;quoted&#39;"
    assert gotpl.HTMLTemplate('{{define "empty"}}{{end}}ok').render() == "ok"


def test_html_template_preserves_runtime_error_for_undefined_template() -> None:
    template = gotpl.HTMLTemplate('{{template "missing" .}}')

    with pytest.raises(gotpl.TemplateExecutionError, match="not defined"):
        template.render("value")
    with pytest.raises(gotpl.TemplateExecutionError, match="not defined"):
        template.render_template("missing", "value")


def test_html_template_renders_associated_named_templates() -> None:
    template = gotpl.HTMLTemplate('{{define "card"}}<p>{{.}}</p>{{end}}root')
    output = StringIO()

    template.render_template_to("card", output, "<&")

    assert output.getvalue() == "<p>&lt;&amp;</p>"
    assert template.render_template("card", "<&") == output.getvalue()


def test_html_template_builds_a_contextual_multi_source_association() -> None:
    template = gotpl.HTMLTemplate.from_sources(
        {
            "page.html": '<a href="/search?q={{template "value" .}}">open</a>',
            "value.html": '{{define "value"}}{{.}}{{end}}',
        }
    )

    assert template.render("a&b") == '<a href="/search?q=a%26b">open</a>'
    assert template.render_template("value", "<&") == "&lt;&amp;"


def test_html_template_with_source_is_immutable_and_reanalyzes_the_namespace() -> None:
    parent = gotpl.HTMLTemplate.from_sources(
        {"base.html": '{{define "card"}}<p>{{.}}</p>{{end}}base'}
    )
    child = parent.with_source(
        '<section>{{template "card" .}}</section>', name="page.html"
    )

    assert parent.render("<&") == "base"
    with pytest.raises(gotpl.TemplateExecutionError, match="not defined"):
        parent.render_template("page.html", "<&")
    assert child.render("<&") == "<section><p>&lt;&amp;</p></section>"
    assert (
        child.render_source(
            '<div>{{template "card" .}}</div>', "<&", name="dynamic.html"
        )
        == "<div><p>&lt;&amp;</p></div>"
    )


def test_html_template_rejects_incomplete_named_template_before_writing() -> None:
    template = gotpl.HTMLTemplate('{{define "fragment"}}<a{{end}}root')
    output = StringIO()

    with pytest.raises(gotpl.TemplateExecutionError, match="non-text context"):
        template.render_template_to("fragment", output)

    assert output.getvalue() == ""


@pytest.mark.asyncio
async def test_html_template_renders_named_template_asynchronously() -> None:
    async def value() -> str:
        return "<&"

    template = gotpl.HTMLTemplate(
        '{{define "card"}}<p>{{value}}</p>{{end}}',
        functions={"value": value},
    )
    output = StringIO()

    await template.render_template_async_to("card", output)

    assert output.getvalue() == "<p>&lt;&amp;</p>"
    assert await template.render_template_async("card") == output.getvalue()
    assert (
        await template.render_source_async(
            '<div>{{template "card" .}}</div>', name="dynamic.html"
        )
        == "<div><p>&lt;&amp;</p></div>"
    )


@pytest.mark.asyncio
async def test_html_named_async_writer_enforces_the_template_budget() -> None:
    template = gotpl.HTMLTemplate(
        '{{define "card"}}<p>{{.}}</p>{{end}}',
        budget=gotpl.ExecutionBudget(max_output_chars=3),
    )

    with pytest.raises(gotpl.BudgetExceededError, match="output character"):
        await template.render_template_async_to("card", StringIO(), "value")


@pytest.mark.asyncio
async def test_html_template_awaits_values_before_contextual_escaping() -> None:
    async def unsafe() -> str:
        return '<script>alert("unsafe")</script>'

    template = gotpl.HTMLTemplate("<p>{{unsafe}}</p>", functions={"unsafe": unsafe})

    assert await template.render_async() == (
        "<p>&lt;script&gt;alert(&#34;unsafe&#34;)&lt;/script&gt;</p>"
    )


@pytest.mark.asyncio
async def test_html_convenience_writer_apis_match_reusable_templates() -> None:
    sync_output = StringIO()
    async_output = StringIO()

    gotpl.render_html_to("<b>{{.}}</b>", sync_output, "<&>")
    await gotpl.render_html_async_to("<b>{{.}}</b>", async_output, "<&>")

    assert sync_output.getvalue() == "<b>&lt;&amp;&gt;</b>"
    assert async_output.getvalue() == sync_output.getvalue()
    assert await gotpl.render_html_async("{{.}}", "<&>") == "&lt;&amp;&gt;"


@pytest.mark.asyncio
async def test_html_template_awaits_structured_javascript_values() -> None:
    async def payload() -> dict[str, str]:
        return {"tag": "</script>"}

    template = gotpl.HTMLTemplate(
        "<script>const payload={{payload}};</script>",
        functions={"payload": payload},
    )

    assert await template.render_async() == (
        '<script>const payload={"tag":"\\u003c/script\\u003e"};</script>'
    )


@pytest.mark.asyncio
async def test_html_template_awaits_values_before_css_filtering() -> None:
    async def color() -> str:
        return "expression(alert(1))"

    template = gotpl.HTMLTemplate(
        "<style>p{color:{{color}}}</style>",
        functions={"color": color},
    )

    assert await template.render_async() == "<style>p{color:ZgotmplZ}</style>"


@pytest.mark.asyncio
async def test_html_template_awaits_values_before_srcset_filtering() -> None:
    async def candidates() -> str:
        return "javascript:evil() 1x, /safe.png 2x"

    template = gotpl.HTMLTemplate(
        '<img srcset="{{candidates}}">',
        functions={"candidates": candidates},
    )

    assert await template.render_async() == ('<img srcset="#ZgotmplZ, /safe.png 2x">')
