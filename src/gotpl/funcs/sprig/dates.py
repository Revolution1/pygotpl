"""Sprig-compatible date, time, and duration helpers."""

from __future__ import annotations

import os
import re
from collections.abc import Callable
from contextlib import suppress
from datetime import UTC, datetime, timedelta, tzinfo
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from goduration.go import (
    MAX_NANOSECONDS,
    MIN_NANOSECONDS,
    SECOND,
    Duration,
    DurationParseError,
)
from gotime.go import Location as GoLocation
from gotime.go import ParseError as GoTimeParseError
from gotime.go import Time as GoTime
from tzlocal import get_localzone

Clock = Callable[[], datetime]

_ZERO_TIME = datetime(1, 1, 1, tzinfo=UTC)


class _GoDateTime(datetime):
    __slots__ = ("nanosecond",)

    nanosecond: int


def now(*, clock: Clock | None = None) -> datetime:
    """Return the current local time."""

    return _clock_value(clock)


def date(layout: str, value: object, *, clock: Clock | None = None) -> str:
    return date_in_zone(layout, value, "Local", clock=clock)


def html_date(value: object, *, clock: Clock | None = None) -> str:
    return date_in_zone("2006-01-02", value, "Local", clock=clock)


def html_date_in_zone(value: object, zone: str, *, clock: Clock | None = None) -> str:
    return date_in_zone("2006-01-02", value, zone, clock=clock)


def date_in_zone(
    layout: str, value: object, zone: str, *, clock: Clock | None = None
) -> str:
    instant = _coerce_datetime(value, clock)
    location = _load_zone(zone)
    if isinstance(instant, GoTime):
        return instant.in_location(GoLocation.from_tzinfo(location)).format(layout)
    nanosecond = _datetime_nanosecond(instant)
    try:
        instant = instant.astimezone(location)
    except (OverflowError, ValueError):
        instant = instant.replace(tzinfo=location)
    return _go_time_from_datetime(instant, nanosecond).format(layout)


def date_modify(duration_text: str, value: datetime) -> datetime:
    try:
        nanoseconds = _parse_duration_nanoseconds(duration_text)
    except ValueError:
        return value
    return _add_nanoseconds(value, nanoseconds)


def must_date_modify(duration_text: str, value: datetime) -> datetime:
    nanoseconds = _parse_duration_nanoseconds(duration_text)
    return _add_nanoseconds(value, nanoseconds)


def ago(value: object, *, clock: Clock | None = None) -> str:
    instant = _coerce_datetime(value, clock)
    if isinstance(instant, GoTime):
        nanoseconds = _instant_age_nanoseconds(_clock_value(clock), instant)
    else:
        nanoseconds = _timedelta_nanoseconds(_clock_value(clock) - instant)
    return str(_duration_clamped(nanoseconds).round(SECOND))


def duration(value: object) -> str:
    seconds = 0
    if isinstance(value, str):
        try:
            seconds = int(value, 10)
            if not -(1 << 63) <= seconds < (1 << 63):
                seconds = 0
        except ValueError:
            pass
    return str(Duration(_signed_int64(seconds * 1_000_000_000)))


def duration_round(value: object, *, clock: Clock | None = None) -> str:
    nanoseconds = 0
    if isinstance(value, str):
        with suppress(ValueError):
            nanoseconds = _parse_duration_nanoseconds(value)
    elif isinstance(value, datetime):
        nanoseconds = _timedelta_nanoseconds(_clock_value(clock) - value)
    absolute = abs(nanoseconds)
    for unit, suffix in (
        (365 * 24 * 3_600_000_000_000, "y"),
        (30 * 24 * 3_600_000_000_000, "mo"),
        (24 * 3_600_000_000_000, "d"),
        (3_600_000_000_000, "h"),
        (60_000_000_000, "m"),
        (1_000_000_000, "s"),
    ):
        if absolute > unit:
            return f"{absolute // unit}{suffix}"
    return "0s"


def to_date(layout: str, value: str) -> datetime:
    try:
        return _parse_go_time(layout, value, _local_timezone())
    except ValueError:
        return _ZERO_TIME


def must_to_date(layout: str, value: str) -> datetime:
    return _parse_go_time(layout, value, _local_timezone())


def unix_epoch(value: datetime) -> str:
    epoch = datetime(1970, 1, 1, tzinfo=UTC)
    normalized = value.astimezone(UTC)
    elapsed = normalized - epoch
    return str(elapsed.days * 86_400 + elapsed.seconds)


def _clock_value(clock: Clock | None) -> datetime:
    value = clock() if clock is not None else datetime.now().astimezone()
    return value.replace(tzinfo=_local_timezone()) if value.tzinfo is None else value


def _coerce_datetime(value: object, clock: Clock | None) -> datetime | GoTime:
    if isinstance(value, datetime):
        return (
            value.replace(tzinfo=_local_timezone()) if value.tzinfo is None else value
        )
    if isinstance(value, int) and not isinstance(value, bool):
        return GoTime.from_unix(value)
    return _clock_value(clock)


def _instant_age_nanoseconds(now_value: datetime, instant: GoTime) -> int:
    if instant.unix_seconds == (1 << 63) - 1:
        return (1 << 63) - 1
    epoch = datetime(1970, 1, 1, tzinfo=UTC)
    elapsed = now_value.astimezone(UTC) - epoch
    now_nanoseconds = _timedelta_nanoseconds(elapsed)
    difference = now_nanoseconds - (
        instant.unix_seconds * 1_000_000_000 + instant.nanosecond
    )
    return max(-(1 << 63), min((1 << 63) - 1, difference))


def _load_zone(name: str) -> tzinfo:
    if name == "Local":
        return _local_timezone()
    return _load_named_zone(name)


def _local_timezone() -> tzinfo:
    if "TZ" in os.environ:
        name = os.environ["TZ"]
        if name.startswith(":"):
            name = name[1:]
        if not name:
            return UTC
        if os.path.isabs(name):
            try:
                with open(name, "rb") as zone_file:
                    return ZoneInfo.from_file(zone_file, key=name)
            except (OSError, ValueError):
                return UTC
        return _load_named_zone(name)
    try:
        return get_localzone()
    except (OSError, ZoneInfoNotFoundError):
        return UTC


def _load_named_zone(name: str) -> tzinfo:
    if name == "UTC":
        return UTC
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        return UTC


def _add_nanoseconds(value: datetime, nanoseconds: int) -> datetime:
    seconds, fraction = divmod(_datetime_nanosecond(value) + nanoseconds, 1_000_000_000)
    if value.tzinfo is None:
        moved = value.replace(microsecond=0) + timedelta(seconds=seconds)
    else:
        location = value.tzinfo
        absolute = value.astimezone(UTC).replace(microsecond=0)
        moved = (absolute + timedelta(seconds=seconds)).astimezone(location)
    return _with_nanosecond(moved, fraction)


def _datetime_nanosecond(value: datetime) -> int:
    if isinstance(value, _GoDateTime):
        return getattr(value, "nanosecond", value.microsecond * 1_000)
    return value.microsecond * 1_000


def _with_nanosecond(value: datetime, nanosecond: int) -> _GoDateTime:
    result = _GoDateTime(
        value.year,
        value.month,
        value.day,
        value.hour,
        value.minute,
        value.second,
        nanosecond // 1_000,
        tzinfo=value.tzinfo,
        fold=value.fold,
    )
    result.nanosecond = nanosecond
    return result


def _timedelta_nanoseconds(value: timedelta) -> int:
    return (
        value.days * 86_400_000_000_000
        + value.seconds * 1_000_000_000
        + value.microseconds * 1_000
    )


def _duration_clamped(nanoseconds: int) -> Duration:
    return Duration(max(MIN_NANOSECONDS, min(MAX_NANOSECONDS, nanoseconds)))


def _parse_duration_nanoseconds(value: str) -> int:
    try:
        return Duration.parse(value).nanoseconds
    except DurationParseError as error:
        raise ValueError(f"time: invalid duration {value!r}") from error


def _signed_int64(value: int) -> int:
    return (value + (1 << 63)) % (1 << 64) - (1 << 63)


def _go_time_from_datetime(value: datetime, nanosecond: int) -> GoTime:
    standard_value = datetime(
        value.year,
        value.month,
        value.day,
        value.hour,
        value.minute,
        value.second,
        value.microsecond,
        tzinfo=value.tzinfo,
        fold=value.fold,
    )
    base = GoTime.from_datetime(standard_value)
    return GoTime.from_unix(
        base.unix_seconds,
        nanosecond,
        location=base.location,
    )


def _parse_go_time(layout: str, value: str, location: tzinfo) -> datetime:
    try:
        parsed = GoTime.parse_in_location(
            layout,
            value,
            GoLocation.from_tzinfo(location),
        )
    except GoTimeParseError as error:
        fixed_fraction = re.search(r"[.,]0+", layout)
        value_fraction = re.search(r"[.,](\d+)", value)
        if (
            fixed_fraction is not None
            and value_fraction is not None
            and len(value_fraction.group(1)) > len(fixed_fraction.group(0)) - 1
        ):
            raise ValueError("fractional second out of range") from error
        raise
    return _with_nanosecond(parsed.to_datetime(), parsed.nanosecond)
