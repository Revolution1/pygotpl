# pyright: reportPrivateUsage=false

from datetime import UTC as DATETIME_UTC
from datetime import datetime

import pytest
from goduration.go import HOUR, SECOND, Duration

from gotime.go import (
    LOCAL,
    UTC,
    Location,
    Month,
    Time,
    Weekday,
    _detect_local_tzinfo,
)


def test_calendar_enums_use_go_values_and_strings() -> None:
    assert (int(Month.JANUARY), int(Month.DECEMBER)) == (1, 12)
    assert (str(Month.FEBRUARY), str(Month(13))) == (
        "February",
        "%!Month(13)",
    )
    assert (int(Weekday.SUNDAY), int(Weekday.SATURDAY)) == (0, 6)
    assert (str(Weekday.THURSDAY), str(Weekday(7))) == (
        "Thursday",
        "%!Weekday(7)",
    )


def test_zero_time_and_component_accessors() -> None:
    zero = Time.zero()

    assert zero.is_zero()
    assert zero.location is UTC
    assert zero.date() == (1, Month.JANUARY, 1)
    assert zero.clock() == (0, 0, 0)
    assert zero.year == 1
    assert zero.month is Month.JANUARY
    assert zero.day == 1
    assert zero.hour == zero.minute == zero.second == zero.nanosecond == 0
    assert zero.weekday is Weekday.MONDAY
    assert zero.year_day == 1


def test_unix_constructors_normalize_like_go_and_default_to_local() -> None:
    value = Time.from_unix(0, -1)

    assert value.location is LOCAL
    assert (value.unix_seconds, value.nanosecond) == (-1, 999_999_999)
    assert Time.from_unix_milliseconds(-1).unix_nanoseconds() == -1_000_000
    assert Time.from_unix_microseconds(-1).unix_nanoseconds() == -1_000
    assert Time.from_unix(1, 2).unix() == 1
    assert Time.from_unix(1, 2_345_678).unix_milliseconds() == 1_002
    assert Time.from_unix(1, 2_345_678).unix_microseconds() == 1_002_345


def test_from_components_normalizes_out_of_range_fields() -> None:
    value = Time.from_components(2011, 10, 32, 24, 60, 60, 1_000_000_000, UTC)

    assert value.date() == (2011, Month.NOVEMBER, 2)
    assert value.clock() == (1, 1, 1)
    assert value.nanosecond == 0


def test_calendar_arithmetic_matches_go_normalization() -> None:
    leap_day = Time.from_components(2024, Month.FEBRUARY, 29, 12, 0, 0, 0, UTC)
    moved = leap_day.add_date(years=1)

    assert moved.date() == (2025, Month.MARCH, 1)
    assert moved.clock() == (12, 0, 0)
    assert moved.add_date(months=1, days=-1).date() == (
        2025,
        Month.MARCH,
        31,
    )


def test_named_comparison_and_python_operator_equality_remain_distinct() -> None:
    instant = Time.from_unix(1_720_530_245, location=UTC)
    local = instant.in_location(LOCAL)
    later = instant + SECOND

    assert instant.equal(local)
    assert instant != local
    assert instant.before(later)
    assert later.after(instant)
    assert instant.compare(local) == 0
    assert instant.compare(later) == -1
    assert later.compare(instant) == 1


def test_location_and_zone_accessors() -> None:
    winter = Time.from_components(2024, 1, 15, 12, 0, 0, 0, UTC).in_location(
        Location.load("America/New_York")
    )
    summer = Time.from_components(2024, 7, 15, 12, 0, 0, 0, UTC).in_location(
        winter.location
    )

    assert winter.zone() == ("EST", -18_000)
    assert summer.zone() == ("EDT", -14_400)
    assert not winter.is_dst()
    assert summer.is_dst()
    assert summer.utc().location is UTC
    assert summer.local().location is LOCAL


def test_location_empty_name_loads_utc_like_go() -> None:
    assert Location.load("") is UTC


def test_local_timezone_detection_honors_go_tz_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TZ", "")
    assert _detect_local_tzinfo() is DATETIME_UTC

    monkeypatch.setenv("TZ", ":America/New_York")
    detected = _detect_local_tzinfo()
    assert getattr(detected, "key", None) == "America/New_York"

    monkeypatch.setenv("TZ", "Not/AZone")
    assert _detect_local_tzinfo() is DATETIME_UTC


def test_round_and_truncate_are_absolute_since_go_zero_time() -> None:
    value = Time.from_unix(61, 600_000_000, location=UTC)

    assert value.truncate(SECOND).unix_nanoseconds() == 61_000_000_000
    assert value.round(SECOND).unix_nanoseconds() == 62_000_000_000
    assert value.round(Duration(0)) == value
    assert value.truncate(-HOUR) == value


def test_datetime_and_injected_clock_construction() -> None:
    expected = datetime(2024, 7, 9, 13, 4, 5, 123_456, tzinfo=DATETIME_UTC)
    value = Time.now(clock=lambda: expected)

    assert value.to_datetime() == expected
    assert value.nanosecond == 123_456_000
    assert Time.since(value, clock=lambda: expected) == Duration(0)
    assert Time.until(value, clock=lambda: expected) == Duration(0)
