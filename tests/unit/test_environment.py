from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

import pytest

from gotpl import Environment, HTMLTemplate, PythonExtensions, Template, TemplateEngine


@dataclass(frozen=True)
class _PrefixExtension:
    functions: dict[str, Callable[..., object]]
    template_kinds: frozenset[Literal["text", "html"]] = frozenset({"text", "html"})


def test_environment_builds_text_and_html_templates() -> None:
    def decorate(value: object) -> str:
        return f"<{value}>"

    environment = Environment(functions={"decorate": decorate})

    text = environment.from_string("{{decorate .}}")
    html = environment.from_html_string("<p>{{.}}</p>")

    assert isinstance(text, Template)
    assert text.render("value") == "<value>"
    assert isinstance(html, HTMLTemplate)
    assert html.render("<value>") == "<p>&lt;value&gt;</p>"


def test_environment_builds_complete_text_and_html_associations() -> None:
    environment = Environment()
    sources = {
        "helpers.tpl": '{{define "label"}}<b>{{.}}</b>{{end}}',
        "main.tpl": '{{template "label" .}}',
    }

    text = environment.from_sources(sources)
    html = environment.from_html_sources(sources)

    assert isinstance(text, TemplateEngine)
    assert text.render_template("main.tpl", "value") == "<b>value</b>"
    assert isinstance(html, HTMLTemplate)
    assert html.render_template("main.tpl", "<value>") == "<b>&lt;value&gt;</b>"


def test_environment_derivation_rejects_accidental_replacement() -> None:
    parent = Environment(functions={"decorate": str})

    with pytest.raises(ValueError, match="already registered"):
        parent.with_functions({"decorate": repr})

    child = parent.with_functions({"decorate": repr}, replace=True)

    assert parent.from_string("{{decorate .}}", name="parent").render("x") == "x"
    assert child.from_string("{{decorate .}}", name="child").render("x") == "'x'"


def test_environment_exposes_read_only_configuration() -> None:
    functions: dict[str, Callable[..., object]] = {"identity": str}
    environment = Environment(functions=functions)
    functions["later"] = repr

    assert set(environment.functions) == {"identity"}
    with pytest.raises(TypeError):
        environment.functions["later"] = repr  # type: ignore[index]


def test_environment_composes_explicit_runtime_extensions() -> None:
    def prefix(value: object) -> str:
        return f"prefix:{value}"

    extension = _PrefixExtension({"prefix": prefix})

    environment = Environment().with_extensions(extension)

    assert environment.from_string("{{prefix .}}").render("value") == "prefix:value"
    assert environment.extensions == (extension,)


def test_environment_rejects_extension_function_collisions() -> None:
    extension = _PrefixExtension({"identity": str})

    with pytest.raises(ValueError, match="runtime extension function collision"):
        Environment(functions={"identity": repr}, extensions=(extension,))


@pytest.mark.parametrize(
    ("options", "message"),
    [
        ({"delimiters": ("", "}}")}, "delimiters"),
        ({"missing_key": "invalid"}, "missing_key"),
        ({"format_mode": "invalid"}, "format_mode"),
    ],
)
def test_environment_validates_configuration_immediately(
    options: dict[str, object], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        Environment(**options)  # type: ignore[arg-type]


def test_environment_rejects_python_extension_collisions_immediately() -> None:
    with pytest.raises(ValueError, match="extension function collision"):
        Environment(
            functions={"reMatch": str},
            python_extensions=PythonExtensions(re_match=True),
        )


def test_environment_accepts_python_extension_profiles_and_categories() -> None:
    common = Environment(python_extensions="common")
    selected = Environment(python_extensions=("hashing", "encoding"))

    assert common.from_string('{{sha256 "hello"}}').render() == (
        "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"
    )
    assert (
        selected.from_string(
            '{{b64encode (utf8Encode "hello")}}|{{sha1 "hello"}}'
        ).render()
        == "aGVsbG8=|aaf4c61ddcc5e8a2dabede0f3b482cd9aea9434d"
    )


def test_environment_all_python_extensions_profile_includes_regex() -> None:
    environment = Environment(python_extensions="all")

    assert environment.from_string('{{reMatch "ell" "hello"}}').render() == "true"


def test_pythonic_environment_keeps_template_syntax_and_uses_python_values() -> None:
    def type_name(value: object) -> str:
        return type(value).__name__

    environment = Environment.pythonic(
        "all",
        functions={"typeName": type_name},
    )
    template = environment.from_string(
        '{{pyPrint .items}}|{{typeName .items}}|{{reMatch "ell" .name}}'
    )

    assert template.render({"items": [1, 2], "name": "hello"}) == "[1, 2]|list|True"
    assert template.format_mode == "python"


def test_environment_does_not_replace_runtime_extension_functions() -> None:
    extension = _PrefixExtension({"identity": str})
    environment = Environment(extensions=(extension,))

    with pytest.raises(ValueError, match="cannot be replaced"):
        environment.with_functions({"identity": repr}, replace=True)
