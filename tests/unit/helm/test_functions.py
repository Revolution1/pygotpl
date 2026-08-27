from __future__ import annotations

from collections.abc import Callable
from types import ModuleType
from typing import cast

import pytest
from yaml.error import YAMLError

import gotpl.funcs.helm as helm
import gotpl.funcs.helm.functions as helm_functions


def _late_function(*_arguments: object) -> str:
    return "late"


def test_helm_package_exports_only_reusable_function_support() -> None:
    assert helm.__all__ == ["MissingOptionalDependencyError", "function_map"]
    assert not hasattr(helm, "Engine")
    assert not hasattr(helm, "Chart")
    assert not hasattr(helm, "load_chart")


def test_helm_function_map_is_application_bindable_and_does_not_expose_env() -> None:
    functions = helm.function_map(
        include=_late_function,
        tpl=_late_function,
        required=_late_function,
        fail=_late_function,
    )

    expected: dict[str, Callable[..., object]] = {
        "include": _late_function,
        "tpl": _late_function,
        "required": _late_function,
        "fail": _late_function,
    }
    assert {name: functions[name] for name in expected} == expected
    assert "env" not in functions
    assert "expandenv" not in functions
    assert functions["getHostByName"]("example.invalid") == ""
    assert len(functions) == 222
    assert {
        "fromJsonArray",
        "fromToml",
        "fromYaml",
        "fromYamlArray",
        "include",
        "lookup",
        "mustToToml",
        "mustToYaml",
        "required",
        "toToml",
        "toYaml",
        "toYamlPretty",
        "tpl",
    }.issubset(functions)


@pytest.mark.parametrize(
    ("name", "argument"),
    [
        ("toYaml", {}),
        ("mustToYaml", {}),
        ("fromYaml", "{}"),
        ("fromYamlArray", "[]"),
    ],
)
def test_yaml_functions_report_the_missing_helm_extra(
    monkeypatch: pytest.MonkeyPatch,
    name: str,
    argument: object,
) -> None:
    real_import = helm_functions.importlib.import_module

    def import_without_yaml(module_name: str) -> ModuleType:
        if module_name == "yaml":
            raise ImportError("yaml intentionally unavailable")
        return real_import(module_name)

    monkeypatch.setattr(helm_functions.importlib, "import_module", import_without_yaml)
    functions = helm.function_map(
        include=_late_function,
        tpl=_late_function,
        required=_late_function,
        fail=_late_function,
    )

    with pytest.raises(
        helm.MissingOptionalDependencyError,
        match=r'pip install "gotpl\[helm\]"',
    ):
        functions[name](argument)


@pytest.mark.parametrize("name", ["toToml", "mustToToml"])
def test_toml_writers_report_the_missing_helm_extra(
    monkeypatch: pytest.MonkeyPatch,
    name: str,
) -> None:
    real_import = helm_functions.importlib.import_module

    def import_without_writer(module_name: str) -> ModuleType:
        if module_name == "tomli_w":
            raise ImportError("tomli-w intentionally unavailable")
        return real_import(module_name)

    monkeypatch.setattr(
        helm_functions.importlib, "import_module", import_without_writer
    )
    functions = helm.function_map(
        include=_late_function,
        tpl=_late_function,
        required=_late_function,
        fail=_late_function,
    )

    with pytest.raises(
        helm.MissingOptionalDependencyError,
        match=r'pip install "gotpl\[helm\]"',
    ):
        functions[name]({"key": "value"})


def test_helm_serializers_preserve_tolerant_and_must_error_contracts() -> None:
    functions = helm.function_map(
        include=_late_function,
        tpl=_late_function,
        required=_late_function,
        fail=_late_function,
    )
    unsupported = object()

    assert functions["toYaml"](unsupported) == ""
    with pytest.raises(YAMLError, match="cannot represent an object"):
        functions["mustToYaml"](unsupported)

    yaml_error = functions["fromYaml"](": invalid: yaml:")
    assert isinstance(yaml_error, dict)
    assert "Error" in yaml_error
    yaml_array_error = functions["fromYamlArray"](": invalid: yaml:")
    assert isinstance(yaml_array_error, list)
    assert len(cast(list[object], yaml_array_error)) == 1

    toml_error = functions["toToml"]([])
    assert isinstance(toml_error, str)
    assert "TOML root must be a mapping" in toml_error
    with pytest.raises(TypeError, match="TOML root must be a mapping"):
        functions["mustToToml"]([])

    toml_decode_error = functions["fromToml"]("not = [valid")
    assert isinstance(toml_decode_error, dict)
    assert "Error" in cast(dict[object, object], toml_decode_error)
    assert functions["fromJson"]("[]") == {}
    json_error = functions["fromJson"]("{")
    assert isinstance(json_error, dict)
    assert "Error" in cast(dict[object, object], json_error)
    assert functions["fromJsonArray"]("{}") == []
    json_array_error = functions["fromJsonArray"]("[")
    assert isinstance(json_array_error, list)
    assert len(cast(list[object], json_array_error)) == 1


def test_helm_yaml_decoders_ignore_valid_values_of_the_wrong_shape() -> None:
    functions = helm.function_map(
        include=_late_function,
        tpl=_late_function,
        required=_late_function,
        fail=_late_function,
    )

    assert functions["fromYaml"]("- one\n- two") == {}
    assert functions["fromYamlArray"]("key: value") == []


@pytest.mark.parametrize(
    ("header", "depth"),
    [
        ("[root]", 1),
        ("[[root.child]]", 2),
        ('[root."literal.dot"]', 2),
        ('[root."escaped\\".dot"]', 2),
        ("[root.'literal.dot']", 2),
    ],
)
def test_toml_table_depth_ignores_quoted_dots(header: str, depth: int) -> None:
    assert (
        helm_functions._toml_table_depth(header)  # pyright: ignore[reportPrivateUsage]
        == depth
    )


def test_toml_indentation_covers_root_text_and_nested_tables() -> None:
    source = 'title = "demo"\n[root]\nvalue = 1\n[root.child]\nitem = 2\n\n'
    assert helm_functions._indent_toml_tables(  # pyright: ignore[reportPrivateUsage]
        source
    ) == ('title = "demo"\n[root]\n  value = 1\n  [root.child]\n    item = 2\n\n')


def test_function_map_accepts_lookup_dns_and_custom_overrides() -> None:
    def lookup(_api: str, _kind: str, _namespace: str, _name: str) -> str:
        return "found"

    def custom_quote(value: object) -> str:
        return f"custom:{value}"

    functions = helm.function_map(
        include=_late_function,
        tpl=_late_function,
        required=_late_function,
        fail=_late_function,
        lookup=lookup,
        enable_dns=True,
        custom={"quote": custom_quote},
    )

    assert functions["lookup"]("v1", "Kind", "ns", "name") == "found"
    assert functions["quote"]("value") == "custom:value"
    assert functions["getHostByName"] is not None
