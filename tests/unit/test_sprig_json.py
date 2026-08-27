import math
from collections.abc import Callable

import pytest

import gotpl
import gotpl.funcs.sprig as sprig


def function(name: str) -> Callable[..., object]:
    return sprig.generic_func_map()[name]


def test_non_must_json_helpers_swallow_supported_failures() -> None:
    unsupported = {1, 2}
    assert function("fromJson")("invalid") is None
    assert function("toJson")(unsupported) == ""
    assert function("toPrettyJson")(unsupported) == ""


@pytest.mark.parametrize(
    "name", ["mustFromJson", "mustToJson", "mustToPrettyJson", "mustToRawJson"]
)
def test_must_json_helpers_return_explicit_function_errors(name: str) -> None:
    value: object = "invalid" if name == "mustFromJson" else {1, 2}
    result = function(name)(value)
    assert isinstance(result, gotpl.FunctionResult)
    assert result.error is not None


@pytest.mark.parametrize(
    ("name", "value", "expected"),
    [
        ("mustFromJson", '{"a":1}', {"a": 1.0}),
        ("mustToJson", {"a": 1}, '{"a":1}'),
        ("mustToPrettyJson", {"a": 1}, '{\n  "a": 1\n}'),
        ("mustToRawJson", {"a": "<x>"}, '{"a":"<x>"}'),
    ],
)
def test_must_json_helpers_succeed_for_supported_values(
    name: str, value: object, expected: object
) -> None:
    result = function(name)(value)
    assert isinstance(result, gotpl.FunctionResult)
    assert result.error is None
    assert result.value == expected


def test_must_json_helpers_preserve_go_encoding_boundaries() -> None:
    parsed = function("mustFromJson")("9007199254740993")
    compact = function("mustToJson")(b"abc")
    pretty = function("mustToPrettyJson")({"items": []})
    raw = function("mustToRawJson")({"tag": "<x>"})

    assert isinstance(parsed, gotpl.FunctionResult)
    assert parsed.value == 9007199254740992.0
    assert isinstance(compact, gotpl.FunctionResult)
    assert compact.value == '"YWJj"'
    assert isinstance(pretty, gotpl.FunctionResult)
    assert pretty.value == '{\n  "items": []\n}'
    assert isinstance(raw, gotpl.FunctionResult)
    assert raw.value == '{"tag":"<x>"}'


def test_raw_json_propagates_unsupported_values() -> None:
    with pytest.raises(TypeError):
        function("toRawJson")({1, 2})


def test_json_escapes_line_separators_in_both_modes() -> None:
    value = {"line": "a\u2028b\u2029c"}
    expected = r'{"line":"a\u2028b\u2029c"}'
    assert function("toJson")(value) == expected
    assert function("toRawJson")(value) == expected


def test_json_uses_go_float64_decode_and_number_formatting() -> None:
    assert function("fromJson")("9007199254740993") == 9007199254740992.0
    assert function("toJson")(1.0) == "1"
    assert function("toJson")(1e20) == "100000000000000000000"
    assert function("toJson")(1e21) == "1e+21"
    assert function("toJson")(1e-6) == "0.000001"
    assert function("toJson")(1e-7) == "1e-7"
    assert function("toJson")(math.nan) == ""


def test_go_json_collection_edges_and_cycles() -> None:
    assert function("toJson")(None) == "null"
    assert function("toJson")(b"abc") == '"YWJj"'
    assert function("toJson")({}) == "{}"
    assert function("toJson")({2: "b", 1: "a"}) == '{"1":"a","2":"b"}'
    assert function("toJson")({True: "unsupported"}) == ""
    assert function("toPrettyJson")({"items": [1, 2]}) == (
        '{\n  "items": [\n    1,\n    2\n  ]\n}'
    )

    cyclic_list: list[object] = []
    cyclic_list.append(cyclic_list)
    cyclic_dict: dict[str, object] = {}
    cyclic_dict["self"] = cyclic_dict
    assert function("toJson")(cyclic_list) == ""
    assert function("toJson")(cyclic_dict) == ""
    with pytest.raises(ValueError, match="cycle"):
        function("toRawJson")(cyclic_list)

    for name in ("mustToJson", "mustToPrettyJson", "mustToRawJson"):
        result = function(name)(cyclic_dict)
        assert isinstance(result, gotpl.FunctionResult)
        assert isinstance(result.error, ValueError)


def test_from_json_rejects_nonstandard_constants() -> None:
    assert function("fromJson")("NaN") is None
