# gotime API

Top-level `gotime.Time` is the Go-compatible surface. Import
`gotime.python.Time` for the Python-native surface.

| Choose | When you need |
| --- | --- |
| `gotime.go` | Go layouts, locations, serialization, signed time behavior, and deterministic Go-shaped timers |
| `gotime.python` | `datetime`, `zoneinfo`, numeric timestamps, `timedelta`, and native asyncio scheduling |

```python
from gotime.go import RFC3339_NANO, UTC, Time

created = Time.from_components(2024, 7, 9, 13, 4, 5, 123_456_789, UTC)
assert created.format(RFC3339_NANO) == "2024-07-09T13:04:05.123456789Z"
```

Conversions between Go and Python surfaces are explicit. There is no global
mode switch. See the
[gotime usage guide](https://github.com/Revolution1/pygotpl/blob/main/packages/gotime/README.md)
for locations, precision, serialization, timers, and asyncio examples.

## Go-compatible surface

::: gotime.go

## Python-native surface

::: gotime.python
