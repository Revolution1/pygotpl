"""Go-compatible time and location values."""

from __future__ import annotations

import json
import os
import re
import struct
import time as _time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC as DATETIME_UTC
from datetime import datetime, timedelta, tzinfo
from enum import IntEnum
from functools import total_ordering
from io import BytesIO
from typing import Self, overload
from zoneinfo import TZPATH, ZoneInfo, ZoneInfoNotFoundError

from goduration.go import (
    MAX_DURATION,
    MAX_NANOSECONDS,
    MIN_DURATION,
    MIN_NANOSECONDS,
    Duration,
)

from ._civil import (
    CivilTime,
    _zone_at,  # pyright: ignore[reportPrivateUsage]
    civil_from_unix,
    days_from_civil,
)
from ._layout import (
    ANSIC,
    DATE_ONLY,
    DATE_TIME,
    KITCHEN,
    LAYOUT,
    RFC822,
    RFC822Z,
    RFC850,
    RFC1123,
    RFC1123Z,
    RFC3339,
    RFC3339_NANO,
    RUBY_DATE,
    STAMP,
    STAMP_MICRO,
    STAMP_MILLI,
    STAMP_NANO,
    TIME_ONLY,
    UNIX_DATE,
    format_civil,
)
from ._layout_parse import LayoutParseFailure, ParsedLayout, parse_layout
from ._tzfile import abbreviation_offset, transition_bounds, transitions_from_data

_MIN_INT64 = -(1 << 63)
_MAX_INT64 = (1 << 63) - 1
_NANOSECONDS_PER_SECOND = 1_000_000_000
_NANOSECONDS_PER_DAY = 86_400 * _NANOSECONDS_PER_SECOND
_UNIX_TO_ZERO_SECONDS = 62_135_596_800
_EPOCH = datetime(1970, 1, 1, tzinfo=DATETIME_UTC)


class _GoIntEnum(IntEnum):
    @classmethod
    def _missing_(cls, value: object) -> Self | None:
        if isinstance(value, bool) or not isinstance(value, int):
            return None
        member = int.__new__(cls, value)
        member._name_ = f"_INVALID_{value}"
        member._value_ = value
        return member


class Month(_GoIntEnum):
    JANUARY = 1
    FEBRUARY = 2
    MARCH = 3
    APRIL = 4
    MAY = 5
    JUNE = 6
    JULY = 7
    AUGUST = 8
    SEPTEMBER = 9
    OCTOBER = 10
    NOVEMBER = 11
    DECEMBER = 12

    def __str__(self) -> str:
        if 1 <= int(self) <= 12:
            return self.name.title()
        return f"%!Month({int(self)})"


class Weekday(_GoIntEnum):
    SUNDAY = 0
    MONDAY = 1
    TUESDAY = 2
    WEDNESDAY = 3
    THURSDAY = 4
    FRIDAY = 5
    SATURDAY = 6

    def __str__(self) -> str:
        if 0 <= int(self) <= 6:
            return self.name.title()
        return f"%!Weekday({int(self)})"


class LocationError(ValueError):
    """Report a Go-compatible location loading failure."""


class ParseError(ValueError):
    """A structured Go-compatible time layout parsing error."""

    def __init__(
        self,
        layout: str,
        value: str,
        layout_element: str,
        value_element: str,
        message: str = "",
    ) -> None:
        self.layout = layout
        self.value = value
        self.layout_element = layout_element
        self.value_element = value_element
        self.message = message
        super().__init__(str(self))

    def __str__(self) -> str:
        result = f"parsing time {_go_quote(self.value)} as {_go_quote(self.layout)}"
        if self.message:
            return result + self.message
        return (
            result
            + f": cannot parse {_go_quote(self.value_element)}"
            + f" as {_go_quote(self.layout_element)}"
        )


def _go_quote(value: str) -> str:
    output = ['"']
    for byte in value.encode():
        if byte >= 0x80 or byte < 0x20:
            output.append(f"\\x{byte:02x}")
        elif byte in (ord('"'), ord("\\")):
            output.extend(("\\", chr(byte)))
        else:
            output.append(chr(byte))
    output.append('"')
    return "".join(output)


class _FixedOffset(tzinfo):
    """A fixed offset without datetime.timezone's 24-hour constructor limit."""

    __slots__ = ("_name", "_offset")

    def __init__(self, name: str, offset_seconds: int) -> None:
        self._name = name
        self._offset = timedelta(seconds=offset_seconds)

    def utcoffset(self, value: datetime | None) -> timedelta:
        del value
        return self._offset

    def dst(self, value: datetime | None) -> timedelta:
        del value
        return timedelta(0)

    def tzname(self, value: datetime | None) -> str:
        del value
        return self._name


@dataclass(frozen=True, slots=True, eq=False)
class Location:
    """An immutable named time-zone location."""

    name: str
    _tzinfo: tzinfo = field(repr=False)
    _fixed_offset_seconds: int | None = field(default=None, repr=False)
    _transitions: tuple[int, ...] | None = field(default=None, repr=False)

    @classmethod
    def load(cls, name: str) -> Location:
        if not isinstance(name, str):  # pyright: ignore[reportUnnecessaryIsInstance]
            raise TypeError("location name must be a string")
        if name in {"", "UTC"}:
            return UTC
        if name == "Local":
            return LOCAL
        if not name or name.startswith(("/", "\\")) or ".." in name:
            raise LocationError(f"time: invalid location name {name}")
        try:
            return cls(name, ZoneInfo(name))
        except ZoneInfoNotFoundError as error:
            raise LocationError(f"unknown time zone {name}") from error

    @classmethod
    def fixed(cls, name: str, offset_seconds: int) -> Location:
        if not isinstance(  # pyright: ignore[reportUnnecessaryIsInstance]
            offset_seconds, int
        ) or isinstance(offset_seconds, bool):
            raise TypeError("location offset must be an integer")
        return cls(name, _FixedOffset(name, offset_seconds), offset_seconds)

    @classmethod
    def from_tzdata(cls, name: str, data: bytes) -> Location:
        """Load a location from IANA TZif bytes without filesystem lookup."""

        if not isinstance(name, str):  # pyright: ignore[reportUnnecessaryIsInstance]
            raise TypeError("location name must be a string")
        if not isinstance(data, bytes):  # pyright: ignore[reportUnnecessaryIsInstance]
            raise TypeError("data must be bytes")
        try:
            transitions = transitions_from_data(data)
            value = ZoneInfo.from_file(BytesIO(data), key=name)
        except (OSError, ValueError, EOFError) as error:
            raise LocationError("malformed time zone information") from error
        return cls(name, value, None, transitions)

    @classmethod
    def from_tzinfo(cls, value: tzinfo, *, name: str | None = None) -> Location:
        if not isinstance(  # pyright: ignore[reportUnnecessaryIsInstance]
            value, tzinfo
        ):
            raise TypeError("value must be datetime.tzinfo")
        if value is DATETIME_UTC:
            return UTC
        if value is LOCAL.tzinfo:
            return LOCAL
        if isinstance(value, ZoneInfo):
            return cls(value.key, value)
        return cls(name or value.tzname(None) or "Local", value)

    @property
    def tzinfo(self) -> tzinfo:
        return self._tzinfo

    def _lookup(self, unix_seconds: int) -> tuple[str, int]:
        if self._fixed_offset_seconds is not None:
            return self.name, self._fixed_offset_seconds
        return _zone_at(self.tzinfo, unix_seconds)

    def __str__(self) -> str:
        return self.name


UTC = Location("UTC", DATETIME_UTC)


def _detect_local_tzinfo() -> tzinfo:
    configured = os.environ.get("TZ")
    if configured is not None:
        if not configured:
            return DATETIME_UTC
        name = configured.removeprefix(":")
        if name == "UTC":
            return DATETIME_UTC
        try:
            if os.path.isabs(name):
                with open(name, "rb") as source:
                    return ZoneInfo.from_file(source, key=name)
            return ZoneInfo(name)
        except (OSError, ValueError, ZoneInfoNotFoundError):
            return DATETIME_UTC
    try:
        path = os.path.realpath("/etc/localtime")
        for root in TZPATH:
            prefix = os.path.realpath(root) + os.sep
            if path.startswith(prefix):
                return ZoneInfo(path[len(prefix) :])
        with open("/etc/localtime", "rb") as source:
            return ZoneInfo.from_file(source, key="Local")
    except (OSError, ValueError, ZoneInfoNotFoundError):
        return datetime.now().astimezone().tzinfo or DATETIME_UTC


LOCAL = Location("Local", _detect_local_tzinfo())


def _integer(value: int, name: str) -> int:
    if isinstance(value, bool) or not isinstance(  # pyright: ignore[reportUnnecessaryIsInstance]
        value, int
    ):
        raise TypeError(f"{name} must be an integer")
    return value


def _int64(value: int, name: str) -> int:
    value = _integer(value, name)
    if not _MIN_INT64 <= value <= _MAX_INT64:
        raise OverflowError(f"{name} exceeds the signed 64-bit range")
    return value


def _signed_int64(value: int) -> int:
    return ((value + (1 << 63)) % (1 << 64)) - (1 << 63)


def _trunc_div(value: int, divisor: int) -> int:
    quotient = abs(value) // divisor
    return -quotient if value < 0 else quotient


def _datetime_unix_seconds(value: datetime) -> int:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Go-compatible time requires an aware datetime")
    delta = value.astimezone(DATETIME_UTC) - _EPOCH
    return delta.days * 86_400 + delta.seconds


@total_ordering
@dataclass(frozen=True, slots=True, eq=False)
class Time:
    """An immutable instant with nanosecond precision and a display location."""

    unix_seconds: int
    nanosecond: int = 0
    location: Location = UTC
    _monotonic_nanoseconds: int | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        _integer(self.unix_seconds, "Unix seconds")
        _integer(self.nanosecond, "nanosecond")
        if not 0 <= self.nanosecond < _NANOSECONDS_PER_SECOND:
            raise ValueError("nanosecond must be between 0 and 999999999")
        if not isinstance(  # pyright: ignore[reportUnnecessaryIsInstance]
            self.location, Location
        ):
            raise TypeError("location must be a gotime.go.Location")
        if self._monotonic_nanoseconds is not None:
            _integer(self._monotonic_nanoseconds, "monotonic nanoseconds")

    @classmethod
    def from_unix(
        cls,
        seconds: int,
        nanoseconds: int = 0,
        *,
        location: Location = LOCAL,
    ) -> Time:
        seconds = _int64(seconds, "Unix seconds")
        nanoseconds = _int64(nanoseconds, "nanoseconds")
        second_delta, normalized = divmod(nanoseconds, _NANOSECONDS_PER_SECOND)
        return cls(_signed_int64(seconds + second_delta), normalized, location)

    @classmethod
    def from_unix_milliseconds(
        cls, milliseconds: int, *, location: Location = LOCAL
    ) -> Time:
        milliseconds = _int64(milliseconds, "Unix milliseconds")
        seconds = _trunc_div(milliseconds, 1_000)
        remainder = milliseconds - seconds * 1_000
        return cls.from_unix(seconds, remainder * 1_000_000, location=location)

    @classmethod
    def from_unix_microseconds(
        cls, microseconds: int, *, location: Location = LOCAL
    ) -> Time:
        microseconds = _int64(microseconds, "Unix microseconds")
        seconds = _trunc_div(microseconds, 1_000_000)
        remainder = microseconds - seconds * 1_000_000
        return cls.from_unix(seconds, remainder * 1_000, location=location)

    @classmethod
    def from_components(
        cls,
        year: int,
        month: int | Month,
        day: int,
        hour: int,
        minute: int,
        second: int,
        nanosecond: int,
        location: Location,
    ) -> Time:
        values = (year, month, day, hour, minute, second, nanosecond)
        if any(
            isinstance(value, bool)
            or not isinstance(  # pyright: ignore[reportUnnecessaryIsInstance]
                value, int
            )
            for value in values
        ):
            raise TypeError("time components must be integers")
        if not isinstance(  # pyright: ignore[reportUnnecessaryIsInstance]
            location, Location
        ):
            raise TypeError("location must be a gotime.go.Location")

        year_delta, month_index = divmod(int(month) - 1, 12)
        normalized_year = year + year_delta
        normalized_month = month_index + 1
        day_nanoseconds = (
            (hour * 60 + minute) * 60 + second
        ) * _NANOSECONDS_PER_SECOND + nanosecond
        day_delta, day_remainder = divmod(day_nanoseconds, _NANOSECONDS_PER_DAY)
        local_days = (
            days_from_civil(normalized_year, normalized_month, 1) + day - 1 + day_delta
        )
        local_seconds = local_days * 86_400 + day_remainder // _NANOSECONDS_PER_SECOND
        normalized_nanosecond = day_remainder % _NANOSECONDS_PER_SECOND
        _, offset = location._lookup(  # pyright: ignore[reportPrivateUsage]
            local_seconds
        )
        unix_seconds = local_seconds - offset
        _, corrected_offset = location._lookup(  # pyright: ignore[reportPrivateUsage]
            unix_seconds
        )
        if corrected_offset != offset:
            unix_seconds = local_seconds - corrected_offset
        return cls(unix_seconds, normalized_nanosecond, location)

    @classmethod
    def from_datetime(cls, value: datetime) -> Time:
        if not isinstance(  # pyright: ignore[reportUnnecessaryIsInstance]
            value, datetime
        ):
            raise TypeError("value must be datetime.datetime")
        seconds = _datetime_unix_seconds(value)
        assert value.tzinfo is not None
        location = Location.from_tzinfo(value.tzinfo, name=value.tzname())
        return cls(seconds, value.microsecond * 1_000, location)

    @classmethod
    def parse(cls, layout: str, value: str) -> Time:
        return cls.parse_in_location(layout, value, UTC)

    @classmethod
    def parse_in_location(cls, layout: str, value: str, location: Location) -> Time:
        if not isinstance(  # pyright: ignore[reportUnnecessaryIsInstance]
            location, Location
        ):
            raise TypeError("location must be a gotime.go.Location")
        try:
            if layout in {RFC3339, RFC3339_NANO}:
                return _parse_rfc3339(value, location)
            parsed = parse_layout(layout, value)
        except ParseError:
            raise
        except LayoutParseFailure as error:
            raise ParseError(
                layout,
                value,
                error.layout_element,
                error.value_element,
                error.message,
            ) from error
        except ValueError as error:
            range_message = _clock_range_message(value)
            raise ParseError(
                layout,
                value,
                layout,
                value,
                range_message or f": {error}",
            ) from error
        return _time_from_parsed_layout(parsed, location)

    @classmethod
    def zero(cls) -> Time:
        return cls(-_UNIX_TO_ZERO_SECONDS, 0, UTC)

    @classmethod
    def now(
        cls,
        *,
        clock: Callable[[], datetime] | None = None,
        monotonic_clock: Callable[[], int] | None = None,
    ) -> Time:
        value = clock() if clock is not None else datetime.now().astimezone()
        if value.tzinfo is None or value.utcoffset() is None:
            value = value.replace(tzinfo=LOCAL.tzinfo)
        wall = cls.from_datetime(value)
        monotonic = (
            monotonic_clock()
            if monotonic_clock is not None
            else (_time.monotonic_ns() if clock is None else None)
        )
        return cls(
            wall.unix_seconds,
            wall.nanosecond,
            wall.location,
            monotonic,
        )

    @classmethod
    def since(
        cls,
        value: Time,
        *,
        clock: Callable[[], datetime] | None = None,
        monotonic_clock: Callable[[], int] | None = None,
    ) -> Duration:
        return cls.now(clock=clock, monotonic_clock=monotonic_clock).subtract(value)

    @classmethod
    def until(
        cls,
        value: Time,
        *,
        clock: Callable[[], datetime] | None = None,
        monotonic_clock: Callable[[], int] | None = None,
    ) -> Duration:
        return value.subtract(cls.now(clock=clock, monotonic_clock=monotonic_clock))

    def civil(self) -> CivilTime:
        fixed_zone = (
            (
                self.location.name,
                self.location._fixed_offset_seconds,  # pyright: ignore[reportPrivateUsage]
            )
            if self.location._fixed_offset_seconds  # pyright: ignore[reportPrivateUsage]
            is not None
            else None
        )
        return civil_from_unix(
            self.unix_seconds,
            self.nanosecond,
            self.location.tzinfo,
            fixed_zone=fixed_zone,
        )

    @property
    def year(self) -> int:
        return self.civil().year

    @property
    def month(self) -> Month:
        return Month(self.civil().month)

    @property
    def day(self) -> int:
        return self.civil().day

    @property
    def hour(self) -> int:
        return self.civil().hour

    @property
    def minute(self) -> int:
        return self.civil().minute

    @property
    def second(self) -> int:
        return self.civil().second

    @property
    def weekday(self) -> Weekday:
        return Weekday(self.civil().weekday)

    @property
    def year_day(self) -> int:
        return self.civil().year_day

    def date(self) -> tuple[int, Month, int]:
        civil = self.civil()
        return civil.year, Month(civil.month), civil.day

    def clock(self) -> tuple[int, int, int]:
        civil = self.civil()
        return civil.hour, civil.minute, civil.second

    def iso_week(self) -> tuple[int, int]:
        """Return the ISO 8601 week-numbering year and week."""

        civil = self.civil()
        days = days_from_civil(civil.year, civil.month, civil.day)
        monday_weekday = (civil.weekday + 6) % 7
        thursday = civil_from_unix(
            (days + 3 - monday_weekday) * 86_400,
            0,
            DATETIME_UTC,
        )
        return thursday.year, (thursday.year_day - 1) // 7 + 1

    def is_zero(self) -> bool:
        return (self.unix_seconds, self.nanosecond) == (
            -_UNIX_TO_ZERO_SECONDS,
            0,
        )

    def in_location(self, location: Location) -> Time:
        if not isinstance(  # pyright: ignore[reportUnnecessaryIsInstance]
            location, Location
        ):
            raise TypeError("location must be a gotime.go.Location")
        return Time(self.unix_seconds, self.nanosecond, location)

    def utc(self) -> Time:
        return self.in_location(UTC)

    def local(self) -> Time:
        return self.in_location(LOCAL)

    def zone(self) -> tuple[str, int]:
        civil = self.civil()
        return civil.zone_name, civil.offset_seconds

    def zone_bounds(self) -> tuple[Time, Time]:
        """Return the beginning and end of the active zone interval."""

        start, end = transition_bounds(
            self.location.tzinfo,
            self.unix_seconds,
            transitions=self.location._transitions,  # pyright: ignore[reportPrivateUsage]
        )
        return (
            Time.zero()
            if start is None
            else Time.from_unix(start, location=self.location),
            Time.zero() if end is None else Time.from_unix(end, location=self.location),
        )

    def format(self, layout: str) -> str:
        if not isinstance(  # pyright: ignore[reportUnnecessaryIsInstance]
            layout, str
        ):
            raise TypeError("layout must be a string")
        return format_civil(self.civil(), layout)

    def append_format(self, prefix: bytes, layout: str) -> bytes:
        if not isinstance(prefix, bytes):  # pyright: ignore[reportUnnecessaryIsInstance]
            raise TypeError("prefix must be bytes")
        return prefix + self.format(layout).encode()

    def go_string(self) -> str:
        civil = self.civil()
        if self.location is UTC:
            location = "time.UTC"
        elif self.location is LOCAL:
            location = "time.Local"
        else:
            location = f"time.Location({_go_quote(self.location.name)})"
        return (
            f"time.Date({civil.year}, time.{Month(civil.month)}, {civil.day}, "
            f"{civil.hour}, {civil.minute}, {civil.second}, {civil.nanosecond}, "
            f"{location})"
        )

    def is_dst(self) -> bool:
        if (
            self.location._fixed_offset_seconds  # pyright: ignore[reportPrivateUsage]
            is not None
        ):
            return False
        return bool(self.to_datetime().dst())

    def to_datetime(self) -> datetime:
        try:
            utc_value = _EPOCH + timedelta(
                seconds=self.unix_seconds,
                microseconds=self.nanosecond // 1_000,
            )
            return utc_value.astimezone(self.location.tzinfo)
        except (OverflowError, ValueError) as error:
            raise OverflowError("time is outside datetime's supported range") from error

    def add(self, duration: Duration) -> Time:
        if not isinstance(  # pyright: ignore[reportUnnecessaryIsInstance]
            duration, Duration
        ):
            raise TypeError("duration must be goduration.go.Duration")
        second_delta, nanosecond = divmod(
            self.nanosecond + duration.nanoseconds,
            _NANOSECONDS_PER_SECOND,
        )
        monotonic = self._monotonic_nanoseconds
        if monotonic is not None:
            candidate = monotonic + duration.nanoseconds
            monotonic = candidate if _MIN_INT64 <= candidate <= _MAX_INT64 else None
        return Time(
            self.unix_seconds + second_delta,
            nanosecond,
            self.location,
            monotonic,
        )

    def add_date(self, years: int = 0, months: int = 0, days: int = 0) -> Time:
        years = _integer(years, "years")
        months = _integer(months, "months")
        days = _integer(days, "days")
        civil = self.civil()
        return Time.from_components(
            civil.year + years,
            civil.month + months,
            civil.day + days,
            civil.hour,
            civil.minute,
            civil.second,
            civil.nanosecond,
            self.location,
        )

    def truncate(self, duration: Duration) -> Time:
        if not isinstance(  # pyright: ignore[reportUnnecessaryIsInstance]
            duration, Duration
        ):
            raise TypeError("duration must be goduration.go.Duration")
        if duration.nanoseconds <= 0:
            return self
        total = (
            self.unix_seconds + _UNIX_TO_ZERO_SECONDS
        ) * _NANOSECONDS_PER_SECOND + self.nanosecond
        rounded = (total // duration.nanoseconds) * duration.nanoseconds
        seconds, nanosecond = divmod(rounded, _NANOSECONDS_PER_SECOND)
        return Time(seconds - _UNIX_TO_ZERO_SECONDS, nanosecond, self.location)

    def round(self, duration: Duration) -> Time:
        if not isinstance(  # pyright: ignore[reportUnnecessaryIsInstance]
            duration, Duration
        ):
            raise TypeError("duration must be goduration.go.Duration")
        if duration.nanoseconds <= 0:
            return self
        total = (
            self.unix_seconds + _UNIX_TO_ZERO_SECONDS
        ) * _NANOSECONDS_PER_SECOND + self.nanosecond
        quotient, remainder = divmod(total, duration.nanoseconds)
        if remainder * 2 >= duration.nanoseconds:
            quotient += 1
        seconds, nanosecond = divmod(
            quotient * duration.nanoseconds, _NANOSECONDS_PER_SECOND
        )
        return Time(seconds - _UNIX_TO_ZERO_SECONDS, nanosecond, self.location)

    def subtract(self, other: Time) -> Duration:
        if not isinstance(  # pyright: ignore[reportUnnecessaryIsInstance]
            other, Time
        ):
            raise TypeError("other must be gotime.go.Time")
        if (
            self._monotonic_nanoseconds is not None
            and other._monotonic_nanoseconds is not None
        ):
            difference = self._monotonic_nanoseconds - other._monotonic_nanoseconds
        else:
            difference = (
                (self.unix_seconds - other.unix_seconds) * _NANOSECONDS_PER_SECOND
                + self.nanosecond
                - other.nanosecond
            )
        if difference < MIN_NANOSECONDS:
            return MIN_DURATION
        if difference > MAX_NANOSECONDS:
            return MAX_DURATION
        return Duration(difference)

    def equal(self, other: Time) -> bool:
        if not isinstance(  # pyright: ignore[reportUnnecessaryIsInstance]
            other, Time
        ):
            raise TypeError("other must be gotime.go.Time")
        if (
            self._monotonic_nanoseconds is not None
            and other._monotonic_nanoseconds is not None
        ):
            return self._monotonic_nanoseconds == other._monotonic_nanoseconds
        return (self.unix_seconds, self.nanosecond) == (
            other.unix_seconds,
            other.nanosecond,
        )

    def before(self, other: Time) -> bool:
        return self.compare(other) < 0

    def after(self, other: Time) -> bool:
        return self.compare(other) > 0

    def compare(self, other: Time) -> int:
        if not isinstance(  # pyright: ignore[reportUnnecessaryIsInstance]
            other, Time
        ):
            raise TypeError("other must be gotime.go.Time")
        if (
            self._monotonic_nanoseconds is not None
            and other._monotonic_nanoseconds is not None
        ):
            left = (self._monotonic_nanoseconds,)
            right = (other._monotonic_nanoseconds,)
        else:
            left = (self.unix_seconds, self.nanosecond)
            right = (other.unix_seconds, other.nanosecond)
        return (left > right) - (left < right)

    def unix(self) -> int:
        return self.unix_seconds

    def unix_milliseconds(self) -> int:
        return _signed_int64(self.unix_seconds * 1_000 + self.nanosecond // 1_000_000)

    def unix_microseconds(self) -> int:
        return _signed_int64(self.unix_seconds * 1_000_000 + self.nanosecond // 1_000)

    def unix_nanoseconds(self) -> int:
        return _signed_int64(
            self.unix_seconds * _NANOSECONDS_PER_SECOND + self.nanosecond
        )

    def marshal_binary(self) -> bytes:
        """Return Go ``time.Time.MarshalBinary`` wire bytes."""

        if self.location is UTC:
            offset_minutes = -1
            offset_seconds = 0
        else:
            _, offset = self.zone()
            offset_minutes = _trunc_div(offset, 60)
            offset_seconds = offset - offset_minutes * 60
            if not -32_768 <= offset_minutes <= 32_767 or offset_minutes == -1:
                raise ValueError("Time.MarshalBinary: unexpected zone offset")
        version = 2 if offset_seconds else 1
        internal_seconds = self.unix_seconds + _UNIX_TO_ZERO_SECONDS
        try:
            result = struct.pack(
                ">Bqi h",
                version,
                internal_seconds,
                self.nanosecond,
                offset_minutes,
            )
            if version == 2:
                result += struct.pack(">b", offset_seconds)
            return result
        except struct.error as error:
            raise ValueError("Time.MarshalBinary: time is out of range") from error

    def append_binary(self, prefix: bytes) -> bytes:
        if not isinstance(prefix, bytes):  # pyright: ignore[reportUnnecessaryIsInstance]
            raise TypeError("prefix must be bytes")
        return prefix + self.marshal_binary()

    @classmethod
    def unmarshal_binary(cls, data: bytes) -> Time:
        """Decode Go ``time.Time`` binary wire bytes into a new value."""

        if not isinstance(data, bytes):  # pyright: ignore[reportUnnecessaryIsInstance]
            raise TypeError("data must be bytes")
        if not data:
            raise ValueError("Time.UnmarshalBinary: no data")
        version = data[0]
        if version not in (1, 2):
            raise ValueError("Time.UnmarshalBinary: unsupported version")
        expected = 16 if version == 2 else 15
        if len(data) != expected:
            raise ValueError("Time.UnmarshalBinary: invalid length")
        internal_seconds, nanosecond, offset_minutes = struct.unpack(
            ">qi h", data[1:15]
        )
        offset = offset_minutes * 60
        if version == 2:
            offset += struct.unpack(">b", data[15:])[0]
        location = UTC if offset_minutes == -1 else Location.fixed("", offset)
        return cls(internal_seconds - _UNIX_TO_ZERO_SECONDS, nanosecond, location)

    def gob_encode(self) -> bytes:
        return self.marshal_binary()

    @classmethod
    def gob_decode(cls, data: bytes) -> Time:
        return cls.unmarshal_binary(data)

    def marshal_text(self) -> bytes:
        """Return Go RFC 3339 text serialization."""

        if not 0 <= self.year <= 9_999:
            raise ValueError("Time.MarshalText: year outside of range [0,9999]")
        _, offset = self.zone()
        if abs(offset) >= 24 * 60 * 60:
            raise ValueError("Time.MarshalText: timezone hour outside of range [0,23]")
        return self.format(RFC3339_NANO).encode()

    def append_text(self, prefix: bytes) -> bytes:
        if not isinstance(prefix, bytes):  # pyright: ignore[reportUnnecessaryIsInstance]
            raise TypeError("prefix must be bytes")
        return prefix + self.marshal_text()

    @classmethod
    def unmarshal_text(cls, data: bytes) -> Time:
        if not isinstance(data, bytes):  # pyright: ignore[reportUnnecessaryIsInstance]
            raise TypeError("data must be bytes")
        return cls.parse(RFC3339_NANO, data.decode())

    def marshal_json(self) -> bytes:
        """Return Go JSON serialization without ASCII rewriting."""

        try:
            text = self.marshal_text().decode()
        except ValueError as error:
            message = str(error).removeprefix("Time.MarshalText: ")
            raise ValueError(f"Time.MarshalJSON: {message}") from error
        return json.dumps(text, ensure_ascii=False, separators=(",", ":")).encode()

    @classmethod
    def unmarshal_json(cls, data: bytes) -> Time:
        if not isinstance(data, bytes):  # pyright: ignore[reportUnnecessaryIsInstance]
            raise TypeError("data must be bytes")
        try:
            value = json.loads(data)
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            raise ValueError(
                "Time.UnmarshalJSON: input is not a JSON string"
            ) from error
        if not isinstance(value, str):
            raise ValueError("Time.UnmarshalJSON: input is not a JSON string")
        return cls.parse(RFC3339_NANO, value)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Time):
            return NotImplemented
        return (
            self.unix_seconds == other.unix_seconds
            and self.nanosecond == other.nanosecond
            and self.location is other.location
            and self._monotonic_nanoseconds == other._monotonic_nanoseconds
        )

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, Time):
            return NotImplemented
        return self.compare(other) < 0

    def __hash__(self) -> int:
        return hash(
            (
                self.unix_seconds,
                self.nanosecond,
                id(self.location),
                self._monotonic_nanoseconds,
            )
        )

    def __str__(self) -> str:
        result = self.format("2006-01-02 15:04:05.999999999 -0700 MST")
        if self._monotonic_nanoseconds is None:
            return result
        magnitude = abs(self._monotonic_nanoseconds)
        seconds, nanoseconds = divmod(magnitude, _NANOSECONDS_PER_SECOND)
        sign = "+" if self._monotonic_nanoseconds >= 0 else "-"
        return f"{result} m={sign}{seconds}.{nanoseconds:09d}"

    def __add__(self, other: object) -> Time:
        if not isinstance(other, Duration):
            return NotImplemented
        return self.add(other)

    def __radd__(self, other: object) -> Time:
        return self.__add__(other)

    @overload
    def __sub__(self, other: Time) -> Duration: ...

    @overload
    def __sub__(self, other: Duration) -> Time: ...

    def __sub__(self, other: object) -> Duration | Time:
        if isinstance(other, Time):
            return self.subtract(other)
        if isinstance(other, Duration):
            return self.add(-other)
        return NotImplemented


_RFC3339_PATTERN = re.compile(
    r"^(\d{4})-(\d{2})-(\d{2})T(\d{1,2}):(\d{2}):(\d{2})"
    r"(?:[.,](\d+))?(Z|([+-])(\d{2}):(\d{2}))$"
)


def _parse_rfc3339(value: str, local: Location) -> Time:
    match = _RFC3339_PATTERN.fullmatch(value)
    if match is None:
        raise ValueError(f"cannot parse {value!r} as RFC3339 time")
    year, month, day, hour, minute, second = (
        int(component) for component in match.groups()[:6]
    )
    if (
        not 1 <= month <= 12
        or not 1 <= day <= _days_in_month(year, month)
        or not 0 <= hour < 24
        or not 0 <= minute < 60
        or not 0 <= second < 60
    ):
        raise ValueError(f"cannot parse {value!r} as RFC3339 time")
    fraction = match.group(7) or ""
    nanosecond = int(fraction[:9].ljust(9, "0")) if fraction else 0
    zone = match.group(8)
    if zone == "Z":
        offset = 0
        location = UTC
    else:
        zone_hour = int(match.group(10))
        zone_minute = int(match.group(11))
        if zone_hour > 24 or zone_minute > 60:
            raise ValueError(f"cannot parse {value!r} as RFC3339 time")
        offset = (zone_hour * 60 + zone_minute) * 60
        if match.group(9) == "-":
            offset = -offset
        local_seconds = (
            days_from_civil(year, month, day) * 86_400
            + hour * 3_600
            + minute * 60
            + second
        )
        unix_seconds = local_seconds - offset
        _, local_offset = local._lookup(  # pyright: ignore[reportPrivateUsage]
            unix_seconds
        )
        location = local if local_offset == offset else Location.fixed("", offset)
        return Time(unix_seconds, nanosecond, location)
    local_seconds = (
        days_from_civil(year, month, day) * 86_400 + hour * 3_600 + minute * 60 + second
    )
    return Time(local_seconds - offset, nanosecond, location)


def _time_from_parsed_layout(parsed: ParsedLayout, local: Location) -> Time:
    if parsed.zone_offset is None and parsed.zone_name is None:
        return Time.from_components(
            parsed.year,
            parsed.month,
            parsed.day,
            parsed.hour,
            parsed.minute,
            parsed.second,
            parsed.nanosecond,
            local,
        )
    local_seconds = (
        days_from_civil(parsed.year, parsed.month, parsed.day) * 86_400
        + parsed.hour * 3_600
        + parsed.minute * 60
        + parsed.second
    )
    offset = parsed.zone_offset
    if offset is None:
        assert parsed.zone_name is not None
        if parsed.zone_name == "UTC":
            offset = 0
        else:
            offset = _abbreviation_offset_for_parsed(local, parsed)
    unix_seconds = local_seconds - offset
    if parsed.zone_name == "UTC":
        result_location = UTC
    else:
        _, local_offset = local._lookup(  # pyright: ignore[reportPrivateUsage]
            unix_seconds
        )
        result_location = (
            local
            if local_offset == offset
            else Location.fixed(parsed.zone_name or "", offset)
        )
    return Time(unix_seconds, parsed.nanosecond, result_location)


def _abbreviation_offset_for_parsed(local: Location, parsed: ParsedLayout) -> int:
    assert parsed.zone_name is not None
    if 1 <= parsed.year <= 9_999:
        naive = datetime(
            parsed.year,
            parsed.month,
            parsed.day,
            parsed.hour,
            parsed.minute,
            parsed.second,
        )
        offset = abbreviation_offset(local.tzinfo, parsed.zone_name, naive)
        if offset is not None:
            return offset
    return 0


def _days_in_month(year: int, month: int) -> int:
    if month == 2:
        leap = year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)
        return 29 if leap else 28
    return 30 if month in {4, 6, 9, 11} else 31


def _clock_range_message(value: str) -> str:
    match = re.search(r"(?<!\d)(\d{1,2}):(\d{2}):(\d{2})(?!\d)", value)
    if match is None:
        return ""
    hour, minute, second = (int(item) for item in match.groups())
    if hour >= 24:
        return ": hour out of range"
    if minute >= 60:
        return ": minute out of range"
    if second >= 60:
        return ": second out of range"
    return ""


from ._go_schedule import (  # noqa: E402
    Ticker,
    Timer,
    after,
    after_func,
    new_ticker,
    new_timer,
    sleep,
    tick,
)

__all__ = [
    "ANSIC",
    "DATE_ONLY",
    "DATE_TIME",
    "KITCHEN",
    "LAYOUT",
    "LOCAL",
    "RFC822",
    "RFC822Z",
    "RFC850",
    "RFC1123",
    "RFC1123Z",
    "RFC3339",
    "RFC3339_NANO",
    "RUBY_DATE",
    "STAMP",
    "STAMP_MICRO",
    "STAMP_MILLI",
    "STAMP_NANO",
    "TIME_ONLY",
    "UNIX_DATE",
    "UTC",
    "CivilTime",
    "Location",
    "LocationError",
    "Month",
    "ParseError",
    "Ticker",
    "Time",
    "Timer",
    "Weekday",
    "after",
    "after_func",
    "new_ticker",
    "new_timer",
    "sleep",
    "tick",
]
