from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from goduration.go import MAX_DURATION, MIN_DURATION
from goduration.go import SECOND as GO_SECOND
from goduration.python import Duration as PythonDuration

import gotime
from gotime.go import UTC as GO_UTC
from gotime.go import Location, LocationError
from gotime.go import Time as GoTime
from gotime.python import Time as PythonTime


def test_top_level_time_defaults_to_go_surface() -> None:
    assert gotime.Time is GoTime


def test_top_level_exports_its_version() -> None:
    assert "__version__" in gotime.__all__
    assert gotime.__version__ == "0.1.0"


def test_go_unix_normalizes_nanoseconds_and_exposes_civil_time() -> None:
    value = GoTime.from_unix(0, 1_500_000_001, location=GO_UTC)
    civil = value.civil()

    assert (value.unix_seconds, value.nanosecond) == (1, 500_000_001)
    assert (
        civil.year,
        civil.month,
        civil.day,
        civil.hour,
        civil.minute,
        civil.second,
        civil.nanosecond,
        civil.zone_name,
    ) == (1970, 1, 1, 0, 0, 1, 500_000_001, "UTC")


def test_go_location_changes_presentation_not_instant() -> None:
    new_york = Location.load("America/New_York")
    utc_value = GoTime.from_unix(1_720_530_245, location=GO_UTC)
    local_value = utc_value.in_location(new_york)
    civil = local_value.civil()

    assert local_value.equal(utc_value)
    assert local_value != utc_value
    assert (civil.hour, civil.zone_name, civil.offset_seconds) == (9, "EDT", -14_400)


def test_go_datetime_round_trip_and_duration_arithmetic() -> None:
    original = datetime(2024, 7, 9, 13, 4, 5, 123_456, tzinfo=UTC)
    value = GoTime.from_datetime(original)

    assert value.to_datetime() == original
    assert (value + GO_SECOND).to_datetime() == original + timedelta(seconds=1)
    assert (value + GO_SECOND) - value == GO_SECOND
    assert value - GO_SECOND == GoTime.from_datetime(original - timedelta(seconds=1))


def test_go_time_subtraction_saturates_to_duration_range() -> None:
    maximum = GoTime.from_unix((1 << 63) - 1)
    minimum = GoTime.from_unix(-(1 << 63))

    assert maximum - minimum == MAX_DURATION
    assert minimum - maximum == MIN_DURATION


def test_go_extreme_civil_conversion_preserves_existing_behavior() -> None:
    civil = GoTime.from_unix((1 << 63) - 1, 123, location=GO_UTC).civil()

    assert (civil.year, civil.month, civil.day, civil.second, civil.nanosecond) == (
        292_277_026_596,
        12,
        4,
        7,
        123,
    )


def test_go_location_reports_clear_errors() -> None:
    with pytest.raises(LocationError, match="unknown time zone"):
        Location.load("Not/AZone")


def test_python_time_uses_datetime_and_preserves_submicrosecond_precision() -> None:
    original = datetime(2024, 7, 9, 13, 4, 5, 123_456, tzinfo=UTC)
    value = PythonTime.from_datetime(original)
    moved = value + PythonDuration(1_500)

    assert moved.datetime == original + timedelta(microseconds=1)
    assert moved.submicrosecond_nanoseconds == 500
    assert moved - value == PythonDuration(1_500)
    with pytest.raises(ValueError, match="precision"):
        moved.to_datetime()
    assert moved.to_datetime(allow_precision_loss=True) == moved.datetime


def test_python_time_follows_datetime_timezone_behavior() -> None:
    value = PythonTime.from_datetime(datetime(2024, 7, 9, 13, tzinfo=UTC))
    local = value.in_timezone(ZoneInfo("America/New_York"))

    assert local.datetime.hour == 9
    assert local.datetime.tzname() == "EDT"
    assert local == value


def test_python_time_arithmetic_accepts_timedelta_and_duration() -> None:
    value = PythonTime.from_datetime(datetime(2024, 1, 1, tzinfo=UTC))

    assert value + timedelta(seconds=1) == value + PythonDuration.from_seconds(1)
    assert value - timedelta(seconds=1) < value
    assert value - (value - timedelta(seconds=1)) == PythonDuration.from_seconds(1)


def test_cross_surface_conversion_is_explicit() -> None:
    go_value = GoTime.from_unix(1_720_530_245, 123_456_789)
    python_value = PythonTime.from_go(go_value)

    assert python_value.submicrosecond_nanoseconds == 789
    assert python_value.to_go() == go_value
