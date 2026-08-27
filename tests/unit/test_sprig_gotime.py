# pyright: reportPrivateUsage=false

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from gotime import _civil
from hypothesis import given
from hypothesis import strategies as st

_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)


@given(st.integers(min_value=-62_135_596_800, max_value=253_402_300_799))
def test_integer_utc_civil_conversion_matches_datetime(unix_seconds: int) -> None:
    expected = _EPOCH + timedelta(seconds=unix_seconds)
    actual = _civil.civil_from_unix(unix_seconds, 0, UTC)

    assert (
        actual.year,
        actual.month,
        actual.day,
        actual.hour,
        actual.minute,
        actual.second,
        actual.weekday,
        actual.year_day,
        actual.zone_name,
        actual.offset_seconds,
    ) == (
        expected.year,
        expected.month,
        expected.day,
        expected.hour,
        expected.minute,
        expected.second,
        (expected.weekday() + 1) % 7,
        expected.timetuple().tm_yday,
        "UTC",
        0,
    )


@given(st.integers(min_value=-2_208_988_800, max_value=4_133_980_799))
def test_integer_named_zone_conversion_matches_zoneinfo(unix_seconds: int) -> None:
    location = ZoneInfo("America/New_York")
    expected = (_EPOCH + timedelta(seconds=unix_seconds)).astimezone(location)
    actual = _civil.civil_from_unix(unix_seconds, 0, location)

    assert (
        actual.year,
        actual.month,
        actual.day,
        actual.hour,
        actual.minute,
        actual.second,
        actual.zone_name,
        actual.offset_seconds,
    ) == (
        expected.year,
        expected.month,
        expected.day,
        expected.hour,
        expected.minute,
        expected.second,
        expected.tzname(),
        int((expected.utcoffset() or timedelta(0)).total_seconds()),
    )


def test_arbitrary_civil_boundaries_and_fixed_offset_location() -> None:
    maximum = _civil.civil_from_unix((1 << 63) - 1, 0, UTC)
    wrapped_minimum = _civil.civil_from_unix(-(1 << 63), 0, UTC)
    fixed = timezone(timedelta(hours=5, minutes=45), "NPT")
    fixed_civil = _civil.civil_from_unix((1 << 63) - 1, 123, fixed)

    assert (maximum.year, maximum.month, maximum.day, maximum.second) == (
        292_277_026_596,
        12,
        4,
        7,
    )
    assert (wrapped_minimum.year, wrapped_minimum.second) == (292_277_026_596, 8)
    assert (
        fixed_civil.hour,
        fixed_civil.minute,
        fixed_civil.nanosecond,
        fixed_civil.zone_name,
        fixed_civil.offset_seconds,
    ) == (21, 15, 123, "NPT", 20_700)


def test_datetime_adapter_preserves_civil_metadata() -> None:
    value = datetime(2024, 2, 29, 23, 59, 58, tzinfo=UTC)
    civil = _civil.civil_from_datetime(value, 123_456_789)

    assert (civil.weekday, civil.year_day, civil.nanosecond) == (4, 60, 123_456_789)
