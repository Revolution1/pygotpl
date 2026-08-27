# M7 gotime Extraction Report

## Decision

`gotime` is an independently buildable, pure Python workspace distribution.
It depends only on `goduration` and `tzdata`; it does not import gotpl.
pygotpl's Sprig date layer now owns only template-facing coercion, registry
names, clock injection, and compatibility error translation.

The package boundary and current public API are accepted for M7. Compatibility
claims are limited to the audited Go 1.27 surface and checked-in differential
vectors. Platform-specific local-zone discovery and civil years outside
Python's `datetime` range remain documented portability limits rather than
being hidden behind a broad claim of complete operating-system equivalence.

## Public Boundary

The distribution exposes two explicit namespaces:

- `gotime.go` provides immutable nanosecond `Time` and `Location` values, Go
  layouts, IANA and TZif locations, calendar and duration arithmetic, Unix
  conversion, monotonic-clock rules, wire formats, and Go-shaped timers and
  tickers with explicit `receive()` operations;
- `gotime.python` provides an immutable value backed by aware `datetime`, an
  explicit nanosecond remainder, standard `tzinfo` interoperability, Python
  duration conventions, synchronous scheduling, and native asyncio sleep,
  deadline, timeout, timer, and ticker APIs; and
- top-level exports default to the Go surface. There is no process-global
  behavior switch, and cross-surface conversion is explicit.

Go channel values and runtime timer internals have no honest Python
representation. The Go-shaped scheduling API therefore preserves observable
stop, reset, one-slot delivery, elapsed-time, and dropped-tick behavior without
pretending that `receive()` is a language-level channel operation.

## Compatibility and TDD Evidence

Behavioral work began from the pinned Go 1.27 `src/time` implementation and
tests. A small Go oracle generates checked-in vectors for UTC, IANA winter and
summer offsets, recurring future transitions, second-level fixed offsets, ISO
weeks, zone bounds, diagnostic strings, and binary, text, and JSON wire forms.
The repository check regenerates those vectors and requires structural JSON
identity (formatting whitespace is intentionally ignored).

The standalone matrix also covers:

- Go-normalized construction, year zero and negative years, signed short-year
  formatting, Unix normalization, calendar fields, ISO weeks, `AddDate`,
  rounding, truncation, comparisons, and `Duration` arithmetic;
- all exported Go layout constants, the upstream format table, optional and
  exact fractional seconds, day-of-year fields, 12-hour clocks, whitespace and
  case rules, all numeric zone forms including seconds, malformed values, and
  structured `ParseError` fields;
- Go binary versions 1 and 2, gob aliases, RFC 3339 text and JSON, legacy comma
  fractions and permissive offsets, invalid lengths, and unsupported offsets;
- TZif parsing, pre-transition lookup, historical and recurring future
  transitions, fixed zones, local-zone environment handling, and independent
  TZif byte loading;
- monotonic preservation and stripping rules, injected wall and monotonic
  clocks, deterministic timers and tickers, asyncio cancellation and timeout
  behavior, and a tolerance-aware system-clock integration test; and
- direct API, error, conversion, hashing, sync/async parity, and Python-native
  usability tests that do not import template concepts.

Direct package evidence on CPython 3.14.7:

| Gate | Result |
| --- | ---: |
| Standalone tests | 218 passed |
| Statement and branch-aware coverage | 96% |
| Ruff | passed |
| Strict Pyright | passed |
| Go version | 1.27.0 |
| Isolated wheel import and value operation | passed |

## Dependency and Packaging Evidence

`gotime` has a `src` layout, PEP 621 metadata, a `py.typed` marker, direct
tests, an owned benchmark, API documentation, and a source oracle. Its sdist
explicitly includes those materials. Runtime dependencies are only
`goduration` and current IANA `tzdata`; neither Go nor a subprocess, compiler,
extension module, or platform-specific wheel is required at runtime.

The wheel and `goduration` wheel were installed into an empty CPython 3.13
virtual environment with dependency resolution disabled. The isolated process
successfully formatted the Unix epoch and parsed a duration. Disabling
resolution tests the workspace artifacts themselves; normal installation
resolves the declared `tzdata` package.

## Performance Evidence

Measurements used CPython 3.14.7 on macOS arm64. Each result is the median of
seven runs of 100,000 public operations with garbage collection disabled only
inside a sample. The benchmark compares the explicit package surfaces and, for
one operation, `datetime` directly. Ratios describe object overhead; they are
not Go-runtime comparisons because Python's native surface intentionally has
different semantics.

The initial profile found that every `Time.format()` call rescanned its layout
and rebuilt formatting data for every token. Compiling immutable layout parts
behind a bounded 512-entry cache reduced the RFC 3339 Nano median from 24,886
ns/op to 3,145 ns/op, an 87.4% improvement, with the complete package and root
compatibility suites unchanged.

| Operation | Go surface ns/op | Python reference ns/op | Python / Go |
| --- | ---: | ---: | ---: |
| Construct value object | 1,035 | 154 | 0.15x |
| RFC/ISO format | 3,145 | 464 | 0.15x |
| Add one second, value objects | 387 | 416 | 1.08x |
| Convert to New York | 290 | 292 | 1.00x |
| Add one second, `datetime` | 387 | 158 | 0.41x |

The remaining formatter gap is expected to be the main standalone CPU target:
the Go surface performs arbitrary reference-layout token dispatch,
nanosecond handling, signed civil-year support, and Go zone formatting, while
`datetime.isoformat()` is a specialized C implementation. No compatibility
shortcut is justified by this comparison. Construction also pays for Go field
normalization and immutable civil conversion. Arithmetic and location-view
changes are already close to the Python-native object surface.

No pre-extraction date-heavy end-to-end render sample exists, so this report
does not invent a regression percentage. M7's complete package report will use
the frozen M6 fixtures as the broad before/after control and add a deterministic
date-heavy fixture as a current trend baseline.

## Reproduction

```console
./scripts/check_gotime_oracle.sh
uv run --directory packages/gotime --frozen pytest -q
uv run --directory packages/gotime --frozen coverage run -m pytest -q
uv run --directory packages/gotime --frozen coverage report
uv run --directory packages/gotime --frozen ruff check .
uv run --directory packages/gotime --frozen pyright
uv run --directory packages/gotime --frozen python \
  benchmarks/compare_surfaces.py --samples 7 --iterations 100000
uv build --package gotime --package goduration
```

## M7 Integration Status

The independent package, dual surfaces, Go oracle, typing, coverage, build,
wheel, and performance slices are complete. The final M7 workspace audit now
covers CPython 3.11 through 3.14 and PyPy 3.11, editable and wheel consumers,
imports, memory, allocations, and end-to-end rendering across all four
extracted packages. See `m7-package-architecture-audit.md`; no remaining M7 gap
belongs to the `gotime` object API.
