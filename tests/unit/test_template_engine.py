from __future__ import annotations

import pytest

import gotpl
from gotpl import ExecutionBudget, PythonExtensions, SandboxPolicy
from gotpl.runtime.engine import TemplateEngine


def test_template_engine_renders_named_sources_with_independent_contexts() -> None:
    engine = TemplateEngine.from_sources(
        {
            "helpers.tpl": '{{define "label"}}{{.prefix}}:{{.value}}{{end}}',
            "first.txt": '{{template "label" .}}',
            "second.txt": '{{template "label" .}}',
        }
    )

    output = engine.render(
        {
            "second.txt": {"prefix": "second", "value": 2},
            "first.txt": {"prefix": "first", "value": 1},
        }
    )

    assert output == {"second.txt": "second:2", "first.txt": "first:1"}


def test_template_engine_derives_a_reusable_dynamic_source() -> None:
    engine = TemplateEngine.from_sources(
        {"helpers.tpl": '{{define "label"}}label:{{.}}{{end}}'}
    )

    derived = engine.with_source('{{template "label" .}}', name="main.txt")

    assert derived.render({"main.txt": "one"}) == {"main.txt": "label:one"}
    with pytest.raises(gotpl.TemplateExecutionError, match="not defined"):
        engine.render({"main.txt": "two"})


def test_template_engine_with_functions_returns_a_new_engine() -> None:
    def decorate(value: object) -> str:
        return f"<{value}>"

    parent = TemplateEngine.from_sources(
        {"page.tpl": "{{decorate .}}"}, functions={"decorate": str}
    )
    child = parent.with_functions({"decorate": decorate})

    assert parent.render({"page.tpl": "value"}) == {"page.tpl": "value"}
    assert child.render({"page.tpl": "value"}) == {"page.tpl": "<value>"}


def test_template_engine_exposes_single_template_and_dynamic_source_rendering() -> None:
    engine = TemplateEngine.from_sources(
        {"helpers.tpl": '{{define "label"}}label:{{.}}{{end}}'}
    )

    assert engine.render_template("label", "one") == "label:one"
    assert (
        engine.render_source('{{template "label" .}}', "two", name="dynamic.tpl")
        == "label:two"
    )


@pytest.mark.asyncio
async def test_template_engine_exposes_async_single_template_rendering() -> None:
    async def decorate(value: str) -> str:
        return f"<{value}>"

    engine = TemplateEngine.from_sources(
        {"main.tpl": "{{decorate .}}"}, functions={"decorate": decorate}
    )

    assert await engine.render_template_async("main.tpl", "one") == "<one>"
    assert await engine.render_source_async("{{decorate .}}", "two") == "<two>"


@pytest.mark.asyncio
async def test_template_engine_awaits_functions_across_source_contexts() -> None:
    async def identify(value: str) -> str:
        return f"async:{value}"

    engine = TemplateEngine.from_sources(
        {
            "helpers.tpl": '{{define "label"}}{{identify .}}{{end}}',
            "first.txt": '{{template "label" .}}',
            "second.txt": '{{template "label" .}}',
        },
        functions={"identify": identify},
    )

    assert await engine.render_async({"first.txt": "a", "second.txt": "b"}) == {
        "first.txt": "async:a",
        "second.txt": "async:b",
    }


def test_template_engine_carries_policy_budget_and_extensions() -> None:
    engine = TemplateEngine.from_sources(
        {"main.txt": '{{reMatch "x" .value}}'},
        sandbox=SandboxPolicy.strict(allow_functions={"reMatch"}),
        budget=ExecutionBudget(max_output_chars=4),
        extensions=PythonExtensions(re_match=True),
    )

    assert engine.render({"main.txt": {"value": "x"}}) == {"main.txt": "true"}
    with pytest.raises(gotpl.BudgetExceededError, match="output character"):
        engine.render({"main.txt": {"value": "missing"}})
