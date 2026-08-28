from __future__ import annotations

from collections.abc import Mapping
from io import StringIO
from typing import cast

import pytest

from gotpl import (
    AsyncRenderContext,
    ContextFunction,
    Environment,
    ExecutionBudget,
    RenderContext,
    SandboxPolicy,
    SandboxViolationError,
    TemplateExecutionError,
)


def test_context_function_renders_an_associated_template() -> None:
    def include(context: RenderContext, name: str, data: object) -> str:
        return context.render_template(name, data)

    engine = Environment(
        functions={"include": ContextFunction(sync=include)}
    ).from_sources(
        {
            "helpers.tpl": '{{define "label"}}label:{{.}}{{end}}',
            "main.tpl": '{{include "label" .value}}',
        }
    )

    assert engine.render_template("main.tpl", {"value": "one"}) == "label:one"


def test_context_function_renders_a_dynamic_source_with_current_association() -> None:
    def render_dynamic(context: RenderContext, source: str, data: object) -> str:
        return context.render_source(source, data, name="dynamic.tpl")

    engine = Environment(
        functions={"renderDynamic": ContextFunction(sync=render_dynamic)}
    ).from_sources(
        {
            "helpers.tpl": '{{define "label"}}label:{{.}}{{end}}',
            "main.tpl": "{{renderDynamic .source .value}}",
        }
    )

    assert (
        engine.render_template(
            "main.tpl",
            {"source": '{{template "label" .}}', "value": "two"},
        )
        == "label:two"
    )


def test_context_exposes_current_values_and_source_metadata() -> None:
    def inspect_context(context: RenderContext) -> str:
        root = cast(Mapping[str, object], context.root)
        dot = cast(Mapping[str, object], context.dot)
        return (
            f"{context.template_name}|{context.source_name}|"
            f"{root['root']}|{dot['root']}"
        )

    template = Environment(
        functions={"inspectContext": ContextFunction(sync=inspect_context)}
    ).from_string("{{inspectContext}}", name="main.tpl")

    assert template.render({"root": "value"}) == "main.tpl|main.tpl|value|value"


@pytest.mark.asyncio
async def test_async_context_function_uses_async_render_context() -> None:
    async def include(context: AsyncRenderContext, name: str, data: object) -> str:
        return await context.render_template(name, data)

    engine = Environment(
        functions={"include": ContextFunction(async_=include)}
    ).from_sources(
        {
            "helpers.tpl": '{{define "label"}}label:{{.}}{{end}}',
            "main.tpl": '{{include "label" .}}',
        }
    )

    assert await engine.render_template_async("main.tpl", "async") == "label:async"
    with pytest.raises(TemplateExecutionError, match="asynchronous rendering"):
        engine.render_template("main.tpl", "sync")


def test_context_parameter_is_hidden_from_template_arity() -> None:
    def contextual(context: RenderContext, value: str) -> str:
        del context
        return value

    template = Environment(
        functions={"contextual": ContextFunction(sync=contextual)}
    ).from_string("{{contextual}}")

    with pytest.raises(TemplateExecutionError, match="want 1 got 0"):
        template.render()


def test_context_function_requires_an_implementation() -> None:
    with pytest.raises(ValueError, match="sync or async"):
        ContextFunction()


def test_context_function_rejects_invalid_implementations_and_direct_calls() -> None:
    with pytest.raises(TypeError, match="sync implementation"):
        ContextFunction(sync="invalid")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="async implementation"):
        ContextFunction(async_="invalid")  # type: ignore[arg-type]

    def identity_context(context: RenderContext) -> RenderContext:
        return context

    function = ContextFunction(sync=identity_context)
    with pytest.raises(RuntimeError, match="called by a gotpl render"):
        function()


def test_context_extension_state_is_reused_within_one_render() -> None:
    key = object()

    def next_value(context: RenderContext) -> int:
        state = context.state(key, list[int])
        state.append(1)
        return len(state)

    template = Environment(
        functions={"nextValue": ContextFunction(sync=next_value)}
    ).from_string("{{nextValue}}{{nextValue}}")

    assert template.render() == "12"


@pytest.mark.asyncio
async def test_async_context_exposes_metadata_state_and_writer_paths() -> None:
    key = object()

    async def inspect(context: AsyncRenderContext) -> str:
        state = context.state(key, list[str])
        state.append(context.template_name)
        return f"{context.source_name}:{len(state)}:{context.root}:{context.dot}"

    template = Environment(
        functions={"inspect": ContextFunction(async_=inspect)}
    ).from_html_sources(
        {
            "main.html": '{{template "helper" .}}{{template "helper" .}}',
            "helper": '{{define "helper"}}{{inspect}}{{end}}',
        }
    )
    writer = StringIO()

    await template.render_template_async_to("main.html", writer, "value")

    assert writer.getvalue() == ("helper:1:value:valuehelper:2:value:value")


def test_html_context_supports_generic_root_and_named_writer_paths() -> None:
    key = object()

    def inspect(context: RenderContext) -> str:
        state = context.state(key, list[str])
        state.append(context.template_name)
        return f"{context.template_name}:{len(state)}"

    template = Environment(
        functions={"inspect": ContextFunction(sync=inspect)}
    ).from_html_sources(
        {
            "main.html": '{{template "helper" .}}{{template "helper" .}}',
            "helper": '{{define "helper"}}{{inspect}}{{end}}',
        }
    )
    root_writer = StringIO()
    named_writer = StringIO()

    template.render_to(root_writer, "value")
    template.render_template_to("main.html", named_writer, "value")

    assert root_writer.getvalue() == "helper:1helper:2"
    assert named_writer.getvalue() == "helper:1helper:2"


@pytest.mark.asyncio
async def test_async_html_context_captures_named_and_dynamic_templates() -> None:
    async def compose(context: AsyncRenderContext, data: object) -> str:
        associated = await context.render_template("helper", data)
        dynamic = await context.render_source("<i>{{.}}</i>", data)
        return f"{associated}|{dynamic}"

    template = Environment(
        functions={"compose": ContextFunction(async_=compose)}
    ).from_html_sources(
        {
            "main.html": "{{compose .}}",
            "helper": '{{define "helper"}}<b>{{.}}</b>{{end}}',
        }
    )

    assert await template.render_template_async("main.html", "<x>") == (
        "&lt;b&gt;&amp;lt;x&amp;gt;&lt;/b&gt;|&lt;i&gt;&amp;lt;x&amp;gt;&lt;/i&gt;"
    )


def test_sync_html_context_captures_an_associated_template() -> None:
    def include(context: RenderContext, data: object) -> str:
        return context.render_template("helper", data)

    template = Environment(
        functions={"include": ContextFunction(sync=include)}
    ).from_html_sources(
        {
            "main.html": "{{include .}}",
            "helper": '{{define "helper"}}<b>{{.}}</b>{{end}}',
        }
    )

    assert template.render_template("main.html", "<x>") == (
        "&lt;b&gt;&amp;lt;x&amp;gt;&lt;/b&gt;"
    )


def test_sandbox_requires_context_capabilities_explicitly() -> None:
    def include(context: RenderContext, name: str, data: object) -> str:
        return context.render_template(name, data)

    function = ContextFunction(
        sync=include,
        capabilities=frozenset({"render-associated"}),
    )

    with pytest.raises(SandboxViolationError, match="render-associated"):
        Environment(
            functions={"include": function},
            sandbox=SandboxPolicy.strict(allow_functions={"include"}),
        ).from_string('{{include "name" .}}')

    template = Environment(
        functions={"include": function},
        sandbox=SandboxPolicy.strict(
            allow_functions={"include"},
            allow_context_capabilities={"render-associated"},
        ),
    ).from_sources(
        {
            "helper": '{{define "name"}}ok{{end}}',
            "main": '{{include "name" .}}',
        }
    )
    assert template.render_template("main") == "ok"


def test_nested_render_shares_function_and_output_budgets() -> None:
    def include(context: RenderContext, name: str, data: object) -> str:
        return context.render_template(name, data)

    passing = Environment(
        functions={"include": ContextFunction(sync=include)},
        budget=ExecutionBudget(max_function_calls=1, max_output_chars=3),
    ).from_sources(
        {
            "helper": '{{define "value"}}abc{{end}}',
            "main": '{{include "value" .}}',
        }
    )
    assert passing.render_template("main") == "abc"

    failing = Environment(
        functions={"include": ContextFunction(sync=include)},
        budget=ExecutionBudget(max_function_calls=0),
    ).from_sources(
        {
            "helper": '{{define "value"}}abc{{end}}',
            "main": '{{include "value" .}}',
        }
    )
    with pytest.raises(TemplateExecutionError, match="function-call budget"):
        failing.render_template("main")


def test_html_context_dynamic_source_is_reanalyzed_and_remains_untrusted() -> None:
    def dynamic(context: RenderContext, source: str, data: object) -> str:
        return context.render_source(source, data)

    template = Environment(
        functions={"dynamic": ContextFunction(sync=dynamic)}
    ).from_html_string("<div>{{dynamic .source .value}}</div>")

    assert template.render({"source": "<b>{{.}}</b>", "value": "<x>"}) == (
        "<div>&lt;b&gt;&amp;lt;x&amp;gt;&lt;/b&gt;</div>"
    )
