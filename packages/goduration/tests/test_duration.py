from dataclasses import FrozenInstanceError
from datetime import timedelta
from decimal import Decimal
from operator import index

import pytest

import goduration
from goduration import (
    HOUR,
    MAX_DURATION,
    MICROSECOND,
    MILLISECOND,
    MIN_DURATION,
    MINUTE,
    NANOSECOND,
    SECOND,
    Duration,
    DurationParseError,
)
from goduration.go import Duration as GoDuration


def test_top_level_duration_defaults_to_explicit_go_surface() -> None:
    assert goduration.Duration is GoDuration
    assert GoDuration.parse("0.3333333333333333333h").nanoseconds == 1_200_000_000_000


@pytest.mark.parametrize(
    ("text", "nanoseconds"),
    [
        ("0", 0),
        ("+0", 0),
        ("-0", 0),
        ("0.0s", 0),
        ("1.s", 1_000_000_000),
        ("1.5h", 5_400_000_000_000),
        ("2h45m6.25s", 9_906_250_000_000),
        (".5ms", 500_000),
        ("12us", 12_000),
        ("12µs", 12_000),
        ("12μs", 12_000),
        ("0.3333333333333333333h", 1_200_000_000_000),
        ("9007199254740993ns", 9_007_199_254_740_993),
        ("9223372036854775807ns", (1 << 63) - 1),
        ("-9223372036854775808ns", -(1 << 63)),
    ],
)
def test_parse_preserves_go_duration_values(text: str, nanoseconds: int) -> None:
    duration = Duration.parse(text)

    assert duration.nanoseconds == nanoseconds


@pytest.mark.parametrize(
    "text",
    [
        "",
        "+",
        "3",
        ".s",
        "1d",
        "1h!",
        "9223372036854775808ns",
        "9223372036854775808.0ns",
        "9223372036854775809.0ns",
        "-9223372036854775809ns",
    ],
)
def test_parse_rejects_invalid_and_overflowing_values(text: str) -> None:
    with pytest.raises(DurationParseError) as captured:
        Duration.parse(text)

    assert captured.value.value == text
    assert str(captured.value).startswith("time: ")


@pytest.mark.parametrize(
    "text",
    [
        "1..s",
        "1h+2s",
        "5000000000000000000ns5000000000000000000ns",
    ],
)
def test_parse_rejects_additional_go_syntax_failures(text: str) -> None:
    with pytest.raises(DurationParseError):
        Duration.parse(text)


def test_parse_matches_go_fraction_precision_limits() -> None:
    assert Duration.parse("0.33333333333333333330h") == Duration.parse("20m")
    assert Duration.parse("0.9223372036854775809ns") == Duration()


def test_core_constructors_reject_invalid_python_values() -> None:
    with pytest.raises(TypeError):
        Duration(True)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        Duration.parse(1)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        Duration.from_seconds(True)
    with pytest.raises(ValueError, match="finite"):
        Duration.from_seconds(float("inf"))
    with pytest.raises(ValueError, match="finite"):
        Duration.from_seconds(Decimal("NaN"))
    with pytest.raises(TypeError):
        Duration.from_timedelta(1)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("nanoseconds", "expected"),
    [
        (0, "0s"),
        (1, "1ns"),
        (-1, "-1ns"),
        (1_200, "1.2µs"),
        (1_250_000, "1.25ms"),
        (1_000_000_001, "1.000000001s"),
        (61_000_000_000, "1m1s"),
        (93_784_000_000_000, "26h3m4s"),
        ((1 << 63) - 1, "2562047h47m16.854775807s"),
        (-(1 << 63), "-2562047h47m16.854775808s"),
    ],
)
def test_string_uses_go_duration_format(nanoseconds: int, expected: str) -> None:
    assert str(Duration(nanoseconds)) == expected


def test_named_constructors_and_constants_are_typed_durations() -> None:
    assert Duration.from_nanoseconds(4) == 4 * NANOSECOND
    assert Duration.from_microseconds(Decimal("1.5")) == 1500 * NANOSECOND
    assert Duration.from_milliseconds(1.25) == 1250 * MICROSECOND
    assert Duration.from_seconds(2.5) == 2500 * MILLISECOND
    assert Duration.from_minutes(2) == 120 * SECOND
    assert Duration.from_hours(2) == 120 * MINUTE
    assert HOUR == 60 * MINUTE


def test_duration_is_immutable_ordered_and_hashable() -> None:
    duration = Duration.from_seconds(2)

    assert duration > SECOND
    assert {duration: "value"}[Duration.from_seconds(2)] == "value"
    with pytest.raises(FrozenInstanceError):
        duration.nanoseconds = 0  # type: ignore[misc]


def test_arithmetic_uses_duration_values_and_numeric_scalars() -> None:
    duration = Duration.parse("1.5s")

    assert duration + MILLISECOND == Duration.parse("1.501s")
    assert duration - SECOND == Duration.parse("500ms")
    assert -duration == Duration.parse("-1.5s")
    assert abs(-duration) == duration
    assert duration * 2 == Duration.parse("3s")
    assert 2 * duration == Duration.parse("3s")
    assert duration / 2 == Duration.parse("750ms")
    assert duration / Duration.parse("500ms") == Duration(3)


def test_integer_operators_follow_go_duration_semantics() -> None:
    assert MAX_DURATION + NANOSECOND == MIN_DURATION
    assert MIN_DURATION - NANOSECOND == MAX_DURATION
    assert -MIN_DURATION == MIN_DURATION
    assert Duration(-2) == MAX_DURATION * 2
    assert MIN_DURATION / Duration(-1) == MIN_DURATION
    assert Duration(2) == 5 * SECOND / (2 * SECOND)
    assert Duration(2) == 5 * SECOND // (2 * SECOND)
    assert 5 * SECOND % (2 * SECOND) == SECOND
    assert divmod(5 * SECOND, 2 * SECOND) == (Duration(2), SECOND)
    assert int(SECOND) == 1_000_000_000
    assert index(SECOND) == 1_000_000_000
    assert Duration.parse("2.5s") == 5 * SECOND // 2
    assert Duration(5) % 2 == Duration(1)
    assert (Duration(0b1100) & Duration(0b1010)) == Duration(0b1000)
    assert (Duration(0b1100) | Duration(0b0011)) == Duration(0b1111)
    assert (Duration(0b1100) ^ Duration(0b1010)) == Duration(0b0110)
    assert ~Duration(0) == Duration(-1)
    assert Duration(1) << 63 == MIN_DURATION
    assert Duration(-8) >> 2 == Duration(-2)


def test_go_integer_operator_failures_are_explicit() -> None:
    with pytest.raises(ZeroDivisionError):
        _ = SECOND // Duration()
    with pytest.raises(ZeroDivisionError):
        _ = SECOND % Duration()
    with pytest.raises(TypeError):
        Duration.__floordiv__(SECOND, "2")  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        Duration.__mod__(SECOND, "2")  # type: ignore[arg-type]
    assert Duration.__and__(SECOND, object()) is NotImplemented
    assert Duration.__or__(SECOND, object()) is NotImplemented
    assert Duration.__xor__(SECOND, object()) is NotImplemented
    assert Duration.__lshift__(SECOND, object()) is NotImplemented
    assert Duration.__rshift__(SECOND, object()) is NotImplemented
    with pytest.raises(ValueError, match="negative shift"):
        _ = SECOND << -1
    with pytest.raises(ValueError, match="negative shift"):
        _ = SECOND >> -1


def test_arithmetic_rejects_unsupported_types_and_overflow() -> None:
    with pytest.raises(TypeError):
        _ = SECOND + 1  # type: ignore[operator]
    with pytest.raises(TypeError):
        _ = SECOND * "2"  # type: ignore[operator]
    with pytest.raises(TypeError):
        _ = SECOND - 1  # type: ignore[operator]
    with pytest.raises(TypeError):
        _ = SECOND / "2"  # type: ignore[operator]
    with pytest.raises(ZeroDivisionError):
        _ = SECOND / 0
    with pytest.raises(ZeroDivisionError):
        _ = SECOND / Duration()
    with pytest.raises(TypeError):
        _ = SECOND * Decimal("1.5")
    with pytest.raises(TypeError):
        _ = SECOND / 1.5  # type: ignore[operator]


def test_parse_errors_match_go_quoted_text() -> None:
    with pytest.raises(DurationParseError) as captured:
        Duration.parse("1d")

    assert str(captured.value) == 'time: unknown unit "d" in duration "1d"'


def test_round_truncate_and_abs_follow_go_boundaries() -> None:
    assert Duration.parse("2m30s").round(MINUTE) == Duration.parse("3m")
    assert Duration.parse("-2m30s").round(MINUTE) == Duration.parse("-3m")
    assert Duration.parse("10m10s").truncate(3 * MINUTE) == Duration.parse("9m")
    assert Duration.parse("-10m10s").truncate(3 * MINUTE) == Duration.parse("-9m")
    assert SECOND.round(Duration(0)) == SECOND
    assert SECOND.truncate(-NANOSECOND) == SECOND
    assert Duration.parse("2m20s").round(MINUTE) == Duration.parse("2m")
    assert (
        Duration(-9_000_000_000_000_000_000).round(Duration(5_000_000_000_000_000_000))
        == MIN_DURATION
    )
    assert abs(MIN_DURATION) == MAX_DURATION
    with pytest.raises(TypeError):
        SECOND.round(1)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        SECOND.truncate(1)  # type: ignore[arg-type]


def test_total_unit_accessors_preserve_sign_and_fraction() -> None:
    duration = Duration(-1_500_001)

    assert duration.total_nanoseconds() == -1_500_001
    assert duration.total_microseconds() == -1500
    assert duration.total_milliseconds() == -1
    assert duration.total_seconds() == pytest.approx(-0.001500001)
    assert duration.total_minutes() == pytest.approx(-0.001500001 / 60)
    assert duration.total_hours() == pytest.approx(-0.001500001 / 3600)


def test_timedelta_conversion_makes_nanosecond_loss_explicit() -> None:
    assert Duration.from_timedelta(timedelta(seconds=1, microseconds=2)) == Duration(
        1_000_002_000
    )
    assert Duration(1_000).to_timedelta() == timedelta(microseconds=1)
    with pytest.raises(ValueError, match="nanosecond precision"):
        Duration(1_001).to_timedelta()
    assert Duration(-1_001).to_timedelta(allow_precision_loss=True) == timedelta(
        microseconds=-1
    )
