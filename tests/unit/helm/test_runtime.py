from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor

import pytest

from gotpl import Environment, Template, TemplateExecutionError
from gotpl.exts.helm import HelmExtension, HelmTemplateEngine


def test_helm_extension_composes_with_generic_environment() -> None:
    engine = Environment(extensions=(HelmExtension(),)).from_sources(
        {
            "helpers.tpl": '{{define "label"}}{{.}}-label{{end}}',
            "main.txt": '{{include "label" .}}|{{tpl "{{.}}-tpl" .}}',
        }
    )

    assert engine.render_template("main.txt", "demo") == "demo-label|demo-tpl"


def test_helm_extension_is_explicitly_text_only() -> None:
    with pytest.raises(ValueError, match="do not support HTML"):
        Environment(extensions=(HelmExtension(),)).from_html_string("{{toYaml .}}")


def test_helm_template_engine_owns_include_tpl_required_and_fail() -> None:
    engine = HelmTemplateEngine.from_sources(
        {
            "helpers.tpl": '{{define "label"}}{{.name}}-label{{end}}',
            "main.txt": (
                '{{include "label" .}}|{{tpl .dynamic .}}|'
                '{{required "name required" .name}}'
            ),
        }
    )

    assert engine.render(
        {"main.txt": {"name": "demo", "dynamic": '{{include "label" .}}'}}
    ) == {"main.txt": "demo-label|demo-label|demo"}

    with pytest.raises(TemplateExecutionError, match="name required"):
        engine.render({"main.txt": {"dynamic": "ok"}})


def test_helm_template_engine_lint_mode_suppresses_required_and_fail() -> None:
    engine = HelmTemplateEngine.from_sources(
        {"main.txt": '{{required "missing" .missing}}|{{fail "broken"}}'},
        lint_mode=True,
    )

    assert engine.render({"main.txt": {}}) == {"main.txt": "|"}


def test_helm_template_engine_is_safe_to_reuse_across_threads() -> None:
    engine = HelmTemplateEngine.from_sources({"main.txt": "{{tpl .dynamic .}}"})

    def render(value: str) -> str:
        output = engine.render({"main.txt": {"value": value, "dynamic": "{{.value}}"}})
        return output["main.txt"]

    with ThreadPoolExecutor(max_workers=4) as executor:
        assert list(executor.map(render, ["one", "two", "three", "four"])) == [
            "one",
            "two",
            "three",
            "four",
        ]


def test_helm_template_engine_scopes_tpl_cache_to_one_render(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0
    original = Template.with_source

    def counted(engine: Template, source: str, *, name: str = "template") -> Template:
        nonlocal calls
        calls += 1
        return original(engine, source, name=name)

    monkeypatch.setattr(Template, "with_source", counted)
    engine = HelmTemplateEngine.from_sources(
        {
            "first.txt": "{{tpl .dynamic .}}",
            "second.txt": "{{tpl .dynamic .}}",
        }
    )
    contexts = {
        "first.txt": {"value": "one", "dynamic": "{{.value}}"},
        "second.txt": {"value": "two", "dynamic": "{{.value}}"},
    }

    assert engine.render(contexts) == {"first.txt": "one", "second.txt": "two"}
    assert engine.render(contexts) == {"first.txt": "one", "second.txt": "two"}
    assert calls == 2


@pytest.mark.asyncio
async def test_helm_template_engine_awaits_custom_functions_in_include_and_tpl() -> (
    None
):
    async def identify(value: str) -> str:
        return f"async:{value}"

    engine = HelmTemplateEngine.from_sources(
        {
            "helpers.tpl": '{{define "helper"}}{{identify .value}}{{end}}',
            "main.txt": ('{{include "helper" .}}|{{tpl "{{identify .value}}" .}}'),
        },
        custom_functions={"identify": identify},
    )

    assert await engine.render_async({"main.txt": {"value": "demo"}}) == {
        "main.txt": "async:demo|async:demo"
    }


@pytest.mark.asyncio
async def test_helm_template_engine_is_safe_to_reuse_across_asyncio_tasks() -> None:
    async def identify(value: str) -> str:
        await asyncio.sleep(0)
        return value

    engine = HelmTemplateEngine.from_sources(
        {"main.txt": '{{tpl "{{identify .value}}" .}}'},
        custom_functions={"identify": identify},
    )

    async def render(value: str) -> str:
        return (await engine.render_async({"main.txt": {"value": value}}))["main.txt"]

    assert await asyncio.gather(render("one"), render("two")) == ["one", "two"]
