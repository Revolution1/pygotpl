"""Python-native time values with submicrosecond precision."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta, tzinfo
from functools import total_ordering
from typing import overload

from goduration.python import Duration

from .go import Time as GoTime

_NANOSECONDS_PER_MICROSECOND = 1_000


def _timedelta_nanoseconds(value: timedelta) -> int:
    return (
        value.days * 86_400_000_000_000
        + value.seconds * 1_000_000_000
        + value.microseconds * 1_000
    )


@total_ordering
@dataclass(frozen=True, slots=True, eq=False)
class Time:
    """A Python datetime plus an exact submicrosecond nanosecond remainder."""

    datetime: datetime
    submicrosecond_nanoseconds: int = 0

    def __post_init__(self) -> None:
        if not isinstance(  # pyright: ignore[reportUnnecessaryIsInstance]
            self.datetime, datetime
        ):
            raise TypeError("value must be datetime.datetime")
        if isinstance(self.submicrosecond_nanoseconds, bool) or not isinstance(  # pyright: ignore[reportUnnecessaryIsInstance]
            self.submicrosecond_nanoseconds, int
        ):
            raise TypeError("submicrosecond nanoseconds must be an integer")
        if not 0 <= self.submicrosecond_nanoseconds < _NANOSECONDS_PER_MICROSECOND:
            raise ValueError("submicrosecond nanoseconds must be between 0 and 999")

    @classmethod
    def from_datetime(cls, value: datetime) -> Time:
        return cls(value)

    @classmethod
    def now(cls, timezone: tzinfo | None = None) -> Time:
        return cls(datetime.now(timezone))

    @classmethod
    def from_timestamp(
        cls, timestamp: int | float, timezone: tzinfo | None = None
    ) -> Time:
        if isinstance(timestamp, bool) or not isinstance(  # pyright: ignore[reportUnnecessaryIsInstance]
            timestamp, (int, float)
        ):
            raise TypeError("timestamp must be an int or float")
        return cls(datetime.fromtimestamp(timestamp, timezone))

    def timestamp(self) -> float:
        return self.datetime.timestamp() + self.submicrosecond_nanoseconds / 1e9

    @classmethod
    def from_go(cls, value: GoTime) -> Time:
        if not isinstance(  # pyright: ignore[reportUnnecessaryIsInstance]
            value, GoTime
        ):
            raise TypeError("value must be gotime.go.Time")
        try:
            base = datetime.fromtimestamp(value.unix_seconds, UTC).replace(
                microsecond=value.nanosecond // 1_000
            )
        except (OverflowError, OSError, ValueError) as error:
            raise OverflowError(
                "Go time is outside datetime's supported range"
            ) from error
        return cls(
            base.astimezone(value.location.tzinfo),
            value.nanosecond % 1_000,
        )

    def to_go(self) -> GoTime:
        base = GoTime.from_datetime(self.datetime)
        return GoTime.from_unix(
            base.unix_seconds,
            base.nanosecond + self.submicrosecond_nanoseconds,
            location=base.location,
        )

    def to_datetime(self, *, allow_precision_loss: bool = False) -> datetime:
        if self.submicrosecond_nanoseconds and not allow_precision_loss:
            raise ValueError("conversion would lose nanosecond precision")
        return self.datetime

    def in_timezone(self, location: tzinfo) -> Time:
        return Time(
            self.datetime.astimezone(location),
            self.submicrosecond_nanoseconds,
        )

    def add(self, duration: Duration) -> Time:
        if not isinstance(  # pyright: ignore[reportUnnecessaryIsInstance]
            duration, Duration
        ):
            raise TypeError("duration must be goduration.python.Duration")
        microseconds, remainder = divmod(
            self.submicrosecond_nanoseconds + duration.nanoseconds,
            _NANOSECONDS_PER_MICROSECOND,
        )
        return Time(
            self.datetime + timedelta(microseconds=microseconds),
            remainder,
        )

    def subtract(self, other: Time) -> Duration:
        if not isinstance(  # pyright: ignore[reportUnnecessaryIsInstance]
            other, Time
        ):
            raise TypeError("other must be gotime.python.Time")
        return Duration(
            _timedelta_nanoseconds(self.datetime - other.datetime)
            + self.submicrosecond_nanoseconds
            - other.submicrosecond_nanoseconds
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Time):
            return NotImplemented
        return self.datetime == other.datetime and (
            self.submicrosecond_nanoseconds == other.submicrosecond_nanoseconds
        )

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, Time):
            return NotImplemented
        if self.datetime != other.datetime:
            return self.datetime < other.datetime
        return self.submicrosecond_nanoseconds < other.submicrosecond_nanoseconds

    def __hash__(self) -> int:
        return hash((self.datetime, self.submicrosecond_nanoseconds))

    def __add__(self, other: object) -> Time:
        if isinstance(other, Duration):
            return self.add(other)
        if isinstance(other, timedelta):
            return Time(
                self.datetime + other,
                self.submicrosecond_nanoseconds,
            )
        return NotImplemented

    def __radd__(self, other: object) -> Time:
        return self.__add__(other)

    @overload
    def __sub__(self, other: Time) -> Duration: ...

    @overload
    def __sub__(self, other: Duration) -> Time: ...

    @overload
    def __sub__(self, other: timedelta) -> Time: ...

    def __sub__(self, other: object) -> Duration | Time:
        if isinstance(other, Time):
            return self.subtract(other)
        if isinstance(other, Duration):
            return self.add(-other)
        if isinstance(other, timedelta):
            return Time(
                self.datetime - other,
                self.submicrosecond_nanoseconds,
            )
        return NotImplemented


from ._python_schedule import (  # noqa: E402
    AsyncTicker,
    AsyncTimer,
    Ticker,
    Timer,
    sleep,
    sleep_async,
    timeout_at,
    wait_until,
)

__all__ = [
    "AsyncTicker",
    "AsyncTimer",
    "Ticker",
    "Time",
    "Timer",
    "sleep",
    "sleep_async",
    "timeout_at",
    "wait_until",
]
