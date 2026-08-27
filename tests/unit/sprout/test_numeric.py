from __future__ import annotations

import math
from collections.abc import Callable, Mapping

import pytest

from gotpl import Template, TemplateExecutionError
from gotpl.funcs.sprout import Handler, registry
from gotpl.runtime import FunctionResult

_SOURCE = (
    "{{add 1 2 3}}|{{add 1.5 2 3}}|{{addf 0.1 0.2}}|{{add1 4}}|"
    "{{sub 10 2 3}}|{{mul 2 3 4}}|{{mulf 1.5 2}}|{{div 20 3}}|"
    "{{divf 20 4}}|{{mod 7 4}}|{{min 3 1 2}}|{{minf 3.5 1.2 2.1}}|"
    "{{max 3 8 2}}|{{maxf 3.5 8.2 2.1}}|{{floor 3.9}}|{{ceil 3.1}}|"
    "{{round 3.14159 3}}"
)


def _functions() -> Mapping[str, Callable[..., object]]:
    return Handler(registry("numeric")).build()


def _failure(value: object, message: str) -> None:
    assert isinstance(value, FunctionResult)
    assert value.error is not None
    assert message in str(value.error)


def test_numeric_registry_matches_sprout_type_and_precision_behavior() -> None:
    functions = _functions()
    assert Template(_SOURCE, functions=functions).render() == (
        "6|6.5|0.3|5|5|24|3|6|5|3|1|1.2|8|8.2|3|4|3.142"
    )


def test_numeric_registry_rejects_zero_division() -> None:
    functions = _functions()
    with pytest.raises(TemplateExecutionError, match="cannot divide by zero"):
        Template("{{div 1 0}}", functions=functions).render()


def test_numeric_empty_and_first_operand_type_rules() -> None:
    functions = _functions()

    assert functions["add"]() == 0.0
    assert functions["sub"]() == 0.0
    assert functions["mul"]() == 1
    assert functions["mulf"]() == 1.0
    assert functions["div"]() == 0
    assert functions["divf"]() == 0.0
    assert functions["add"](True, 1) is True
    assert functions["add"](2, 0.75) == 2
    assert functions["add"](2.0, 0.75) == 2.75
    assert functions["add1"](2.5) == 3.5
    assert functions["add1"](2) == 3


def test_numeric_string_byte_and_rounding_inputs() -> None:
    functions = _functions()

    assert functions["floor"](b"3.9") == 3.0
    assert functions["ceil"](bytearray(b"3.1")) == 4.0
    assert functions["round"](1.24, 1, 0.3) == 1.3
    assert functions["round"](1.25, 1) == 1.3
    assert functions["min"]("3", 2.9, True) == 1
    assert functions["minf"]("3.5", 2) == 2.0
    assert functions["max"]("3", 2.9, True) == 3
    assert functions["maxf"]("3.5", 2) == 3.5


def test_numeric_float_division_preserves_ieee_special_values() -> None:
    functions = _functions()

    not_a_number = functions["divf"](0, 0)
    assert isinstance(not_a_number, float)
    assert math.isnan(not_a_number)
    assert functions["divf"](1, 0) == math.inf
    assert functions["divf"](-1, 0) == -math.inf


@pytest.mark.parametrize(
    ("name", "arguments", "message"),
    [
        ("add", ("1", 2), "cannot convert numeric result to str"),
        ("floor", (object(),), "unable to cast object"),
        ("ceil", (object(),), "unable to cast object"),
        ("round", (object(), 2), "unable to cast object"),
        ("mul", (object(), 2), "unable to cast object"),
        ("div", (1, "bad"), "could not convert string"),
        ("div", (object(), 1), "unable to cast object"),
        ("divf", (1, object()), "unable to cast object"),
        ("mod", (1, 0), "math domain error"),
        ("min", (object(),), "unable to cast object"),
        ("minf", (object(),), "unable to cast object"),
        ("max", (object(),), "unable to cast object"),
        ("maxf", (object(),), "unable to cast object"),
    ],
)
def test_numeric_conversion_failures_are_explicit(
    name: str, arguments: tuple[object, ...], message: str
) -> None:
    _failure(_functions()[name](*arguments), message)
