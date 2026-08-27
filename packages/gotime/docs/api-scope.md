# Go 1.27 Time API Scope

This document is the implementation ledger for `gotime`. The compatibility
reference is the pinned Go 1.27.0 checkout at `.references/go/src/time`.
Implementation work starts from the upstream implementation and tests; the
current pygotpl date helpers are migration inputs, not the definition of a
complete `gotime` API.

## Surface Policy

`gotime.go` preserves observable Go behavior, including normalization,
nanosecond precision, signed widths, calendar arithmetic, location lookup,
layout parsing and formatting, monotonic-clock rules, and serialization.

`gotime.python` exposes a similar object-oriented API while using Python
`datetime`, `date`, `time`, `timedelta`, `tzinfo`, `zoneinfo`, exceptions,
unbounded integers, protocols, and asyncio conventions. Cross-surface
conversion is always explicit. Top-level exports default to `gotime.go`.

Python names are idiomatic snake_case. Go names shown below identify behavior,
not a requirement to expose non-Pythonic method spelling.

## Value and Calendar API

| Go API group | Required Python API | Status |
| --- | --- | --- |
| `Time`, zero value | immutable `Time`, `Time.zero()` | Implemented with optional monotonic reading |
| `Month`, `Weekday` and constants | typed enums and constants | Implemented |
| `Date` | `Time.from_components(...)` with Go normalization | Implemented; oracle expansion pending |
| `Unix`, `UnixMilli`, `UnixMicro` | `from_unix`, `from_unix_milliseconds`, `from_unix_microseconds` | Implemented |
| `Now`, `Since`, `Until` | injectable wall and monotonic clocks | Implemented with independently injected clocks |
| `IsZero`, `Before`, `After`, `Compare`, `Equal` | named methods plus Python comparison operators | Implemented with Go monotonic fallback rules |
| `Date`, `Year`, `Month`, `Day`, `YearDay`, `Weekday`, `ISOWeek` | civil accessors and properties | Implemented with oracle coverage |
| `Clock`, `Hour`, `Minute`, `Second`, `Nanosecond` | clock accessors and properties | Implemented |
| `Add`, `Sub` | `Duration` arithmetic and operators | Implemented core |
| `AddDate` | normalized calendar arithmetic | Implemented; transition matrix pending |
| `Round`, `Truncate` | absolute-time rounding and truncation | Implemented; full boundary matrix pending |
| `Unix`, `UnixMilli`, `UnixMicro`, `UnixNano` | exact Unix-unit accessors | Implemented |
| `UTC`, `Local`, `In`, `Location` | immutable location conversion | Implemented core |
| `Zone`, `ZoneBounds`, `IsDST` | zone metadata and transition bounds | Implemented for fixed, UTC, recorded TZif transitions, and recurring future rules |

## Formatting and Parsing API

| Go API group | Required Python API | Status |
| --- | --- | --- |
| Go layout constants | all 20 constants from `Layout` through `TimeOnly` | Implemented |
| `Time.Format`, `AppendFormat` | `format` and buffer-oriented formatting | Implemented with upstream format and signed-year matrices |
| `Time.String`, `GoString` | compatible readable and diagnostic forms | Implemented with monotonic suffix and Go byte quoting |
| `Parse`, `ParseInLocation` | `Time.parse` and location-aware parsing | Package-owned parser implemented with upstream success, range, fraction, and zone matrices |
| `ParseError` | structured parse exception with Go-equivalent fields | Implemented with direct field and upstream error-category tests |
| RFC 3339 strict parsing | JSON/text parsing foundation | Implemented with Go 1.27 legacy permissiveness |

The layout implementation must cover every token, fractional separator,
timezone-seconds form, invalid layout, invalid value, and parse error tested in
Go's `format_test.go`. Sprig fallback behavior stays in pygotpl adapters.

## Locations and TZif

| Go API group | Required Python API | Status |
| --- | --- | --- |
| `UTC`, `Local` | explicit UTC and process-local locations | Implemented; dynamic local-source detection audit pending |
| `FixedZone` | arbitrary Go integer offsets | Implemented with package-owned fixed offsets; `datetime` conversion remains limited to offsets below 24 hours |
| `LoadLocation` | Go name validation and IANA lookup | Partial |
| `LoadLocationFromTZData` | independent TZif loading | Implemented with explicit and recurring transition bounds |
| historical and future transitions | Go first-zone and extension rules | Implemented for representable `ZoneInfo` years; extreme-year audit pending |

The Go surface cannot delegate semantic decisions entirely to `zoneinfo`:
Go's pre-transition selection, name validation, fixed-zone behavior, TZif
loading, and transition bounds require package-owned logic. The Python surface
may expose ordinary `tzinfo` and `ZoneInfo` objects directly.

## Serialization

The Go surface implements `AppendBinary`, `MarshalBinary`, `GobEncode`,
`MarshalJSON`, `MarshalText`, and their decoding counterparts. Monotonic
readings participate in instant operations but are stripped from location,
calendar, rounding, and wire-format results according to Go's rules. Because Python
immutable values do not use Go pointer receivers, decoders return a new
`Time`. Checked-in Go 1.27 vectors cover UTC, IANA zones, second-level fixed
offsets, ISO weeks, transition bounds, text, JSON, and both binary versions.
The owned RFC 3339 decoder supports year zero, legacy comma fractions, Go's
accepted `+24:00` and `+00:60` offsets, and truncation after nine fractional
digits. The remaining upstream invalid-input and error-text matrix is still an
open gate. Python-native JSON, pickle, and text helpers remain separate and
must not silently claim Go wire compatibility.

## Clocks, Timers, and Asyncio

Go also exports `Sleep`, `After`, `AfterFunc`, `Timer`, `Ticker`, `Tick`,
`NewTimer`, and `NewTicker`. These are part of the audit and will not be
mistaken for calendar APIs.

- The Go surface provides typed timers and tickers with stop/reset, callback,
  one-slot delivery, and monotonic event semantics. Explicit `receive()` avoids
  pretending a Python object is a Go channel.
- The Python surface provides synchronous sleep, timers, and tickers plus
  native asyncio sleep, deadlines, timeouts, timers, and async iterators.
- Wall-clock and monotonic readings remain distinct. Serializable `Time`
  values never expose a process monotonic reading as a Unix timestamp.
- Deterministic tests use `ManualClock` and injected async sleepers. A small,
  tolerance-aware system-clock integration suite covers real scheduling.

## Delivery Slices

1. Complete value, calendar, location, comparison, Unix, and duration APIs.
2. Extract and complete Go layout formatting and parsing against
   `format_test.go`.
3. Complete TZif loading, transition bounds, local location, and fixed zones.
4. Add Go binary, gob, JSON, and text serialization compatibility.
5. Add monotonic clocks, timers, tickers, synchronous utilities, and asyncio
   utilities with deterministic clock tests.
6. Run the full upstream-derived matrix, property tests, independent coverage,
   strict typing, wheel isolation, and performance gates.

The package is not complete until every row is implemented, explicitly
deferred with rationale, or declared inapplicable because Go's construct has no
honest Python representation. A small pygotpl-facing subset is not sufficient.
