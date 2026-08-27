from __future__ import annotations

import sys

import pytest

from gotpl import Template, TemplateExecutionError
from gotpl.funcs.sprout import Handler, MissingOptionalDependencyError, registry


def test_encoding_registry_matches_base_and_json_oracle_results() -> None:
    functions = Handler(registry("encoding")).build()
    source = (
        '{{base64Encode "Hello World"}}|'
        '{{base64Decode "SGVsbG8gV29ybGQ="}}|'
        '{{base32Encode "Hello World"}}|'
        '{{base32Decode "JBSWY3DPEBLW64TMMQ======"}}|'
        "{{toJSON .}}|{{toPrettyJSON .}}|{{toRawJSON .}}"
    )

    assert Template(source, functions=functions).render({"foo": 55, "html": "<b>"}) == (
        "SGVsbG8gV29ybGQ=|Hello World|JBSWY3DPEBLW64TMMQ======|Hello World|"
        '{"foo":55,"html":"\\u003cb\\u003e"}|'
        '{\n  "foo": 55,\n  "html": "\\u003cb\\u003e"\n}|'
        '{"foo":55,"html":"<b>"}'
    )


def test_encoding_failures_stop_template_execution_with_capability_context() -> None:
    functions = Handler(registry("encoding")).build()
    template = Template(
        'prefix{{base64Decode "bad"}}suffix',
        name="encoding-error",
        functions=functions,
    )

    with pytest.raises(TemplateExecutionError, match="base64 decode error"):
        template.render()


def test_yaml_functions_explain_the_missing_extra(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(sys.modules, "yaml", None)
    functions = Handler(registry("encoding")).build()

    with pytest.raises(
        TemplateExecutionError,
        match=r"gotpl\[yaml\]",
    ) as captured:
        Template('{{fromYAML "answer: 42"}}', functions=functions).render()
    assert isinstance(captured.value.__cause__, MissingOptionalDependencyError)


def test_yaml_extra_matches_sprout_mapping_and_indentation() -> None:
    pytest.importorskip("yaml")
    functions = Handler(registry("encoding")).build()

    assert (
        Template("{{fromYAML .}}", functions=functions).render(
            "foo: 55\nbar:\n  baz: 1\n"
        )
        == "map[bar:map[baz:1] foo:55]"
    )
    assert (
        Template("{{toYAML .}}", functions=functions).render({"foo": 55, "bar": "baz"})
        == "bar: baz\nfoo: 55"
    )
    assert (
        Template("{{toIndentYAML 8 .}}", functions=functions).render(
            {"foo": {"baz": "bar", "bar": "baz"}, "bar": "baz"}
        )
        == "bar: baz\nfoo:\n        bar: baz\n        baz: bar"
    )
