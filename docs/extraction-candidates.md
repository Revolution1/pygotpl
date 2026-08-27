# Extraction Candidates

## Purpose

This document tracks compatibility components considered for independent Python
distributions inside the pygotpl repository. Extraction is retained only when
the component has a coherent standalone product surface; a technical module
boundary alone is not sufficient.

Extraction must preserve pygotpl's pure Python runtime, supported Python
versions, typing quality, and differential evidence. A new package must be
useful outside template rendering and must not force pygotpl users to install
unrelated dependencies.

`goduration` and `gotime` are the selected distribution names and are declared
as bounded PyPI dependencies of `gotpl`. The completed M7 in-repository
extraction does not by itself authorize a repository split; external
publication still follows the coordinated release gates.

## Incubation Decision

M7 originally extracted all four candidates as workspace distributions. The M10
pre-freeze review retained `goduration` and `gotime`, whose object models are
independently useful, and reintegrated the deliberately incomplete `gofmt` and
`goregexp` implementations under `gotpl._compat`. Separate wheels for code with
no intended standalone users increased installation, release, dependency, CI,
and support surface without strengthening the internal module boundary.

The intended layout is:

```text
packages/
    goduration/
        pyproject.toml
        src/goduration/
        tests/
    gotime/
        pyproject.toml
        src/gotime/
        tests/
src/gotpl/
    _compat/
        gofmt/
        goregexp/
tests/
```

`gotime` may depend on `goduration`; neither leaf may import the gotpl AST,
compiler, runtime sentinels, VM, or function registry. Private compatibility
modules may be imported only by the explicitly allowed gotpl owners recorded in
`docs/architecture.md` and the executable import-layer test.

## Candidate Register

| Candidate | Incubating implementation | Earliest review point | Status |
| --- | --- | --- | --- |
| `gotime` | `packages/gotime`; adapters in `gotpl.funcs.sprig.dates` | M7, after `goduration` | extracted |
| `goduration` | `packages/goduration`; adapters in `gotpl.funcs.sprig.dates` | M7, first workspace extraction | extracted |
| `gofmt` | `gotpl._compat.gofmt`; adapter in `gotpl.runtime.gofmt` | M10 package review | reintegrated-private |
| `goregexp` | `gotpl._compat.goregexp`; adapter in `gotpl.funcs.sprig.regex` | M10 package review | reintegrated-private |

`gotime` and `goduration` are retained independently useful products.
`gofmt` and `goregexp` are not standalone candidates. Their compatibility,
generated-data, security, and performance boundaries remain directly tested,
but they no longer own distribution metadata or a public release lifecycle.
Neither has a roadmap to reproduce its complete Go standard-library package or
to compete with Python's standard library.

Status values are:

- `observed`: a reusable boundary has been noticed but not yet validated.
- `research`: feasibility, dependency, or compatibility questions remain.
- `incubating`: pygotpl owns an implementation with direct tests.
- `ready-for-review`: every extraction gate in this document has evidence.
- `extracted`: an independent workspace distribution exists and pygotpl
  consumes it.
- `split`: the distribution has passed the additional separate-repository gate.
- `reintegrated-private`: a prior extraction was reversed because it did not
  justify an independent product and release surface.

## Standalone API Principles

Extraction is a product-level API redesign, not a mechanical move of pygotpl
helpers. Every independent package must expose two explicit, typed surfaces:
one for exact Go behavior and one that borrows the Go API shape while following
Python's native types, protocols, exceptions, and numeric expectations.

The namespace convention is consistent across packages:

- `<package>.go` owns exact Go behavior;
- `<package>.python` owns Python-native behavior; and
- convenient top-level exports default to the Go surface because pygotpl's
  default compatibility contract is Go-compatible.

Callers select a surface through imports or immutable construction state. A
process-global mode switch is prohibited. Conversion between surface-specific
value objects must be explicit, and pygotpl adapters must import the intended
surface rather than relying on an ambiguous alias.

Both surfaces should:

- use value objects for concepts with identity and operations, such as
  `Duration`, `Time`, `Location`, and compiled regular expressions;
- provide clear constructors and class methods such as `Duration.parse(...)`
  rather than requiring callers to assemble low-level helper calls;
- implement Python operators when their meaning is unambiguous, including
  duration arithmetic, comparison, negation, multiplication, division, and
  time-plus-duration or time-minus-time operations;
- return `NotImplemented` for unsupported operand types and avoid surprising
  coercions merely because a Sprig wrapper accepts them;
- preserve Go precision, widths, overflow, formatting, coercion, and error
  semantics on the Go surface;
- preserve arbitrary-size Python integers, ordinary Python float and Decimal
  behavior, standard-library types, protocols, and idiomatic exceptions on the
  Python surface unless its contract documents a narrower invariant;
- interoperate deliberately with Python standard-library types without losing
  nanoseconds or silently changing timezone semantics;
- provide complete type annotations, useful representations, stable hashing
  for immutable values, and API-focused tests independent of gotpl.

Convenience must not erase precision or compatibility. Shared implementation is
allowed only below the semantic boundary; one surface must never accidentally
inherit the other surface's overflow, rounding, formatting, regex, time-zone,
or coercion policy.

## Candidate: gotime

Current implementation: `packages/gotime`, with template-facing coercion and
error adapters in `gotpl.funcs.sprig.dates`.

Potential scope:

- Go reference-time layout formatting and parsing.
- IANA location loading and Go-compatible invalid-zone behavior.
- TZif-backed Go zone-abbreviation lookup and historical offsets.
- Unix timestamp conversion.
- Go zero-time representation and conversion rules.
- Nanosecond-preserving time values and arithmetic beyond Python
  `datetime`'s microsecond precision.
- Explicit local-time and injectable-clock policies for Python callers.

The expected standalone center is an immutable `Time` value rather than a set
of formatting functions. It should support arithmetic with `Duration`,
subtraction of two times to produce `Duration`, chronological comparison,
timezone conversion, Go layout parsing and formatting, Unix conversions, and
lossless access to nanoseconds. Python `datetime` conversion must make any
precision loss explicit.

Python's `time` module is not a suitable primary representation for this API.
It mainly exposes timestamps, process and system clocks, sleeps, and a limited
`struct_time`; it does not provide the calendar, location, parsing, formatting,
or arithmetic model needed to reproduce Go `time.Time`. The implementation
should instead combine purpose-built integer civil-time primitives with
`datetime` and `zoneinfo` interoperability. The `time` module remains useful
only at the clock boundary, especially `time.time_ns()` for wall-clock input
and `time.monotonic_ns()` or `time.perf_counter_ns()` for elapsed-time APIs.
Monotonic readings must never be confused with serializable wall-clock values.

The Go surface preserves Go calendar bounds, locations, layout parsing,
normalization, duration arithmetic, and errors. The Python surface accepts and
returns standard `datetime`, `date`, `time`, `timedelta`, `tzinfo`, and
`zoneinfo` values where natural, follows Python timestamp and exception
conventions, and makes nanosecond precision extensions explicit.

The package should be extracted only after the required Go layout token matrix,
timezone transitions, fractional seconds, invalid inputs, and platform behavior
have differential tests. Sprig-specific fallback rules remain adapters in
`gotpl.funcs.sprig` rather than becoming gotime defaults.

`gotime` may depend on `goduration` once both APIs are stable. `goduration`
must not depend on `gotime`: duration parsing, formatting, and arithmetic are
useful without calendars, time zones, or wall-clock values.

The in-repository extraction completed against Go 1.27.0. The owned Go-layout
compiler and parser, TZif reader, nanosecond value model, wire formats,
monotonic rules, deterministic scheduling, and Python asyncio APIs have direct
standalone tests. A checked-in Go oracle covers values, locations, future
transitions, and serialization. See
`docs/reports/m7-gotime-extraction.md` for compatibility, packaging, coverage,
and performance evidence and for the explicit platform limits.

## Candidate: goduration

Current location: `packages/goduration`, with Sprig coercion and error adapters
in `gotpl.funcs.sprig.dates`.

Potential scope:

- Go `time.ParseDuration` syntax and signed 64-bit bounds.
- Go `time.Duration.String` formatting.
- Nanosecond-preserving arithmetic and rounding.
- Conversion helpers that do not silently inherit Sprig's input coercions.

The expected standalone center is an immutable `Duration` value stored as
signed integer nanoseconds. At minimum, its API design must evaluate:

- `Duration.parse(...)` and named constructors for nanoseconds through hours;
- `+`, `-`, unary `-`, `abs()`, comparisons, and hashing;
- multiplication by numeric scalars and division with explicitly defined
  duration-versus-scalar and duration-versus-duration results;
- round, truncate, component access, Go string formatting, and explicit
  `timedelta` conversion;
- Go `int64` wraparound for compatibility arithmetic, checked construction and
  parsing boundaries, and an unbounded Python variant exposed as a deliberate
  and separately tested choice.

The implemented Go surface uses signed 64-bit nanoseconds, Go fractional
parsing, Go arithmetic wraparound, integer division and remainder, and Go
rounding saturation. The implemented Python surface uses
arbitrary-size integer nanoseconds, exact decimal text parsing, Python numeric
protocols, and
idiomatic Python errors. Float input follows documented Python float semantics
rather than Go's parsing implementation. Both remain immutable duration objects
and provide explicit, checked conversion to one another. Top-level exports
default to the Go surface, and pygotpl imports that namespace explicitly.

Extraction requires exhaustive differential vectors for units, fractions,
overflow, negative values, formatting thresholds, and malformed input. Sprig's
`duration` and `durationRound` functions should remain thin compatibility
wrappers around the independent primitives.

The in-repository extraction completed against Go 1.27.0. The package exposes
an immutable signed-64-bit `Duration`, named constructors, arithmetic,
comparison, hashing, rounding, truncation, unit totals, and explicit
`datetime.timedelta` conversion. Its generated oracle fixture covers parsing,
formatting, invalid input, overflow, and rounding boundaries, including Go's
float64 fraction rule. See `docs/reports/m7-goduration-extraction.md` for gate
evidence and the measured adapter trade-offs.

## Candidate: gofmt

Current implementation: `gotpl._compat.gofmt`, with template sentinel and mode
adaptation in `gotpl.runtime.gofmt`.

Potential scope:

- The Go `fmt.Sprintf` verbs, flags, width, precision, and indexed operands
  exercised by Go templates, Sprig, and pygotpl's public formatting modes.
- Go-compatible scalar, byte-slice, pointer, and formatter protocols.
- A deliberate Python-native formatting mode layered outside the compatibility
  core.

The Go surface owns Go verbs, widths, numeric types, and formatter protocols.
The Python surface uses Python values, `format()` conventions, and Python type
names while borrowing only the convenient formatter API shape.

The private module is an internal-support boundary, not a standalone product or
a commitment to recreate the whole Go `fmt` package.
Its explicit non-goals are
`Scan*`, `Errorf`, stdout/stderr functions, `io.Writer` emulation, and exhaustive
modeling of Go's static type system. Extraction requires the adopted
template-facing matrix and a small usable public API; unrelated upstream
formatting and scanning matrices do not block M7.

The M7 extraction established 19 checked-in Go oracle vectors and the required
dual formatting behavior. M10 removed its redundant wheel and standalone
metadata while retaining the implementation, direct tests, benchmark, oracle,
and thin template sentinel adapter. See
`docs/reports/m7-gofmt-extraction.md` for historical extraction evidence and
decision D012 for reintegration.

## Candidate: goregexp

Current implementation: `gotpl._compat.goregexp`, with the Sprig result/error
adapter in `gotpl.funcs.sprig.regex`.

Potential scope:

- The Go regexp/RE2-compatible syntax and operations exercised by Sprig and
  pygotpl's template-facing registries.
- Match, find, split, quote, and replacement expansion semantics required by
  those registries.
- Rejection of Python-only constructs and protection from backtracking risks.

The incubating implementation uses a pure Python ordered Thompson NFA for
general accepted patterns. A narrowly audited standard-library fast path is
limited to a single consuming atom or its greedy repetition, where there is no
alternative backtracking path. This preserves the project's no-compiled-
extension runtime rule while providing linear input complexity.

The private module is an internal-support architectural and security boundary,
not a standalone product and not an attempt to compete with Python's
richer `re` module or third-party regex engines. Its scope grows only when a
pinned Go-template, Sprig, Slim-Sprig, Sprout, or Helm compatibility case needs
additional behavior. Every such addition requires oracle-backed tests and must
preserve the linear-time and resource-limit guarantees. Its explicit non-goals
are exhaustive reproduction of Go's full `regexp` package, reader/index APIs
not used by pygotpl, and extensions without a concrete template-ecosystem
consumer.

The Python-native `reMatch` template extension is not part of `goregexp`'s Go
compatibility API. It is a pygotpl extension backed by the standard-library
`re` engine, uses Python pattern syntax and search semantics, and must retain a
distinct name. It must never replace Sprig's `regexMatch` or enter a Go, Sprig,
Slim-Sprig, or strict-sandbox profile implicitly.

The former duplicate Python surface was removed during reintegration. Pythonic
templates use `gotpl.pythonic` and the standard-library `re` engine directly;
the private compatibility engine remains RE2-compatible. Syntax, matching,
replacement, and error behavior never cross namespaces implicitly.

The M7 extraction completed against Go 1.27.0. Its owned
parser and ordered NFA have explicit compilation limits, generated Go Unicode
17.0.0 tables, a checked-in Go oracle, adversarial linear-time tests, and
coverage, lint, typing, benchmark, and oracle gates remain integrated into the
root suite. M10 removed its redundant wheel and Python-surface duplication. See
`docs/reports/m7-goregexp-extraction.md` for historical scope evidence and
decision D012 for reintegration.

## Components to Keep Integrated

The template AST, compiler instructions, value adapter, execution VMs, named
template association, and contextual HTML state machine are coupled to template
semantics and should remain in gotpl. Similar-looking general utilities are
not extraction candidates unless an independent API and independent users are
demonstrated.

## Recording New Candidates

Add a candidate when implementation work reveals a Go-compatibility primitive
that meets all of these discovery criteria:

1. It has a coherent use case outside templates.
2. Its semantics can be specified without the pygotpl AST, compiler, VM, or
   function registry.
3. At least one meaningful compatibility boundary is broader than the current
   Sprig or template wrapper.
4. Keeping the boundary explicit improves testing, dependency isolation,
   security review, or performance measurement.

Do not add ordinary helpers, one-function wrappers, or speculative package
ideas that lack an independent consumer. For each accepted candidate, add a
register row and a section containing:

- the provisional package name and current implementation location;
- reference implementation and version policy;
- proposed public scope and explicit non-goals;
- direct normal, boundary, failure, and platform test requirements;
- performance, security, and optional-dependency considerations;
- the earliest milestone or evidence point at which extraction can be reviewed.

New candidates start as `observed` or `research`. Promote their status only
when repository evidence supports the transition.

## In-Repository Extraction Gate

A candidate can become a workspace distribution only when all of the following
are true:

1. Its compatibility target and version policy are explicit.
2. Differential normal, boundary, invalid-input, and platform tests are
   portable without the pygotpl VM.
3. Its public API is useful without template-specific sentinels or exceptions.
4. Its object model and operator behavior pass standalone API usability tests.
5. Performance and allocation baselines exist before the move.
6. The dependency and security impact is documented.
7. pygotpl can consume the package without changing observable behavior.
8. Independent package metadata, typing, build, and test commands work from
   both the package directory and the repository workspace.
9. Editable workspace use and built-wheel installation produce identical
   pygotpl behavior.
10. Coordinated version constraints, build order, and rollback behavior are
    documented.
11. Both explicit `go` and `python` surfaces have independent normal, boundary,
    failure, typing, and cross-conversion tests; top-level defaults resolve to
    the Go surface.

## Separate-Repository Gate

No package moves to another repository during M7. A later split requires all
in-repository gates plus:

1. Named maintainers and repository ownership.
2. Independent CI, release automation, security reporting, and changelog.
3. A coordinated release procedure that cannot leave pygotpl depending on an
   unpublished or incompatible version.
4. Evidence that cross-repository development does not weaken differential
   testing or make atomic compatibility changes impractical.
5. A migration plan preserving source history, issues, documentation links,
   package ownership, and rollback capability.
