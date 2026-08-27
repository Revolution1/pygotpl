from __future__ import annotations

import pytest

from examples.helm_runtime import Capabilities, Chart, Engine, Release
from gotpl import TemplateExecutionError


def _chart(**templates: str) -> Chart:
    return Chart(
        name="moby",
        version="1.2.3",
        app_version="2.0.0",
        templates=templates,
        files={"book/title.txt": "Moby-Dick"},
    )


def test_engine_renders_chart_globals_sprig_and_files() -> None:
    chart = _chart(
        **{
            "templates/main.yaml": (
                "{{.Chart.Name}}/{{.Chart.Version}}/{{.Chart.AppVersion}}|"
                "{{.Release.Name}}/{{.Release.Namespace}}|"
                "{{.Capabilities.KubeVersion.Version}}|"
                '{{.Files.Get "book/title.txt"}}|{{.Values.outer | title}}|'
                "{{.Template.Name}}/{{.Template.BasePath}}"
            )
        }
    )
    output = Engine().render(
        chart,
        {"outer": "spouter"},
        release=Release(name="demo", namespace="testing"),
        capabilities=Capabilities.default(),
    )

    assert output == {
        "moby/templates/main.yaml": (
            "moby/1.2.3/2.0.0|demo/testing|v1.36.0|Moby-Dick|Spouter|"
            "moby/templates/main.yaml/moby/templates"
        )
    }


def test_engine_include_tpl_required_and_partial_suppression() -> None:
    chart = _chart(
        **{
            "templates/_helpers.tpl": '{{define "label"}}{{.Release.Name}}-x{{end}}',
            "templates/main.yaml": (
                '{{include "label" .}}|{{tpl .Values.dynamic .}}|'
                '{{required "name is required" .Values.name}}'
            ),
        }
    )
    output = Engine().render(
        chart,
        {"dynamic": '{{include "label" .}}', "name": "ok"},
        release=Release(name="demo"),
    )

    assert output == {"moby/templates/main.yaml": "demo-x|demo-x|ok"}


def test_tpl_can_include_a_definition_from_its_dynamic_source() -> None:
    chart = _chart(**{"templates/main.yaml": "{{tpl .Values.dynamic .}}"})

    assert Engine().render(
        chart,
        {
            "name": "value",
            "dynamic": (
                '{{define "dynamic"}}dynamic:{{.Values.name}}{{end}}'
                '{{include "dynamic" .}}'
            ),
        },
    ) == {"moby/templates/main.yaml": "dynamic:value"}


def test_engine_required_and_fail_follow_lint_mode() -> None:
    required_chart = _chart(
        **{"templates/main.yaml": '{{required "name is required" .Values.name}}'}
    )
    with pytest.raises(TemplateExecutionError, match="name is required"):
        Engine().render(required_chart, {})

    fail_chart = _chart(**{"templates/main.yaml": 'before{{fail "broken"}}after'})
    with pytest.raises(TemplateExecutionError, match="broken"):
        Engine().render(fail_chart)
    assert Engine(lint_mode=True).render(fail_chart) == {
        "moby/templates/main.yaml": "beforeafter"
    }


def test_engine_strict_mode_and_disabled_dns_match_helm_defaults() -> None:
    chart = _chart(
        **{
            "templates/main.yaml": (
                '{{getHostByName "helm.sh"}}|{{tpl "{{.Values.missing}}" .}}'
            )
        }
    )
    assert Engine().render(chart) == {"moby/templates/main.yaml": "|"}
    with pytest.raises(TemplateExecutionError, match="missing"):
        Engine(strict=True).render(chart)


def test_engine_recurses_into_dependency_value_scopes_and_subcharts() -> None:
    child = Chart(
        name="child",
        version="1.0.0",
        templates={"templates/child.yaml": "{{.Values.value}}/{{.Chart.IsRoot}}"},
    )
    parent = Chart(
        name="parent",
        version="1.0.0",
        templates={
            "templates/main.yaml": "{{.Subcharts.child.Chart.Name}}/"
            "{{.Subcharts.child.Values.value}}"
        },
        dependencies=(child,),
    )

    assert Engine().render(parent, {"child": {"value": "scoped"}}) == {
        "parent/charts/child/templates/child.yaml": "scoped/false",
        "parent/templates/main.yaml": "child/scoped",
    }


@pytest.mark.asyncio
async def test_engine_async_awaits_functions_inside_include_and_tpl() -> None:
    async def identify(value: str) -> str:
        return f"async:{value}"

    chart = _chart(
        **{
            "templates/_helpers.tpl": (
                '{{define "helper"}}{{identify .Values.name}}{{end}}'
            ),
            "templates/main.yaml": (
                '{{include "helper" .}}|{{tpl "{{identify .Values.name}}" .}}'
            ),
        }
    )

    assert await Engine(custom_functions={"identify": identify}).render_async(
        chart, {"name": "value"}
    ) == {"moby/templates/main.yaml": "async:value|async:value"}
