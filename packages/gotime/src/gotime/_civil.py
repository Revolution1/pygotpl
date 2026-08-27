"""Integer civil-time conversion shared by the Go time surface."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta, tzinfo
from zoneinfo import ZoneInfo

from ._tzfile import zone_before_first_transition

_SECONDS_PER_DAY = 86_400
_UNIX_TO_INTERNAL = 62_135_596_800
_ABSOLUTE_YEARS = 292_277_022_400
_MARCH_THROUGH_DECEMBER = 306
_ABSOLUTE_TO_INTERNAL = -(
    (_ABSOLUTE_YEARS * 146_097 // 400 + _MARCH_THROUGH_DECEMBER) * _SECONDS_PER_DAY
)
_ABSOLUTE_TO_UNIX = _ABSOLUTE_TO_INTERNAL - _UNIX_TO_INTERNAL
_UINT64_MODULUS = 1 << 64
_MIN_DATETIME_UNIX = -62_135_596_800
_MAX_DATETIME_UNIX = 253_402_300_799


@dataclass(frozen=True, slots=True)
class CivilTime:
    year: int
    month: int
    day: int
    hour: int
    minute: int
    second: int
    nanosecond: int
    weekday: int
    year_day: int
    zone_name: str
    offset_seconds: int


def civil_from_datetime(value: datetime, nanosecond: int) -> CivilTime:
    offset = int((value.utcoffset() or timedelta(0)).total_seconds())
    return CivilTime(
        value.year,
        value.month,
        value.day,
        value.hour,
        value.minute,
        value.second,
        nanosecond,
        (value.weekday() + 1) % 7,
        value.timetuple().tm_yday,
        value.tzname() or "UTC",
        offset,
    )


def civil_from_unix(
    unix_seconds: int,
    nanosecond: int,
    location: tzinfo,
    *,
    fixed_zone: tuple[str, int] | None = None,
) -> CivilTime:
    zone_name, offset = fixed_zone or _zone_at(location, unix_seconds)
    calendar_seconds = _calendar_unix_seconds(unix_seconds + offset)
    days, seconds = divmod(calendar_seconds, _SECONDS_PER_DAY)
    year, month, day = _civil_from_days(days)
    hour, seconds = divmod(seconds, 3_600)
    minute, second = divmod(seconds, 60)
    return CivilTime(
        year,
        month,
        day,
        hour,
        minute,
        second,
        nanosecond,
        (days + 4) % 7,
        _year_day(year, month, day),
        zone_name,
        offset,
    )


def _calendar_unix_seconds(unix_seconds: int) -> int:
    if unix_seconds < _ABSOLUTE_TO_UNIX:
        return unix_seconds + _UINT64_MODULUS
    return unix_seconds


def _zone_at(location: tzinfo, unix_seconds: int) -> tuple[str, int]:
    if location is UTC:
        return "UTC", 0
    before_first = zone_before_first_transition(location, unix_seconds)
    if before_first is not None:
        return before_first
    if _MIN_DATETIME_UNIX <= unix_seconds <= _MAX_DATETIME_UNIX:
        localized = datetime.fromtimestamp(unix_seconds, UTC).astimezone(location)
        return _datetime_zone(localized)
    if isinstance(location, ZoneInfo):
        return _mapped_future_zone(location, unix_seconds)
    offset = int((location.utcoffset(None) or timedelta(0)).total_seconds())
    return location.tzname(None) or "UTC", offset


def _mapped_future_zone(location: ZoneInfo, unix_seconds: int) -> tuple[str, int]:
    days, seconds = divmod(_calendar_unix_seconds(unix_seconds), _SECONDS_PER_DAY)
    year, month, day = _civil_from_days(days)
    mapped_year = 2_000 + (year - 2_000) % 400
    hour, seconds = divmod(seconds, 3_600)
    minute, second = divmod(seconds, 60)
    mapped = datetime(mapped_year, month, day, hour, minute, second, tzinfo=UTC)
    return _datetime_zone(mapped.astimezone(location))


def _datetime_zone(value: datetime) -> tuple[str, int]:
    offset = int((value.utcoffset() or timedelta(0)).total_seconds())
    return value.tzname() or "UTC", offset


def _civil_from_days(days: int) -> tuple[int, int, int]:
    shifted = days + 719_468
    era, day_of_era = divmod(shifted, 146_097)
    year_of_era = (
        day_of_era - day_of_era // 1_460 + day_of_era // 36_524 - day_of_era // 146_096
    ) // 365
    year = year_of_era + era * 400
    day_of_year = day_of_era - (
        365 * year_of_era + year_of_era // 4 - year_of_era // 100
    )
    month_prime = (5 * day_of_year + 2) // 153
    day = day_of_year - (153 * month_prime + 2) // 5 + 1
    month = month_prime + (3 if month_prime < 10 else -9)
    year += month <= 2
    return year, month, day


def days_from_civil(year: int, month: int, day: int) -> int:
    """Return days since the Unix epoch for a normalized Gregorian date."""

    adjusted_year = year - (month <= 2)
    era, year_of_era = divmod(adjusted_year, 400)
    month_prime = month + (-3 if month > 2 else 9)
    day_of_year = (153 * month_prime + 2) // 5 + day - 1
    day_of_era = year_of_era * 365 + year_of_era // 4 - year_of_era // 100 + day_of_year
    return era * 146_097 + day_of_era - 719_468


def _year_day(year: int, month: int, day: int) -> int:
    starts = (0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334)
    result = starts[month - 1] + day
    if month > 2 and _is_leap(year):
        result += 1
    return result


def _is_leap(year: int) -> bool:
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)
