from __future__ import annotations

from collections.abc import Callable, Mapping

import pytest

from gotpl import Template
from gotpl.funcs.sprout import Handler, registry
from gotpl.runtime import INVALID, UNTYPED_NIL, FunctionResult

SOURCE = (
    "{{$l := list 1 2 2 0 3}}{{$l | append 4}}|{{$l | prepend 9}}|"
    "{{concat (list 1 2) (list 3 4)}}|{{$l | chunk 2}}|{{$l | uniq}}|"
    "{{$l | compact}}|{{flatten (list 1 (list 2 (list 3)))}}|"
    "{{flattenDepth 1 (list 1 (list 2 (list 3)))}}|{{$l | slice 1 3}}|"
    "{{$l | has 2}}|{{$l | without 2 3}}|{{$l | rest}}|{{$l | initial}}|"
    "{{$l | first}}|{{$l | last}}|{{$l | reverse}}|"
    '{{sortAlpha (list "b" "a")}}|{{splitList "," "a,b"}}|'
    '{{strSlice (list 1 nil "x")}}|{{until -3}}|{{untilStep 5 0 -2}}'
)


def _functions() -> Mapping[str, Callable[..., object]]:
    return Handler(registry("slices")).build()


def _failure(value: object, message: str) -> None:
    assert isinstance(value, FunctionResult)
    assert value.error is not None
    assert message in str(value.error)


def test_slices_registry_matches_sprout_pipeline_and_flatten_behavior() -> None:
    functions = _functions()
    assert Template(SOURCE, functions=functions).render() == (
        "[1 2 2 0 3 4]|[9 1 2 2 0 3]|[1 2 3 4]|[[1 2] [2 0] [3]]|"
        "[1 2 0 3]|[1 2 2 3]|[1 2 3]|[1 2 [3]]|[2 2]|true|[1 0]|"
        "[2 2 0 3]|[1 2 2 0]|1|3|[3 0 2 2 1]|[a b]|[a b]|[1 x]|"
        "[0 -1 -2]|[5 3 1]"
    )


@pytest.mark.parametrize("value", [None, UNTYPED_NIL, INVALID])
def test_slice_operations_report_nil_inputs(value: object) -> None:
    functions = _functions()

    _failure(functions["append"](1, value), "cannot append nil")
    assert functions["has"](1, value) is False
    assert functions["strSlice"](value) == []


def test_slice_operations_report_shape_and_argument_errors() -> None:
    functions = _functions()

    _failure(functions["prepend"](1, "bad"), "cannot prepend on type str")
    _failure(functions["chunk"](1, "bad"), "cannot chunk on type str")
    _failure(functions["chunk"](0, [1]), "chunk size must be positive")
    _failure(functions["uniq"]("bad"), "cannot uniq on type str")
    _failure(functions["compact"]("bad"), "cannot compact on type str")
    _failure(functions["flatten"]("bad"), "cannot flatten on type str")
    _failure(functions["slice"](), "at least one argument")
    _failure(functions["slice"]("bad"), "cannot slice on type str")
    _failure(functions["slice"](object(), [1]), "cannot convert object")
    _failure(functions["slice"](-1, [1]), "start index out of bounds")
    _failure(functions["slice"](2, [1]), "start index out of bounds")
    _failure(functions["slice"](1, 0, [1]), "end index out of bounds")
    _failure(functions["slice"](0, 2, [1]), "end index out of bounds")
    _failure(functions["has"](1, "bad"), "cannot find has on type str")
    _failure(functions["without"](1), "at least two arguments")
    _failure(functions["without"](1, "bad"), "cannot without on type str")
    _failure(functions["rest"]("bad"), "cannot rest on type str")
    _failure(functions["initial"]("bad"), "cannot initial on type str")
    _failure(functions["first"]("bad"), "cannot first on type str")
    _failure(functions["last"]("bad"), "cannot last on type str")
    _failure(functions["reverse"]("bad"), "cannot reverse on type str")


def test_slice_empty_and_scalar_results_match_sprout() -> None:
    functions = _functions()

    assert functions["concat"]([1], "ignored", (2,)) == [1, 2]
    assert functions["slice"]([]) is None
    assert functions["rest"]([]) is None
    assert functions["initial"]([]) is None
    assert functions["first"]([]) is None
    assert functions["last"]([]) is None
    assert functions["reverse"]((1, 2)) == [2, 1]
    assert functions["strSlice"](12) == ["12"]
    assert functions["until"](3) == [0, 1, 2]
    assert functions["untilStep"](0, 5, -1) == []
    assert functions["untilStep"](5, 0, 1) == []


@pytest.mark.parametrize(
    ("index", "expected"),
    [(True, [20]), (1.9, [20]), ("0x1", [20])],
)
def test_slice_indices_accept_sprout_numeric_forms(
    index: object, expected: list[int]
) -> None:
    assert _functions()["slice"](index, 2, [10, 20, 30]) == expected
