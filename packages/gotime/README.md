# gotime

`gotime` provides immutable time and location values through two explicit
surfaces:

- `gotime.go` targets Go `time.Time` and `time.Location` compatibility.
- `gotime.python` follows Python `datetime` and `zoneinfo` conventions while
  preserving submicrosecond nanoseconds.

Top-level exports default to the Go surface. The package is extracted inside
the pygotpl workspace and is not yet a stable external release. The
current implementation includes the value, civil-time, location, Unix,
calendar arithmetic, ISO week, comparison, rounding, transition-bound,
formatting, parsing-foundation, diagnostic-string, and Go-compatible binary,
gob, text, and JSON serialization layers. `Time.now()` also records an
injectable monotonic reading and applies Go's preserve-or-strip rules for
instant, location, calendar, rounding, formatting, and wire operations. Both
surfaces include deterministic synchronous scheduling; the Python surface also
provides native asyncio sleep, deadline, timeout, timer, and ticker APIs. The
complete Go-shaped API is implemented. Exact platform-local timezone discovery
and civil years outside Python's representable `datetime` range have documented
portability limits; the package never silently clips those values.

The complete Go 1.27 API inventory and delivery order are tracked in
[`docs/api-scope.md`](docs/api-scope.md).

## Go-compatible values

Top-level imports default to the Go surface. Importing from `gotime.go` makes
that choice explicit:

```python
from goduration.go import HOUR
from gotime.go import RFC3339_NANO, UTC, Location, Time

created = Time.from_components(2024, 7, 9, 13, 4, 5, 123_456_789, UTC)
assert created.format(RFC3339_NANO) == "2024-07-09T13:04:05.123456789Z"

new_york = created.in_location(Location.load("America/New_York"))
assert new_york.zone() == ("EDT", -4 * 60 * 60)
assert (new_york + HOUR).subtract(new_york) == HOUR
```

`Time.parse()` and `Time.parse_in_location()` consume Go reference-time
layouts. Values preserve nanoseconds, support year zero, and are not limited
to `datetime`'s year range. Converting an unrepresentable value to `datetime`
raises `OverflowError` instead of silently clipping it.

Go-compatible wire helpers return bytes:

```python
encoded = created.marshal_binary()
assert Time.unmarshal_binary(encoded).equal(created)
assert created.marshal_json() == b'"2024-07-09T13:04:05.123456789Z"'
```

## Python-native values

The Python surface follows `datetime`, `timedelta`, timestamp, numeric, and
exception conventions. A submicrosecond remainder keeps conversion explicit:

```python
from datetime import UTC, datetime, timedelta

from goduration.python import Duration
from gotime.python import Time

value = Time(datetime(2024, 7, 9, 13, 4, 5, 123_456, tzinfo=UTC), 789)
later = value + Duration.from_seconds(1)
assert later - value == Duration.from_seconds(1)

# Precision loss must be requested when a nanosecond remainder exists.
standard = value.to_datetime(allow_precision_loss=True)
assert standard.microsecond == 123_456
assert value + timedelta(seconds=1) == later
```

Cross-surface conversion is explicit through `Time.from_go()` and `to_go()`.
There is no global compatibility-mode switch.

## Timers and asyncio

Go-shaped scheduling uses explicit `receive()` because Python has no Go
channel equivalent:

```python
from goduration.go import SECOND
from gotime.go import new_timer

event = new_timer(SECOND).receive()
```

Python-native scheduling accepts `Duration`, `timedelta`, or numeric seconds:

```python
from gotime.python import AsyncTicker, sleep_async

await sleep_async(0.1)

ticker = AsyncTicker(1.0)
first_tick = await anext(ticker)
ticker.stop()
```

`ManualClock` and injectable async sleepers make timer tests deterministic.
System clock readings keep wall and monotonic time separate; monotonic readings
are never serialized as Unix timestamps.

## License

Copyright 2026 Revolution1. Licensed under the
[Apache License 2.0](LICENSE).
