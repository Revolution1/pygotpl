from collections.abc import Callable
from typing import cast

import pytest

import gotpl
import gotpl.funcs.sprig as sprig


def function(name: str) -> Callable[..., object]:
    return sprig.generic_func_map()[name]


def test_dict_stringifies_keys_and_supplies_an_odd_value() -> None:
    assert function("dict")(1, "one", "missing") == {
        "1": "one",
        "missing": "",
    }
    assert function("dict")(b"bytes", 1, bytearray(b"mutable"), 2) == {
        "bytes": 1,
        "mutable": 2,
    }


def test_keys_and_values_accept_mutable_python_dictionaries() -> None:
    value = {"a": 1, "b": 2}
    assert function("keys")(value) == ["a", "b"]
    assert function("values")(value) == [1, 2]
    assert function("keys")() == []
    assert function("keys")({"a": 1}, {"a": 2, "b": 3}) == ["a", "a", "b"]
    assert function("values")({}) == []


def test_dictionary_selection_preserves_present_nil_and_nested_aliases() -> None:
    nested = {"x": 1}
    source: dict[str, object] = {"nil": None, "nested": nested}

    assert function("get")(source, "missing") == ""
    assert function("get")(source, "nil") is None
    assert function("pluck")("nil", source, {}) == [None]
    picked = cast(dict[str, object], function("pick")(source, "missing", "nested"))
    omitted = cast(dict[str, object], function("omit")(source, "missing"))
    assert picked["nested"] is nested
    assert omitted["nested"] is nested


def test_set_and_unset_mutate_and_return_the_original_dictionary() -> None:
    value = {"a": 1}

    assert function("set")(value, "b", 2) is value
    assert value == {"a": 1, "b": 2}
    assert function("unset")(value, "missing") is value
    assert function("unset")(value, "a") is value
    assert function("hasKey")(value, "a") is False


def test_deep_copy_does_not_share_nested_collections() -> None:
    original = {"items": [1]}
    result = function("mustDeepCopy")(original)
    assert isinstance(result, gotpl.FunctionResult)
    assert result.error is None
    copied = result.value
    assert copied == original
    assert copied is not original
    assert isinstance(copied, dict)
    cast(list[int], copied["items"]).append(2)
    assert original == {"items": [1]}


def test_deep_copy_must_and_non_must_failure_contracts() -> None:
    class Uncopyable:
        def __deepcopy__(self, memo: dict[int, object]) -> object:
            raise ValueError("cannot copy")

    with pytest.raises(RuntimeError, match="deepCopy error: cannot copy"):
        function("deepCopy")(Uncopyable())
    result = function("mustDeepCopy")(Uncopyable())
    assert isinstance(result, gotpl.FunctionResult)
    assert isinstance(result.error, ValueError)


def test_merge_must_and_non_must_failure_contracts() -> None:
    class BrokenDict(dict[str, object]):
        def items(self):  # type: ignore[override]
            raise ValueError("cannot iterate mapping")

    broken = BrokenDict()
    assert function("merge")({}, broken) == ""
    assert function("mergeOverwrite")({}, broken) == ""
    for name in ("mustMerge", "mustMergeOverwrite"):
        result = function(name)({}, broken)
        assert isinstance(result, gotpl.FunctionResult)
        assert isinstance(result.error, ValueError)


@pytest.mark.parametrize("name", ["mustMerge", "mustMergeOverwrite"])
def test_must_merge_variants_return_successful_function_results(name: str) -> None:
    destination: dict[str, object] = {"a": 1}
    result = function(name)(destination, {"b": 2})

    assert isinstance(result, gotpl.FunctionResult)
    assert result.error is None
    assert result.value is destination


def test_dig_returns_an_explicit_go_style_result() -> None:
    result = function("dig")("outer", "inner", "fallback", {"outer": {}})

    assert isinstance(result, gotpl.FunctionResult)
    assert result.error is None
    assert result.value == "fallback"


@pytest.mark.parametrize(
    "arguments",
    [
        ("only", "fallback"),
        (1, "fallback", {}),
        ("key", "fallback", []),
        ("outer", "inner", "fallback", {"outer": 1}),
    ],
)
def test_dig_rejects_invalid_shapes(arguments: tuple[object, ...]) -> None:
    with pytest.raises((TypeError, IndexError)):
        function("dig")(*arguments)


def test_merge_fills_zero_values_but_overwrite_accepts_zero_sources() -> None:
    zero_values: dict[str, object] = {"n": 0, "s": "", "b": False, "l": []}
    filled_values: dict[str, object] = {"n": 1, "s": "x", "b": True, "l": [2]}

    assert function("merge")(zero_values.copy(), filled_values) == filled_values
    assert function("mergeOverwrite")(filled_values.copy(), zero_values) == zero_values
