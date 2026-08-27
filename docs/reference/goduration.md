# goduration API

Install the standalone package with `pip install goduration`.

Top-level `goduration.Duration` is the Go-compatible surface. Import
`goduration.python.Duration` for Python-native arithmetic and unbounded numeric
behavior.

| Choose | When you need |
| --- | --- |
| `goduration.go` | Go parsing, signed 64-bit overflow, truncating unit accessors, and Go rounding ties |
| `goduration.python` | Arbitrary-size values, `Decimal`, `timedelta` arithmetic, ratios, and Python rounding |

```python
from goduration.go import Duration as GoDuration
from goduration.python import Duration as PythonDuration

go_timeout = GoDuration.parse("1.5s")
python_timeout = PythonDuration.from_seconds(1.5)

assert str(go_timeout) == "1.5s"
assert str(python_timeout) == "1.5s"
```

The APIs intentionally use separate imports rather than a mutable global mode.
The package's
[complete usage guide](https://github.com/Revolution1/pygotpl/blob/main/packages/goduration/README.md)
documents arithmetic, rounding, totals, `timedelta` conversion, errors, and
every difference between the surfaces.

## Go-compatible surface

::: goduration.go

## Python-native surface

::: goduration.python
