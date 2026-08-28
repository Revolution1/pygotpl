from __future__ import annotations

import json
import os
import shutil
import subprocess
from collections.abc import Mapping
from pathlib import Path
from typing import TypedDict, cast

import pytest

from examples.helm_runtime import (
    Capabilities,
    Chart,
    Engine,
    HelmFiles,
    Release,
    load_chart,
)
from gotpl import TemplateExecutionError

PROJECT_ROOT = Path(__file__).parents[2]
ORACLE_ROOT = PROJECT_ROOT / "tools" / "helm_oracle"
FIXTURE_ROOT = Path(__file__).parents[1] / "fixtures" / "helm" / "basic"


class HelmOracleRequest(TypedDict):
    name: str
    version: str
    app_version: str
    templates: dict[str, str]
    files: dict[str, str]
    dependencies: list[HelmOracleRequest]
    values: dict[str, object]
    release_name: str
    namespace: str
    strict: bool
    lint_mode: bool
    custom_profile: str


class HelmOracleResponse(TypedDict):
    output: dict[str, str]
    error: str


def _run_oracle(request: HelmOracleRequest) -> HelmOracleResponse:
    if shutil.which("go") is None:
        pytest.skip("the Helm conformance oracle requires the Go toolchain")
    environment = os.environ.copy()
    environment["GOCACHE"] = str(PROJECT_ROOT / ".cache" / "go-build")
    environment["GOMODCACHE"] = str(PROJECT_ROOT / ".cache" / "go-mod")
    process = subprocess.run(
        ["go", "run", "."],
        cwd=ORACLE_ROOT,
        env=environment,
        input=json.dumps(request) + "\n",
        capture_output=True,
        check=False,
        text=True,
        timeout=120,
    )
    if process.returncode != 0:
        raise AssertionError(f"Helm oracle failed: {process.stderr}")
    return cast(HelmOracleResponse, json.loads(process.stdout))


def _request(chart: Chart, values: Mapping[str, object]) -> HelmOracleRequest:
    files = cast(HelmFiles, chart.files)
    return {
        "name": chart.name,
        "version": chart.version,
        "app_version": chart.app_version,
        "templates": dict(chart.templates),
        "files": {name: value.decode() for name, value in files.items()},
        "dependencies": [_request(child, {}) for child in chart.dependencies],
        "values": dict(values),
        "release_name": "demo",
        "namespace": "testing",
        "strict": False,
        "lint_mode": False,
        "custom_profile": "",
    }


def test_helm_fixture_matches_the_pinned_v4_engine() -> None:
    chart = load_chart(FIXTURE_ROOT)
    values = {"name": "Python"}
    expected = _run_oracle(_request(chart, values))
    actual = Engine().render(
        chart,
        values,
        release=Release(name="demo", namespace="testing"),
        capabilities=Capabilities.default(),
    )

    assert expected == {"output": actual}


def test_helm_include_tpl_required_and_capabilities_match_the_pinned_engine() -> None:
    chart = Chart(
        name="moby",
        version="1.2.3",
        templates={
            "templates/_helpers.tpl": ('{{define "label"}}{{.Release.Name}}-x{{end}}'),
            "templates/main.yaml": (
                '{{include "label" .}}|{{tpl .Values.dynamic .}}|'
                '{{required "name is required" .Values.name}}|'
                "{{.Capabilities.KubeVersion.Version}}"
            ),
        },
    )
    values = {"dynamic": '{{include "label" .}}', "name": "ok"}
    expected = _run_oracle(_request(chart, values))
    actual = Engine().render(
        chart,
        values,
        release=Release(name="demo", namespace="testing"),
        capabilities=Capabilities.default(),
    )

    assert expected == {"output": actual}


def test_helm_default_capability_objects_match_the_pinned_engine() -> None:
    chart = Chart(
        name="capabilities",
        version="1.0.0",
        templates={
            "templates/result.txt": (
                "{{.Capabilities.KubeVersion.Version}}|"
                "{{.Capabilities.KubeVersion.GitVersion}}|"
                "{{.Capabilities.KubeVersion}}|"
                '{{.Capabilities.APIVersions.Has "apps/v1"}}|'
                '{{.Capabilities.APIVersions.Has "apiextensions.k8s.io/v1"}}|'
                "{{len .Capabilities.APIVersions}}|"
                "{{.Capabilities.HelmVersion.Version}}|"
                "{{.Capabilities.HelmVersion.KubeClientVersion}}|"
                "{{.Capabilities.HelmVersion.GoVersion}}|"
                "{{range .Capabilities.APIVersions}}{{.}},{{end}}"
            )
        },
    )
    expected = _run_oracle(_request(chart, {}))
    actual = Engine().render(chart, capabilities=Capabilities.default())

    assert expected == {"output": actual}


def test_helm_serialization_and_decoding_functions_match_the_pinned_engine() -> None:
    chart = Chart(
        name="functions",
        version="1.0.0",
        templates={
            "templates/result.txt": (
                '{{printf "%q" (toYaml .Values.mapping)}}|'
                '{{printf "%q" (toYaml .Values.nested)}}|'
                '{{printf "%q" (toYaml .Values.ambiguousStrings)}}|'
                '{{printf "%q" (toYaml .Values.multiline)}}|'
                '{{printf "%q" (toYamlPretty .Values.sequence)}}|'
                '{{printf "%q" (toToml .Values.mapping)}}|'
                '{{printf "%q" (toToml .Values.nestedToml)}}|'
                "{{fromToml .Values.toml}}|"
                "{{fromYaml .Values.yaml}}|"
                '{{kindOf (get (fromYaml .Values.yamlDate) "date")}}|'
                "{{fromYamlArray .Values.yamlArray}}|"
                "{{fromJson .Values.json}}|"
                "{{fromJsonArray .Values.jsonArray}}|"
                '{{lookup "v1" "Namespace" "" "missing"}}'
            )
        },
    )
    values: dict[str, object] = {
        "mapping": {"foo": "bar"},
        "nested": {"outer": {"inner": "value", "items": [1]}},
        "ambiguousStrings": {
            "false": "false",
            "null": "null",
            "on": "on",
            "true": "true",
            "yes": "yes",
        },
        "multiline": {"config.yaml": "line1\nline2\n"},
        "sequence": {"items": [1, 2, 3]},
        "nestedToml": {"mast": {"sail": "white"}},
        "toml": 'hello = "world"',
        "yaml": "hello: world",
        "yamlDate": "date: 2024-04-01",
        "yamlArray": "- one\n- 2\n- name: helm\n",
        "json": '{"hello":"world"}',
        "jsonArray": '["one",2,{"name":"helm"}]',
    }
    expected = _run_oracle(_request(chart, values))
    actual = Engine().render(chart, values)

    assert expected == {"output": actual}


def test_helm_parent_definition_wins_for_tpl_include_like_the_pinned_engine() -> None:
    child = Chart(
        name="child",
        version="1.0.0",
        templates={
            "templates/_helpers.tpl": '{{define "label"}}child{{end}}',
        },
    )
    chart = Chart(
        name="parent",
        version="1.0.0",
        templates={
            "templates/_helpers.tpl": '{{define "label"}}parent{{end}}',
            "templates/result.txt": '{{tpl "{{include \\"label\\" .}}" .}}',
        },
        dependencies=(child,),
    )
    expected = _run_oracle(_request(chart, {}))
    actual = Engine().render(chart)

    assert expected == {"output": actual}


def test_helm_recursive_include_matches_the_pinned_engine_at_practical_depth() -> None:
    chart = Chart(
        name="recursive",
        version="1.0.0",
        templates={
            "templates/_helpers.tpl": (
                '{{define "count"}}{{.n}}'
                '{{if gt .n 0}}{{include "count" (dict "n" (sub .n 1))}}{{end}}'
                "{{end}}"
            ),
            "templates/result.txt": '{{include "count" (dict "n" 32)}}',
        },
    )
    expected = _run_oracle(_request(chart, {}))
    actual = Engine().render(chart)

    assert expected == {"output": actual}


@pytest.mark.parametrize(
    ("template_source", "values", "meaning"),
    [
        ('{{include "missing" .}}', {}, "missing"),
        ("{{tpl .Values.dynamic .}}", {"dynamic": "{{if"}, "unclosed action"),
    ],
)
def test_helm_include_and_tpl_failures_preserve_pinned_error_meaning(
    template_source: str,
    values: dict[str, object],
    meaning: str,
) -> None:
    chart = Chart(
        name="errors",
        version="1.0.0",
        templates={"templates/result.txt": template_source},
    )
    expected = _run_oracle(_request(chart, values))

    assert meaning in expected["error"]
    with pytest.raises(TemplateExecutionError, match=meaning):
        Engine().render(chart, values)


def test_helm_strict_missing_key_fails_in_both_engines_with_source_context() -> None:
    chart = Chart(
        name="strict",
        version="1.0.0",
        templates={"templates/result.txt": "{{.Values.missing}}"},
    )
    request = _request(chart, {})
    request["strict"] = True
    expected = _run_oracle(request)

    assert "strict/templates/result.txt" in expected["error"]
    assert "missing" in expected["error"]
    with pytest.raises(TemplateExecutionError, match="missing") as captured:
        Engine(strict=True).render(chart)
    assert "strict/templates/result.txt" in str(captured.value)


def test_helm_custom_functions_override_the_base_map_like_the_pinned_engine() -> None:
    def custom_upper(value: object) -> str:
        return "custom:" + str(value)

    chart = Chart(
        name="custom",
        version="1.0.0",
        templates={"templates/result.txt": '{{upper "value"}}'},
    )
    request = _request(chart, {})
    request["custom_profile"] = "override-upper"
    expected = _run_oracle(request)
    actual = Engine(custom_functions={"upper": custom_upper}).render(chart)

    assert expected == {"output": actual}
