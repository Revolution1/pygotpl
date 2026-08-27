"""Sprout time registry backed by the extracted Go-compatible values."""

from __future__ import annotations

from goduration.go import SECOND, Duration
from gotime.go import Location, Time

from gotpl.runtime import FunctionResult

from .registry import TemplateFunction

_INT64_MIN = -(1 << 63)
_INT64_MAX = (1 << 63) - 1
_NANOSECONDS_PER_SECOND = 1_000_000_000


def _wrap_int64(value: int) -> int:
    return (value + (1 << 63)) % (1 << 64) - (1 << 63)


def _compute_time(value: object) -> Time:
    if isinstance(value, Time):
        return value
    if isinstance(value, int) and not isinstance(value, bool):
        return Time.from_unix(value)
    return Time.now().local()


def _date(layout: str, value: object) -> FunctionResult:
    current = _compute_time(value)
    name, offset = current.zone()
    fixed = current.in_location(Location.fixed(name, offset))
    return FunctionResult.success(fixed.format(layout))


def _date_in_zone(layout: str, value: object, zone: str) -> FunctionResult:
    current = _compute_time(value)
    try:
        return FunctionResult.success(
            current.in_location(Location.load(zone)).format(layout)
        )
    except ValueError as error:
        return FunctionResult.failure(error, value=current.utc().format(layout))


def _duration(value: object) -> str:
    number = 0
    if isinstance(value, str):
        try:
            number = int(value, 10)
        except ValueError:
            number = 0
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        number = int(value)
    nanoseconds = _wrap_int64(number * _NANOSECONDS_PER_SECOND)
    return str(Duration(nanoseconds))


def _date_ago(value: object) -> str:
    current = _compute_time(value)
    return str(Time.now().subtract(current).round(SECOND))


def _now() -> Time:
    return Time.now()


def _unix_epoch(value: Time) -> str:
    return str(value.unix())


def _unix_milliseconds(value: Time) -> str:
    return str(value.unix_milliseconds())


def _unix_microseconds(value: Time) -> str:
    return str(value.unix_microseconds())


def _integer(value: object) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        result = value
    elif isinstance(value, float):
        result = int(value)
    elif isinstance(value, str):
        try:
            result = int(value.strip(), 0)
        except ValueError:
            try:
                result = int(value.strip(), 10)
            except ValueError as error:
                raise ValueError(f"unable to cast {value!r} to int64") from error
    else:
        raise ValueError(f"unable to cast {type(value).__name__} to int64")
    if not _INT64_MIN <= result <= _INT64_MAX:
        raise ValueError(f"unable to cast {value!r} to int64")
    return result


def _from_unix(value: object) -> FunctionResult:
    try:
        return FunctionResult.success(Time.from_unix(_integer(value)))
    except ValueError as error:
        return FunctionResult.failure(error, value=Time.zero())


def _from_unix_milliseconds(value: object) -> FunctionResult:
    try:
        return FunctionResult.success(Time.from_unix_milliseconds(_integer(value)))
    except ValueError as error:
        return FunctionResult.failure(error, value=Time.zero())


def _from_unix_microseconds(value: object) -> FunctionResult:
    try:
        return FunctionResult.success(Time.from_unix_microseconds(_integer(value)))
    except ValueError as error:
        return FunctionResult.failure(error, value=Time.zero())


def _date_modify(layout: str, value: Time) -> FunctionResult:
    try:
        return FunctionResult.success(value.add(Duration.parse(layout)))
    except ValueError as error:
        return FunctionResult.failure(error, value=Time.zero())


def _duration_value(value: object) -> int:
    if isinstance(value, str):
        try:
            return Duration.parse(value).nanoseconds
        except ValueError:
            return 0
    if isinstance(value, Duration):
        return value.nanoseconds
    if isinstance(value, int) and not isinstance(value, bool):
        return _wrap_int64(value)
    if isinstance(value, Time):
        return Time.now().subtract(value).nanoseconds
    return 0


def _duration_round(value: object) -> str:
    nanoseconds = _duration_value(value)
    magnitude = abs(nanoseconds)
    if magnitude == 0:
        return "0s"
    sign = "-" if nanoseconds < 0 else ""
    units = (
        (365 * 24 * 3_600 * _NANOSECONDS_PER_SECOND, "y"),
        (30 * 24 * 3_600 * _NANOSECONDS_PER_SECOND, "mo"),
        (24 * 3_600 * _NANOSECONDS_PER_SECOND, "d"),
        (3_600 * _NANOSECONDS_PER_SECOND, "h"),
        (60 * _NANOSECONDS_PER_SECOND, "m"),
        (_NANOSECONDS_PER_SECOND, "s"),
    )
    for unit, suffix in units:
        if magnitude > unit:
            return f"{sign}{magnitude // unit}{suffix}"
    return sign


def _html_date(value: object) -> FunctionResult:
    return _date_in_zone("2006-01-02", value, "Local")


def _html_date_in_zone(value: object, zone: str) -> FunctionResult:
    return _date_in_zone("2006-01-02", value, zone)


def functions() -> dict[str, TemplateFunction]:
    """Return the complete pinned Sprout time function map."""

    return {
        "date": _date,
        "dateInZone": _date_in_zone,
        "duration": _duration,
        "dateAgo": _date_ago,
        "now": _now,
        "unixEpoch": _unix_epoch,
        "toUnixMilli": _unix_milliseconds,
        "toUnixMicro": _unix_microseconds,
        "fromUnix": _from_unix,
        "fromUnixMilli": _from_unix_milliseconds,
        "fromUnixMicro": _from_unix_microseconds,
        "dateModify": _date_modify,
        "durationRound": _duration_round,
        "htmlDate": _html_date,
        "htmlDateInZone": _html_date_in_zone,
    }
