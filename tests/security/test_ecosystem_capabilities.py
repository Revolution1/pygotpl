from __future__ import annotations

import builtins
import socket
from collections.abc import Callable

import pytest

from gotpl import Template, TemplateEngine, TemplateSyntaxError
from gotpl.funcs.helm import function_map
from gotpl.funcs.sprig import text_func_map
from gotpl.funcs.sprout import Handler, group, registry


def _late(*_arguments: object) -> str:
    return ""


def _helm_functions(
    *,
    lookup: Callable[[str, str, str, str], object] | None = None,
    enable_dns: bool = False,
) -> dict[str, Callable[..., object]]:
    return function_map(
        include=_late,
        tpl=_late,
        required=_late,
        fail=_late,
        lookup=lookup,
        enable_dns=enable_dns,
    )


def test_core_multi_source_engine_adds_no_ecosystem_capabilities() -> None:
    engine = TemplateEngine.from_sources({"main.txt": "{{.}}"})

    assert engine.template.functions == {}
    assert engine.render({"main.txt": "safe"}) == {"main.txt": "safe"}


def test_sprout_and_helm_names_do_not_leak_into_core_or_sprig() -> None:
    sprig_names = set(text_func_map())

    ecosystem_names = {"cidrRangeList", "include", "tpl", "toYamlPretty", "uuidv7"}
    assert not ecosystem_names.intersection(sprig_names)
    with pytest.raises(TemplateSyntaxError, match=r"function .* not defined"):
        Template('{{include "missing" .}}')


def test_sprout_groups_make_non_hermetic_capabilities_explicit() -> None:
    all_names = set(group("all").function_names)
    hermetic_names = set(group("hermetic").function_names)

    assert {
        "env",
        "expandEnv",
        "randBytes",
        "randInt",
        "parseIP",
        "cidrRangeList",
    }.issubset(all_names)
    assert not {
        "env",
        "expandEnv",
        "randBytes",
        "randInt",
        "parseIP",
        "cidrRangeList",
    }.intersection(hermetic_names)
    assert "pathClean" in all_names & hermetic_names
    assert "genPrivateKey" not in all_names | hermetic_names


def test_sprout_filesystem_registry_is_path_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def denied_open(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("path helpers must not open files")

    monkeypatch.setattr(builtins, "open", denied_open)
    functions = Handler(registry("filesystem")).build()

    assert (
        Template(
            '{{pathClean "a/../b"}}|{{osBase "a/b.txt"}}', functions=functions
        ).render()
        == "b|b.txt"
    )


def test_helm_functions_disable_ambient_process_and_network_access(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def denied_dns(_name: str) -> str:
        raise AssertionError("disabled DNS must not call the resolver")

    monkeypatch.setattr(socket, "gethostbyname", denied_dns)
    functions = _helm_functions()

    assert "env" not in functions
    assert "expandenv" not in functions
    assert functions["getHostByName"]("example.invalid") == ""
    assert functions["lookup"]("v1", "Pod", "default", "missing") == {}


def test_helm_lookup_requires_an_explicit_application_adapter() -> None:
    calls: list[tuple[str, str, str, str]] = []

    def lookup(api: str, kind: str, namespace: str, name: str) -> object:
        calls.append((api, kind, namespace, name))
        return {"metadata": {"name": name}}

    functions = _helm_functions(lookup=lookup)

    assert functions["lookup"]("v1", "Pod", "testing", "demo") == {
        "metadata": {"name": "demo"}
    }
    assert calls == [("v1", "Pod", "testing", "demo")]
