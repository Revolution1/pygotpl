from collections.abc import Callable

import pytest

import gotpl
import gotpl.funcs.sprig as sprig


def function(name: str) -> Callable[..., object]:
    return sprig.generic_func_map()[name]


def test_list_helpers_cover_empty_and_nil_inputs() -> None:
    assert function("has")("item", None) is False
    assert function("slice")([]) == []
    assert function("first")([]) is None
    assert function("rest")([]) == []


@pytest.mark.parametrize(
    ("name", "arguments", "message"),
    [
        ("mustAppend", (1, 2), "Cannot push on type int"),
        ("mustPush", (1, 2), "Cannot push on type int"),
        ("mustPrepend", (1, 2), "Cannot prepend on type int"),
        ("mustFirst", (1,), "Cannot find first on type int"),
        ("mustLast", (1,), "Cannot find last on type int"),
        ("mustRest", (1,), "Cannot find rest on type int"),
        ("mustInitial", (1,), "Cannot find initial on type int"),
        ("mustReverse", (1,), "Cannot find reverse on type int"),
        ("mustCompact", (1,), "Cannot compact on type int"),
        ("mustUniq", (1,), "Cannot find uniq on type int"),
        ("mustWithout", (1,), "Cannot find without on type int"),
        ("mustHas", ("needle", 1), "Cannot find has on type int"),
        ("mustSlice", (1.5,), "list should be type of slice or array but float64"),
        ("mustChunk", (2, 1), "Cannot chunk type int"),
    ],
)
def test_must_list_helpers_return_errors_for_non_sequences(
    name: str, arguments: tuple[object, ...], message: str
) -> None:
    result = function(name)(*arguments)
    assert isinstance(result, gotpl.FunctionResult)
    assert isinstance(result.error, TypeError)
    assert message in str(result.error)


def test_non_must_concat_rejects_non_sequences() -> None:
    with pytest.raises(TypeError, match="Cannot concat type int as list"):
        function("concat")([1], 2)


@pytest.mark.parametrize("indices", [(-1,), (0, 4), (2, 1), (0, 1, 2)])
def test_list_slice_rejects_invalid_bounds(indices: tuple[int, ...]) -> None:
    with pytest.raises(IndexError, match="bounds"):
        function("mustSlice")([1, 2, 3], *indices)


def test_chunk_rejects_nonpositive_sizes() -> None:
    with pytest.raises(ValueError, match="positive"):
        function("mustChunk")(0, [1])


@pytest.mark.parametrize(
    ("name", "arguments"),
    [
        ("mustAppend", (None, 1)),
        ("mustPush", (None, 1)),
        ("mustPrepend", (None, 1)),
        ("mustFirst", (None,)),
        ("mustLast", (None,)),
        ("mustRest", (None,)),
        ("mustInitial", (None,)),
        ("mustReverse", (None,)),
        ("mustCompact", (None,)),
        ("mustUniq", (None,)),
        ("mustWithout", (None,)),
        ("mustSlice", (None,)),
        ("mustChunk", (1, None)),
    ],
)
def test_must_list_helpers_preserve_upstream_nil_reflection_panics(
    name: str, arguments: tuple[object, ...]
) -> None:
    with pytest.raises(
        RuntimeError, match="invalid memory address or nil pointer dereference"
    ):
        function(name)(*arguments)


def test_must_has_treats_nil_as_an_explicit_success() -> None:
    result = function("mustHas")("needle", None)
    assert result == gotpl.FunctionResult.success(False)


@pytest.mark.parametrize(
    ("name", "arguments"),
    [
        ("append", (1, 2)),
        ("push", (1, 2)),
        ("prepend", (1, 2)),
        ("first", (1,)),
        ("last", (1,)),
        ("rest", (1,)),
        ("initial", (1,)),
        ("reverse", (1,)),
        ("compact", (1,)),
        ("uniq", (1,)),
        ("without", (1,)),
        ("has", ("needle", 1)),
        ("slice", (1,)),
        ("chunk", (2, 1)),
    ],
)
def test_non_must_list_functions_panic_for_non_sequences(
    name: str, arguments: tuple[object, ...]
) -> None:
    with pytest.raises(TypeError):
        function(name)(*arguments)


def test_deep_list_equality_preserves_go_type_identity() -> None:
    values = [[1], [1], {"a": [2]}, {"a": [2]}, 1, True]
    unique = function("mustUniq")(values)
    contains = function("mustHas")({"a": [2]}, values)
    filtered = function("mustWithout")(values, [1], {"a": [2]})
    assert isinstance(unique, gotpl.FunctionResult)
    assert unique.value == [[1], {"a": [2]}, 1, True]
    assert isinstance(contains, gotpl.FunctionResult)
    assert contains.value is True
    assert isinstance(filtered, gotpl.FunctionResult)
    assert filtered.value == [1, True]


def test_list_transforms_do_not_mutate_inputs_or_copy_nested_values() -> None:
    nested: list[object] = ["shared"]
    original = [nested, 2]
    appended = function("append")(original, 3)
    prepended = function("prepend")(original, 0)
    reversed_values = function("reverse")(original)

    assert original == [["shared"], 2]
    assert appended == [["shared"], 2, 3]
    assert prepended == [0, ["shared"], 2]
    assert reversed_values == [2, ["shared"]]
    assert isinstance(appended, list)
    assert isinstance(prepended, list)
    assert isinstance(reversed_values, list)
    assert appended[0] is nested
    assert prepended[1] is nested
    assert reversed_values[1] is nested


def test_nil_and_allocated_empty_slices_remain_observably_distinct() -> None:
    empty = function("list")()
    nil_rest = function("rest")([])

    assert function("toJson")(empty) == "[]"
    assert function("toJson")(nil_rest) == "null"
    assert function("deepEqual")(empty, nil_rest) is False
    assert function("toJson")(function("rest")([1])) == "[]"
    assert function("toJson")(function("initial")([1])) == "[]"
    assert function("toJson")(function("slice")([1], 0, 0)) == "[]"
    assert function("toJson")(function("concat")([None])) == "[null]"


def test_list_operations_accept_python_byte_slices_as_go_uint8_slices() -> None:
    assert function("append")(b"AB", 67) == [65, 66, 67]
    assert function("prepend")(bytearray(b"BC"), 65) == [65, 66, 67]
    assert function("slice")(b"ABC", 1) == [66, 67]
    assert function("chunk")(2, b"ABC") == [[65, 66], [67]]


def test_deep_list_operations_terminate_for_recursive_collections() -> None:
    left: list[object] = []
    right: list[object] = []
    left.append(left)
    right.append(right)

    assert function("has")(right, [left]) is True
    assert function("uniq")([left, right]) == [left]
    assert function("without")([left], right) == []


def test_string_conversion_handles_bytes_nil_and_scalars() -> None:
    assert function("toString")(b"value") == "value"
    assert function("toStrings")(None) == []
    assert function("toStrings")(7) == ["7"]
    assert function("toStrings")([1, None, 2]) == ["1", "2"]


def test_must_variants_are_explicit_go_style_result_functions() -> None:
    functions = sprig.generic_func_map()
    aliases = {
        "mustAppend": "append",
        "mustPush": "push",
        "mustPrepend": "prepend",
        "mustFirst": "first",
        "mustLast": "last",
        "mustRest": "rest",
        "mustInitial": "initial",
        "mustReverse": "reverse",
        "mustCompact": "compact",
        "mustUniq": "uniq",
        "mustWithout": "without",
        "mustHas": "has",
        "mustSlice": "slice",
        "mustChunk": "chunk",
    }
    assert all(
        functions[must] is not functions[plain] for must, plain in aliases.items()
    )
    for name in aliases:
        arguments: tuple[object, ...] = ([1, 2],)
        if name in {"mustAppend", "mustPush", "mustPrepend"}:
            arguments = ([1, 2], 3)
        elif name == "mustWithout":
            arguments = ([1, 2], 2)
        elif name in {"mustHas", "mustChunk"}:
            arguments = (1, [1, 2])
        result = functions[name](*arguments)
        assert isinstance(result, gotpl.FunctionResult)
        assert result.error is None
