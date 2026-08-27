from dataclasses import FrozenInstanceError
from datetime import timedelta
from decimal import Decimal
from operator import index
from typing import Any, cast

import pytest

from goduration.go import Duration as GoDuration
from goduration.python import (
    DAY,
    HOUR,
    MICROSECOND,
    MILLISECOND,
    MINUTE,
    NANOSECOND,
    SECOND,
    WEEK,
    Duration,
)


def test_python_duration_uses_unbounded_integer_nanoseconds() -> None:
    value = Duration((1 << 100) + 7)

    assert value.nanoseconds == (1 << 100) + 7
    assert value + NANOSECOND == Duration((1 << 100) + 8)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (1.5, 2),
        (2.5, 2),
        (-1.5, -2),
        (Decimal("3.5"), 4),
    ],
)
def test_python_constructors_use_round_half_even(
    value: float | Decimal, expected: int
) -> None:
    assert Duration.from_nanoseconds(value) == Duration(expected)


def test_python_parse_uses_exact_decimal_not_go_float_scaling() -> None:
    assert Duration.parse("+0") == Duration()
    assert Duration.parse("-1.5s") == Duration.from_seconds(-1.5)
    assert Duration.parse("1h2m3s") == Duration.from_seconds(3_723)
    assert Duration.parse("0.9223372036854775809ns") == NANOSECOND
    assert Duration.parse("2.5ns") == Duration(2)
    assert Duration.parse("3.5ns") == Duration(4)
    assert Duration.parse("0.5ns0.5ns") == NANOSECOND
    assert Duration.parse("100000000000000000000h").nanoseconds > 1 << 63


def test_python_parse_raises_idiomatic_errors() -> None:
    with pytest.raises(ValueError, match="invalid duration"):
        Duration.parse("1d")
    with pytest.raises(TypeError, match="string"):
        Duration.parse(1)  # type: ignore[arg-type]
    for invalid in ("", "+", "1h!", "1h+2s"):
        with pytest.raises(ValueError, match="invalid duration"):
            Duration.parse(invalid)


def test_python_duration_is_immutable_ordered_and_hashable() -> None:
    value = Duration.from_seconds(1)

    assert value > MILLISECOND
    assert {value: "value"}[SECOND] == "value"
    with pytest.raises(FrozenInstanceError):
        value.nanoseconds = 0  # type: ignore[misc]
    with pytest.raises(TypeError):
        Duration(True)  # type: ignore[arg-type]


def test_python_named_constructors_cover_every_unit() -> None:
    assert Duration.from_microseconds(1.5) == Duration(1_500)
    assert Duration.from_milliseconds(1.5) == Duration(1_500_000)
    assert Duration.from_minutes(1.5) == 90 * SECOND
    assert Duration.from_hours(1.5) == 90 * MINUTE
    assert Duration.from_days(1.5) == 36 * HOUR
    assert Duration.from_weeks(1.5) == 10.5 * DAY
    assert WEEK == 7 * DAY


def test_python_arithmetic_uses_unbounded_and_half_even_behavior() -> None:
    value = Duration.from_seconds(1.5)

    assert value + timedelta(milliseconds=1) == Duration.from_seconds(1.501)
    assert timedelta(milliseconds=1) + value == Duration.from_seconds(1.501)
    assert value - SECOND == Duration.from_seconds(0.5)
    assert value - timedelta(milliseconds=1) == Duration.from_seconds(1.499)
    assert timedelta(seconds=2) - value == Duration.from_seconds(0.5)
    assert -value == Duration.from_seconds(-1.5)
    assert abs(-value) == value
    assert value * 1.5 == Duration.from_seconds(2.25)
    assert 1.5 * value == Duration.from_seconds(2.25)
    assert value / 2 == Duration.from_seconds(0.75)
    assert value / Duration.from_milliseconds(500) == 3.0
    assert Duration(2_500).round(MICROSECOND) == Duration(2_000)
    assert Duration(3_500).round(MICROSECOND) == Duration(4_000)
    assert Duration(-2_500).round(MICROSECOND) == Duration(-2_000)
    assert Duration(-3_500).round(MICROSECOND) == Duration(-4_000)
    assert Duration(3_999).truncate(MICROSECOND) == Duration(3_000)
    assert Duration(-3_999).truncate(MICROSECOND) == Duration(-3_000)


def test_python_integer_protocol_floor_modulo_and_sum() -> None:
    positive = Duration(5)
    negative = Duration(-5)
    divisor = Duration(2)

    assert not Duration()
    assert bool(positive)
    assert int(negative) == -5
    assert index(negative) == -5
    assert negative // divisor == -3
    assert negative % divisor == Duration(1)
    assert divmod(negative, divisor) == (-3, Duration(1))
    assert negative // 2 == Duration(-3)
    assert sum([Duration(2), Duration(3)]) == Duration(5)
    assert negative // timedelta(microseconds=1) == -1
    assert negative % timedelta(microseconds=1) == Duration(995)
    assert divmod(negative, timedelta(microseconds=1)) == (-1, Duration(995))


def test_python_floor_modulo_and_divmod_failures() -> None:
    for operation in (
        lambda: SECOND // Duration(),
        lambda: SECOND // timedelta(),
        lambda: SECOND // 0,
        lambda: SECOND % Duration(),
        lambda: SECOND % timedelta(),
        lambda: divmod(SECOND, Duration()),
        lambda: divmod(SECOND, timedelta()),
    ):
        with pytest.raises(ZeroDivisionError):
            operation()
    assert Duration.__floordiv__(SECOND, cast(Any, object())) is NotImplemented
    assert Duration.__mod__(SECOND, object()) is NotImplemented
    assert Duration.__divmod__(SECOND, object()) is NotImplemented


def test_python_arithmetic_rejects_unsupported_values_and_zero_division() -> None:
    with pytest.raises(TypeError):
        _ = SECOND + 1  # type: ignore[operator]
    with pytest.raises(TypeError):
        _ = SECOND - 1  # type: ignore[operator]
    with pytest.raises(TypeError):
        _ = 1 - SECOND  # type: ignore[operator]
    with pytest.raises(TypeError):
        _ = SECOND * "2"  # type: ignore[operator]
    with pytest.raises(TypeError):
        _ = SECOND / "2"  # type: ignore[operator]
    with pytest.raises(ZeroDivisionError):
        _ = SECOND / 0
    with pytest.raises(ZeroDivisionError):
        _ = SECOND / Duration()
    with pytest.raises(TypeError):
        SECOND.round(1)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        SECOND.truncate(1)  # type: ignore[arg-type]
    assert SECOND.round(Duration()) == SECOND
    assert SECOND.truncate(-NANOSECOND) == SECOND


def test_python_total_units_preserve_fractional_values() -> None:
    value = Duration(-1_500_001)

    assert value.total_nanoseconds() == -1_500_001
    assert value.total_microseconds() == pytest.approx(-1500.001)
    assert value.total_milliseconds() == pytest.approx(-1.500001)
    assert value.total_seconds() == pytest.approx(-0.001500001)
    assert value.total_minutes() == pytest.approx(-0.001500001 / 60)
    assert value.total_hours() == pytest.approx(-0.001500001 / 3600)
    assert value.total_days() == pytest.approx(-0.001500001 / 86_400)
    assert value.total_weeks() == pytest.approx(-0.001500001 / (7 * 86_400))


def test_python_timedelta_conversion_uses_python_half_even_precision() -> None:
    assert Duration.from_timedelta(timedelta(seconds=1, microseconds=2)) == Duration(
        1_000_002_000
    )
    assert Duration(1_500).to_timedelta() == timedelta(microseconds=2)
    assert Duration(2_500).to_timedelta() == timedelta(microseconds=2)
    assert Duration(-1_500).to_timedelta() == timedelta(microseconds=-2)
    with pytest.raises(TypeError):
        Duration.from_timedelta(1)  # type: ignore[arg-type]


def test_python_and_go_conversion_is_explicit_and_checked() -> None:
    go_value = GoDuration.parse("1.5s")
    python_value = Duration.from_go(go_value)

    assert python_value == Duration.from_seconds(1.5)
    assert python_value.to_go() == go_value
    with pytest.raises(OverflowError):
        Duration(1 << 100).to_go()
    with pytest.raises(TypeError):
        Duration.from_go(Duration())  # type: ignore[arg-type]


def test_python_string_retains_compact_duration_literals() -> None:
    assert str(Duration()) == "0s"
    assert str(Duration(-1)) == "-1ns"
    assert str(MICROSECOND) == "1µs"
    assert str(Duration(1_200)) == "1.2µs"
    assert str(MILLISECOND) == "1ms"
    assert str(Duration(1_250_000)) == "1.25ms"
    assert str(Duration.from_seconds(1.5)) == "1.5s"
    assert str(90 * MINUTE) == "1h30m0s"


def test_python_numeric_inputs_must_be_finite() -> None:
    with pytest.raises(ValueError, match="finite"):
        Duration.from_seconds(float("inf"))
    with pytest.raises(ValueError, match="finite"):
        Duration.from_seconds(Decimal("NaN"))
    with pytest.raises(TypeError):
        Duration.from_seconds("1")  # type: ignore[arg-type]
