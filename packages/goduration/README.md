# goduration

`goduration` provides immutable, typed duration objects with nanosecond
precision. It offers two explicit APIs:

- `goduration.go` reproduces Go `time.Duration` behavior where compatibility
  matters.
- `goduration.python` keeps the same convenient object-oriented API while
  following Python numeric and standard-library conventions.

Top-level imports default to the Go-compatible API. There is no global mode
switch, so different parts of one application can safely use different
surfaces, including across threads and asyncio tasks.

The package is developed inside the pygotpl workspace and released as an
independent distribution.

## Installation

Install the standalone package from PyPI:

```console
python -m pip install goduration
```

The installed package is pure Python, typed with a `py.typed` marker, and has no
runtime dependencies.

## Which API Should I Use?

Use the Go surface when values must match Go programs, Go template functions,
Sprig, serialized Go duration text, or signed 64-bit overflow behavior.

```python
from goduration.go import Duration
```

Use the Python surface for ordinary Python application code, especially when
you want arbitrary-size integers, Python float and Decimal rounding,
`datetime.timedelta` arithmetic, or idiomatic Python exceptions.

```python
from goduration.python import Duration
```

For the common Go-compatible case, use the shorter top-level import:

```python
from goduration import Duration
```

## Behavior at a Glance

| Behavior | Go surface | Python surface |
| --- | --- | --- |
| Import | `goduration.go` or top level | `goduration.python` |
| Integer range | Signed 64-bit nanoseconds | Arbitrary-size integer nanoseconds |
| Duration text | Go `time.ParseDuration` behavior | Same readable units, exact Decimal accumulation |
| Numeric conversion | Truncates fractional nanoseconds | Rounds fractional nanoseconds, ties to even |
| `round()` ties | Away from zero | To even |
| Microsecond and millisecond totals | Integers truncated toward zero | Fraction-preserving floats |
| `timedelta` output | Rejects precision loss by default | Rounds to microseconds, ties to even |
| `timedelta` arithmetic | Explicit conversion | Supported directly |
| Parsing errors | `DurationParseError` with Go-style text | Idiomatic `ValueError` |
| Construction overflow | Raises outside the Go range | No package-defined integer limit |
| Arithmetic overflow | Wraps as signed `int64` | Uses arbitrary-size integers |
| Duration division | Integer `Duration` quotient | Floating-point ratio |
| Modulo | Go truncating remainder | Python floor-division remainder |

Both surfaces are immutable, ordered, hashable, and measured internally in
integer nanoseconds. Both support parsing, named constructors, arithmetic,
rounding, truncation, compact strings, total-unit accessors, and `timedelta`
conversion. Ratios are intentionally Python-surface behavior.

## Common API Reference

| API | Purpose |
| --- | --- |
| `Duration(nanoseconds)` | Construct directly from integer nanoseconds. |
| `Duration.parse(text)` | Parse a signed sequence of duration components. |
| `from_nanoseconds(value)` | Construct from an int, float, or Decimal. |
| `from_microseconds(value)` | Construct from microseconds. |
| `from_milliseconds(value)` | Construct from milliseconds. |
| `from_seconds(value)` | Construct from seconds. |
| `from_minutes(value)` | Construct from minutes. |
| `from_hours(value)` | Construct from hours. |
| `from_days(value)` | Python surface: construct from days. |
| `from_weeks(value)` | Python surface: construct from weeks. |
| `from_timedelta(value)` | Convert a `datetime.timedelta`. |
| `round(multiple)` | Round to a duration multiple using surface-specific ties. |
| `truncate(multiple)` | Truncate toward zero to a duration multiple. |
| `total_nanoseconds()` | Return exact integer nanoseconds. |
| `total_microseconds()` | Return microseconds using the selected surface policy. |
| `total_milliseconds()` | Return milliseconds using the selected surface policy. |
| `total_seconds()` | Return seconds as a float. |
| `total_minutes()` | Return minutes as a float. |
| `total_hours()` | Return hours as a float. |
| `total_days()` | Python surface: return days as a float. |
| `total_weeks()` | Python surface: return weeks as a float. |
| `to_timedelta(...)` | Convert to Python's microsecond-resolution duration. |
| `str(duration)` | Produce a compact duration string. |

Both surfaces export `NANOSECOND`, `MICROSECOND`, `MILLISECOND`, `SECOND`,
`MINUTE`, and `HOUR` as typed duration constants. The Go surface additionally
exports its signed 64-bit bounds. The Python surface additionally exports
`DAY` and `WEEK`.

## Go-Compatible API

### Parse and Format

The parser accepts the Go duration units `ns`, `us`, `µs`, `μs`, `ms`, `s`,
`m`, and `h`. Components can be combined and may contain fractions.

```python
from goduration.go import Duration

duration = Duration.parse("2h45m6.25s")

assert duration.nanoseconds == 9_906_250_000_000
assert str(duration) == "2h45m6.25s"
assert Duration.parse("-500ms").nanoseconds == -500_000_000
```

Days are not part of Go's duration grammar:

```python
from goduration.go import Duration, DurationParseError

try:
    Duration.parse("1d")
except DurationParseError as error:
    assert str(error).startswith("time: unknown unit")
```

Go-compatible parsing includes Go's float64 fraction behavior and signed
64-bit range checks. This matters for high-precision edge cases, not just large
whole numbers.

### Construct Values

Named constructors make the unit explicit:

```python
from decimal import Decimal

from goduration.go import Duration

timeout = Duration.from_seconds(2.5)
interval = Duration.from_milliseconds(Decimal("12.5"))
tiny = Duration.from_nanoseconds(7)

assert str(timeout) == "2.5s"
assert str(interval) == "12.5ms"
assert tiny.nanoseconds == 7
```

You can also construct directly from integer nanoseconds:

```python
from goduration.go import Duration

duration = Duration(1_500_000_000)
assert str(duration) == "1.5s"
```

Direct construction requires an integer. Use a named constructor when the
input is a float or Decimal.

### Constants and Bounds

Typed unit constants are available from nanoseconds through hours:

```python
from goduration.go import HOUR, MILLISECOND, MINUTE, SECOND

assert HOUR == 60 * MINUTE
assert MINUTE == 60 * SECOND
assert 250 * MILLISECOND == SECOND / 4
```

The Go surface also exports `MIN_NANOSECONDS`, `MAX_NANOSECONDS`,
`MIN_DURATION`, and `MAX_DURATION`.

```python
from goduration.go import MAX_DURATION, MIN_DURATION, NANOSECOND

assert MAX_DURATION + NANOSECOND == MIN_DURATION
```

This wraparound is Go's runtime `int64` behavior. Direct construction and text
parsing still reject values outside the signed 64-bit range.

### Arithmetic

Duration arithmetic is object-oriented:

```python
from goduration.go import Duration, MILLISECOND, SECOND

duration = Duration.parse("1.5s")

assert duration + MILLISECOND == Duration.parse("1.501s")
assert duration - SECOND == Duration.parse("500ms")
assert -duration == Duration.parse("-1.5s")
assert abs(-duration) == duration
assert duration * 2 == Duration.parse("3s")
assert duration / 2 == Duration.parse("750ms")
assert duration / Duration.parse("500ms") == Duration(3)
assert 5 * SECOND % (2 * SECOND) == SECOND
```

Integer multiplication and division return durations and use signed-64-bit
wraparound. Dividing one duration by another also returns a duration containing
Go's integer quotient. Modulo returns Go's truncating remainder. Division or
modulo by zero raises `ZeroDivisionError`.

### Round and Truncate

`round()` uses Go's ties-away-from-zero rule. `truncate()` always moves toward
zero.

```python
from goduration.go import Duration, MINUTE

assert Duration.parse("2m30s").round(MINUTE) == Duration.parse("3m")
assert Duration.parse("-2m30s").round(MINUTE) == Duration.parse("-3m")
assert Duration.parse("10m10s").truncate(3 * MINUTE) == Duration.parse("9m")
```

### Read Totals

```python
from goduration.go import Duration

duration = Duration.parse("1.500001ms")

assert duration.total_nanoseconds() == 1_500_001
assert duration.total_microseconds() == 1_500
assert duration.total_milliseconds() == 1
assert duration.total_seconds() == 0.001500001
```

The integer microsecond and millisecond accessors truncate toward zero, matching
the Go-oriented fixed-unit interpretation.

### Work with `datetime.timedelta`

Converting from `timedelta` is exact because `timedelta` has microsecond
precision:

```python
from datetime import timedelta

from goduration.go import Duration

duration = Duration.from_timedelta(timedelta(seconds=1, microseconds=2))
assert duration.nanoseconds == 1_000_002_000
```

Converting back rejects hidden nanosecond loss by default:

```python
from goduration.go import Duration

duration = Duration(1_001)

try:
    duration.to_timedelta()
except ValueError as error:
    assert "precision" in str(error)

rounded_toward_zero = duration.to_timedelta(allow_precision_loss=True)
assert rounded_toward_zero.microseconds == 1
```

## Python-Native API

The Python surface retains the useful duration object without carrying Go's
integer-width and rounding policies into ordinary Python code.

### Arbitrary-Size Durations

```python
from goduration.python import Duration

duration = Duration.parse("100000000000000000000h")

assert duration.nanoseconds > 2**63
assert duration + Duration(1) == Duration(duration.nanoseconds + 1)
```

There is no package-defined integer limit. Limits can still come from Python or
from a target type during explicit conversion.

### Python Numeric Rounding

Named constructors accept `int`, `float`, and `Decimal`. Fractional
nanoseconds use Python's round-half-to-even rule:

```python
from decimal import Decimal

from goduration.python import Duration

assert Duration.from_nanoseconds(1.5).nanoseconds == 2
assert Duration.from_nanoseconds(2.5).nanoseconds == 2
assert Duration.from_nanoseconds(Decimal("3.5")).nanoseconds == 4
```

Float inputs are interpreted as their exact binary float values before the
final rounding step. Decimal inputs retain decimal precision.

Text parsing accumulates every component exactly and rounds the complete value
once:

```python
from goduration.python import Duration

assert Duration.parse("0.5ns0.5ns").nanoseconds == 1
```

This deliberately differs from Go's per-component fraction handling.

### Python Arithmetic and `timedelta`

The Python surface accepts `timedelta` directly in addition and subtraction:

```python
from datetime import timedelta

from goduration.python import Duration

duration = Duration.from_seconds(1.5)

assert duration + timedelta(milliseconds=1) == Duration.from_seconds(1.501)
assert timedelta(seconds=2) - duration == Duration.from_seconds(0.5)
```

Scalar arithmetic follows the same round-half-even nanosecond policy as the
constructors:

```python
from goduration.python import Duration

duration = Duration.from_seconds(1.5)

assert duration * 1.5 == Duration.from_seconds(2.25)
assert duration / 2 == Duration.from_seconds(0.75)
assert duration / Duration.from_milliseconds(500) == 3.0
```

Python floor division and modulo follow Python integer and `timedelta`
conventions. Zero durations are false, durations convert to their exact integer
nanosecond count with `int()`, and `sum()` works without a special start value.

### Days and Weeks

Days and weeks are Python conveniences, not Go duration text units:

```python
from goduration.python import DAY, WEEK, Duration

assert Duration.from_days(1.5) == 36 * Duration.from_hours(1)
assert Duration.from_weeks(2) == 2 * WEEK
assert WEEK == 7 * DAY
```

### Python Round and Truncate

Python rounding uses ties to even:

```python
from goduration.python import Duration, MICROSECOND

assert Duration(2_500).round(MICROSECOND) == Duration(2_000)
assert Duration(3_500).round(MICROSECOND) == Duration(4_000)
assert Duration(-2_500).round(MICROSECOND) == Duration(-2_000)
assert Duration(3_999).truncate(MICROSECOND) == Duration(3_000)
```

This is one of the most visible differences from the Go surface.

### Fraction-Preserving Totals

```python
from goduration.python import Duration

duration = Duration(-1_500_001)

assert duration.total_microseconds() == -1500.001
assert duration.total_milliseconds() == -1.500001
assert duration.total_seconds() == -0.001500001
```

`total_nanoseconds()` remains an integer because nanoseconds are the internal
storage unit.

### Python `timedelta` Conversion

`timedelta` stores microseconds, so Python-surface conversion rounds nanoseconds
to microseconds using ties to even:

```python
from datetime import timedelta

from goduration.python import Duration

assert Duration(1_500).to_timedelta() == timedelta(microseconds=2)
assert Duration(2_500).to_timedelta() == timedelta(microseconds=2)
assert Duration(-1_500).to_timedelta() == timedelta(microseconds=-2)
```

## Converting Between APIs

Conversion is always explicit. Moving from Go to Python is lossless:

```python
from goduration.go import Duration as GoDuration
from goduration.python import Duration as PythonDuration

go_duration = GoDuration.parse("1.5s")
python_duration = PythonDuration.from_go(go_duration)

assert python_duration.nanoseconds == go_duration.nanoseconds
```

Moving back checks the Go signed 64-bit range:

```python
from goduration.python import Duration as PythonDuration

small = PythonDuration.from_seconds(1.5)
assert str(small.to_go()) == "1.5s"

try:
    PythonDuration(2**100).to_go()
except OverflowError:
    pass
```

The package never clamps, wraps, or silently changes surface during conversion.

## Shared Properties

Values from both surfaces are immutable and safe to reuse:

```python
from goduration.python import Duration

duration = Duration.from_seconds(2)
mapping = {duration: "timeout"}

assert mapping[Duration.from_seconds(2)] == "timeout"
assert duration > Duration.from_seconds(1)
```

Go and Python duration objects are intentionally different types. Compare or
combine them only after explicit conversion.

## Relationship to gotpl and Sprig

gotpl imports `goduration.go` explicitly for its default Go and Sprig
compatibility profiles. Sprig input coercion, template registry names, clocks,
and compatibility error translation remain gotpl responsibilities.

Using `goduration.python` does not change gotpl globally. Convert values
explicitly when crossing between a Python-native application boundary and a
Go-compatible template integration.

## Development and Benchmarks

Run the standalone test and quality gates:

```console
uv run --directory packages/goduration --frozen pytest -q
uv run --directory packages/goduration --frozen ruff check .
uv run --directory packages/goduration --frozen pyright
```

Compare the two surfaces on shared operations:

```console
uv run --directory packages/goduration --frozen python \
  benchmarks/compare_surfaces.py
```

See [Semantic Surfaces](docs/semantics.md) for the compact behavior matrix and
precision policy.

## License

Copyright 2026 Revolution1. Licensed under the
[Apache License 2.0](LICENSE).
