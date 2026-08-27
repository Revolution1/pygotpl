import math
from collections.abc import Callable
from typing import cast

import pytest

import gotpl.funcs.sprig as sprig


def function(name: str) -> Callable[..., object]:
    return sprig.generic_func_map()[name]


@pytest.mark.parametrize(
    ("name", "value", "expected"),
    [
        ("int", "1.9", 0),
        ("int", True, 1),
        ("int", object(), 0),
        ("float64", "1.25", 1.25),
        ("float64", "invalid", 0.0),
        ("toDecimal", "invalid", 0),
    ],
)
def test_numeric_conversions_follow_sprig_fallbacks(
    name: str, value: object, expected: object
) -> None:
    assert function(name)(value) == expected


def test_octal_conversion_uses_go_default_value_formatting() -> None:
    assert function("toDecimal")(7.0) == 7
    assert function("toDecimal")(-7.0) == -7
    assert function("toDecimal")(7.5) == 0


def test_integer_division_and_remainder_truncate_toward_zero() -> None:
    assert function("div")(-7, 3) == -2
    assert function("div")(7, -3) == -2
    assert function("mod")(-7, 3) == -1
    assert function("mod")(-(2**63), -1) == 0
    with pytest.raises(ZeroDivisionError):
        function("div")(1, 0)
    with pytest.raises(ZeroDivisionError):
        function("mod")(1, 0)


def test_go_string_integer_parsing_and_int64_overflow() -> None:
    convert = function("int64")

    assert [convert(value) for value in ("1.2", "1.0", "0x10", "010", "08")] == [
        0,
        1,
        16,
        8,
        0,
    ]
    assert function("atoi")("010") == 10
    assert function("atoi")("1.0") == 0
    assert function("add")(2**63 - 1, 1) == -(2**63)
    assert function("sub")(-(2**63), 1) == 2**63 - 1
    assert function("mul")(2**62, 2) == -(2**63)
    assert convert(str(2**63)) == 0
    assert function("float64")("0x1p+2") == 4.0
    assert function("float64")("-0x1.8p+1") == -3.0
    assert function("float64")("1e400") == 0.0


@pytest.mark.parametrize(
    ("arguments", "expected"),
    [
        ((3, 0, 1), []),
        ((3, 9, -1), []),
        ((3, 0, 0), []),
        ((3, 0, -1), [3, 2, 1]),
    ],
)
def test_until_step_handles_direction_and_zero_steps(
    arguments: tuple[int, int, int], expected: list[int]
) -> None:
    assert function("untilStep")(*arguments) == expected


def test_seq_rejects_unsupported_arity_and_direction() -> None:
    assert function("seq")(0, 1, 2, 3) == ""
    assert function("seq")(3, 3, 2) == ""


def test_sprig_empty_treats_python_objects_like_go_structs() -> None:
    assert function("empty")(object()) is False


def test_float_arithmetic_covers_empty_and_nan_paths() -> None:
    assert function("addf")() == 0.0
    assert function("subf")(5) == 5.0
    assert function("mulf")(5) == 5.0
    assert math.isnan(cast(float, function("maxf")(1, math.nan)))
    assert math.isnan(cast(float, function("minf")(math.nan, 1)))


def test_float_conversion_and_rounding_cover_fallbacks() -> None:
    assert function("float64")(object()) == 0.0
    assert function("int")(math.nan) == -(2**63)
    assert function("int")(float(2**63)) == -(2**63)
    assert function("int")(1.9) == 1
    assert function("int")("0") == 0
    assert function("ceil")("invalid") == 0.0
    assert function("floor")("invalid") == 0.0
    assert function("round")(1.25, 1) == 1.3
    assert function("round")(1.26, 1, 0.5) == 1.3


def test_numeric_string_parsers_reject_go_invalid_whitespace_and_separators() -> None:
    assert function("float64")(" 1.5 ") == 0.0
    assert function("int64")(" 12 ") == 0
    assert function("int64")("+") == 0
    assert function("int64")("0_7") == 7
    assert function("atoi")("1_000") == 0
    assert function("toDecimal")("7_7") == 0
    assert function("atoi")("\uff11\uff12") == 0
    assert function("float64")("0x_1p2") == 4.0
    assert function("float64")("0x1_0p2") == 64.0
    assert function("float64")("1_2.3_4e5_6") == 1.234e57
    assert function("float64")("1__2") == 0.0
    assert function("float64")("0x1.2") == 0.0
    assert function("float64")("0x1p99999") == 0.0


def test_go_float_math_preserves_signed_zero() -> None:
    negative_zero = function("float64")("-0")
    assert math.copysign(1.0, cast(float, negative_zero)) == -1.0
    assert math.copysign(1.0, cast(float, function("ceil")(negative_zero))) == -1.0
    assert math.copysign(1.0, cast(float, function("floor")(negative_zero))) == -1.0
    assert math.copysign(1.0, cast(float, function("maxf")(-0.0, 0.0))) == 1.0
    assert math.copysign(1.0, cast(float, function("maxf")(-0.0, -0.0))) == -1.0
    assert math.copysign(1.0, cast(float, function("minf")(0.0, -0.0))) == -1.0
    assert math.copysign(1.0, cast(float, function("minf")(0.0, 0.0))) == 1.0
    assert math.copysign(1.0, cast(float, function("round")(-0.0, 1))) == -1.0
    assert math.copysign(1.0, cast(float, function("round")(-0.0, 1, -0.5))) == -1.0


def test_decimal_division_uses_sprigs_sixteen_fractional_places() -> None:
    assert function("divf")("0.00000000000000000001", 3) == 0.0
    assert function("divf")(2, 3) == 0.6666666666666667
    with pytest.raises(ZeroDivisionError, match="decimal division by 0"):
        function("divf")(1, 0)


def test_special_float_values_follow_go_math_and_decimal_boundaries() -> None:
    assert math.isnan(cast(float, function("float64")("NaN")))
    assert function("float64")("+NaN") == 0.0
    assert function("float64")("-NaN") == 0.0
    assert function("float64")("Inf") == math.inf
    assert function("ceil")("Inf") == math.inf
    assert function("floor")("-Inf") == -math.inf
    assert math.isnan(cast(float, function("round")("NaN", 2)))
    with pytest.raises(ValueError, match="Cannot create a Decimal from NaN"):
        function("addf")("NaN", 1)
    with pytest.raises(ValueError, match=r"Cannot create a Decimal from -Inf"):
        function("divf")("-Inf", 1)


@pytest.mark.parametrize("name", ["add1f", "addf", "subf", "mulf"])
def test_decimal_arithmetic_preserves_nonfinite_panics(name: str) -> None:
    with pytest.raises(ValueError, match="Cannot create a Decimal from \\+Inf"):
        function(name)("+Inf", 1) if name != "add1f" else function(name)("+Inf")
