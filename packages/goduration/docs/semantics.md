# Semantic Surfaces

`goduration` separates compatibility from Python convenience through explicit
modules. Top-level exports alias `goduration.go`; no mutable mode exists.

| Behavior | `goduration.go` | `goduration.python` |
| --- | --- | --- |
| Storage | Signed 64-bit integer nanoseconds | Arbitrary-size integer nanoseconds |
| Text grammar | Go `time.ParseDuration` | The same unit-oriented grammar |
| Decimal text | Go float64 fractional scaling and per-part truncation | Exact Decimal accumulation, then round half to even |
| Float constructors | Decimal text conversion with truncation to nanoseconds | Exact binary-float value rounded half to even |
| Decimal constructors | Truncation to nanoseconds | Round half to even |
| Construction overflow | Rejects values outside signed 64-bit | No package-defined integer bound |
| Arithmetic overflow | Wraps as Go `int64` | Uses arbitrary-size integers |
| Duration division | Integer quotient stored as `Duration` | Floating-point ratio |
| Modulo | Go remainder, with the dividend's sign | Python floor-division remainder |
| `round()` ties | Away from zero | To even |
| Total microseconds and milliseconds | Integers truncated toward zero | Fraction-preserving floats |
| `timedelta` output | Rejects precision loss by default | Rounds to Python microseconds, ties to even |
| Errors | Go-compatible parsing messages where applicable | Idiomatic `TypeError`, `ValueError`, and `ZeroDivisionError` |

Both values are immutable, ordered, hashable, and measured in nanoseconds.
Both support named constructors, arithmetic, rounding, truncation, compact
duration strings, and `datetime.timedelta` interoperability. The Python surface
provides duration ratios; the Go surface preserves Go's integer division.

## Explicit Conversion

Convert from Go to Python without precision loss:

```python
from goduration.go import Duration as GoDuration
from goduration.python import Duration as PythonDuration

value = PythonDuration.from_go(GoDuration.parse("2h30m"))
```

Conversion back to Go checks the signed-64-bit range:

```python
go_value = value.to_go()
```

An out-of-range Python duration raises `OverflowError`. Explicit conversion
never wraps, clamps, or silently changes surfaces. Arithmetic performed after
conversion on `goduration.go.Duration` follows Go's signed-64-bit wraparound.

## Python Numeric Policy

Python constructors accept `int`, `float`, and `Decimal`, excluding `bool`.
Integers remain exact. Floats are interpreted as their exact binary values,
then rounded to integer nanoseconds with Python's ties-to-even rule. Decimal
values retain decimal precision through the same final rounding step.

Parsing first accumulates every textual component exactly as Decimal
nanoseconds and rounds the complete result once. This makes expressions such as
`0.5ns0.5ns` equal one nanosecond on the Python surface, while the Go surface
retains Go's per-component behavior.
