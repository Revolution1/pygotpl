# M7: Package and Architecture Foundation

> Historical milestone: M10 decision D012 retained the `goduration` and
> `gotime` extractions but reintegrated the non-product `gofmt` and `goregexp`
> distributions under `gotpl._compat`. Completed checkboxes below record the M7
> state rather than the current package layout.

## Outcome

Establish the repository workspace, independent Go-compatibility distributions,
internal dependency boundaries, and performance-ready execution framework
before adding Sprout and Helm integrations.

This milestone changes structure without weakening observable Go, Sprig,
Slim-Sprig, HTML, sync, or async behavior. It is the last intended broad
architecture change before ecosystem work and the 1.0 API freeze.

## Deliverables

- [x] A uv workspace rooted at the repository with one coordinated lock file
  and independently buildable member distributions.
- [x] A `packages/` layout containing `goduration`, `gotime`, `gofmt`, and
  `goregexp`, each with its own `pyproject.toml`, `src/`, `tests/`, docs, and
  `py.typed` marker.
- [x] An immutable, human-friendly `goduration.Duration` API with Go-compatible
  parsing, formatting, signed 64-bit bounds, arithmetic, comparison, hashing,
  rounding, truncation, and explicit `datetime.timedelta` interoperability.
- [x] A Python-native `goduration.python.Duration` surface with arbitrary-size
  integers, Python float and Decimal semantics, explicit cross-surface
  conversion, and no implicit signed-64-bit overflow policy.
- [x] Immutable `gotime.Time` and `gotime.Location` APIs with nanosecond
  precision, Go layouts, IANA locations, Unix conversion, `Duration`
  arithmetic, chronological comparison, and explicit `datetime`
  interoperability.
- [x] Explicit `gotime.go` and `gotime.python` surfaces: the former preserves
  Go time behavior, while the latter follows Python datetime, zoneinfo,
  timestamp, exception, and numeric conventions behind a similar object API.
- [x] A Go 1.27 `time` source-and-test audit covering value, calendar, layout,
  location, TZif, serialization, monotonic-clock, timer, ticker, and scheduling
  APIs before declaring the standalone package complete.
- [x] Go-compatible `gotime` coverage for the complete value and calendar API,
  all layout constants and parsing/formatting, location and transition
  behavior, supported wire formats, and clock semantics.
- [x] Python-native synchronous and asyncio clock, deadline, timer, and ticker
  APIs, with deterministic injected-clock tests and explicit differences from
  Go channel behavior.
- [x] A deliberately narrow `gofmt` workspace API covering pygotpl's adopted
  Go `Sprintf` matrix, formatter protocols, bytes, pointers, and the separately
  named Python formatting mode. It is not a complete Go `fmt` clone.
- [x] Explicit `gofmt.go` and `gofmt.python` namespaces with no global or
  implicit formatting-mode switch.
- [x] A deliberately narrow `goregexp` workspace API for pygotpl's adopted
  Sprig/RE2 matrix, with an immutable compiled-pattern object, project-owned
  parsing, explicit resource limits, and no CPython-private parser dependency.
- [x] Explicit `goregexp.go` and `goregexp.python` namespaces, with RE2 and
  Python `re` syntax and semantics kept separate. It is not a general-purpose
  replacement for Python's regex ecosystem.
- [x] `gofmt` and `goregexp` are classified as internal-support distributions:
  independently buildable for architecture enforcement, but scoped only to
  concrete pygotpl ecosystem needs rather than standalone product completeness.
- [x] Thin pygotpl adapters for Sprig date, duration, regex, and runtime
  formatting behavior without changing existing coercion or error semantics.
- [x] A documented internal dependency graph and automated import-layer tests.
- [x] Clear ownership boundaries for parsing, compilation, runtime adaptation,
  sync and async execution, HTML contextual analysis, escapers, registries,
  and public template APIs.
- [x] A specialized-instruction design for common operand, lookup, callable,
  formatting, and HTML-context shapes, backed by representative prototype
  benchmarks before production adoption.
- [x] Before-and-after package import, build, wheel, latency, memory, and
  allocation evidence using the M6 methodology.

## Workspace Layout

```text
packages/
    goduration/
        pyproject.toml
        src/goduration/
        tests/
        docs/
    gotime/
        pyproject.toml
        src/gotime/
        tests/
        docs/
    gofmt/
        pyproject.toml
        src/gofmt/
        tests/
        docs/
    goregexp/
        pyproject.toml
        src/goregexp/
        tests/
        docs/
src/gotpl/
tests/
benchmarks/
```

Each distribution has independent metadata, typing, tests, documentation, and
wheel verification. The root workspace coordinates development and atomic
compatibility changes. No package moves to another repository in M7.

## Dependency Direction

```text
goduration <- gotime

goduration ----\
gotime ----------\
gofmt -------------> pygotpl
goregexp -----------/
```

- `goduration`, `gofmt`, and `goregexp` are independent leaves.
- `gotime` may depend only on `goduration` among workspace packages.
- No extracted package may import gotpl's AST, compiler, VM, sentinels,
  exceptions, or function registries.
- pygotpl owns template and Sprig coercion, registry names, error translation,
  and compatibility adapters.
- Sprout and Helm are future owned pygotpl modules. They follow an explicit
  internal ownership graph and use only public workspace-package APIs.

## Extraction Order

1. Extract `goduration` and migrate Sprig duration adapters.
2. Extract `gotime` on top of `goduration` and migrate Sprig date adapters.
3. Extract `gofmt` while preserving both Go and Python template format modes.
4. Replace the CPython-internal regex parser dependency, extract `goregexp`,
   and migrate Sprig regex adapters.
5. Verify editable workspace and built-wheel installations through the complete
   pygotpl suite.
6. Apply internal package and execution-framework cleanup only after the leaf
   dependency graph is stable.

## Progress Evidence

The first extraction slice is complete. `goduration` is an independently
buildable, typed, dependency-free workspace distribution, and pygotpl now uses
it through thin Sprig adapters. The package has direct API tests, checked-in Go
1.27 oracle vectors, 100% branch coverage with no missed statements, independent
Ruff and strict Pyright gates, and isolated wheel-install verification.

Both `goduration.go` and `goduration.python` are implemented. Top-level exports
default to the Go surface, pygotpl's Sprig adapters import it explicitly, and
cross-surface conversion is checked and explicit.

The general Sprig control workload moved from 65,692 ns/op at the M6 baseline
to 66,784 ns/op after extraction. That fixture does not invoke duration
functions, so the 1.66% difference is treated as benchmark noise control, not
as evidence that the duration path passed its end-to-end gate. A new
duration-heavy shared fixture now establishes a valid post-extraction baseline;
no equivalent pre-extraction end-to-end sample exists, so it is not presented
as a regression percentage. Full measurements, limitations, and commands are
recorded in `docs/reports/m7-goduration-extraction.md`.

The `gotime` extraction is complete at the workspace-package level. The ignored
Go checkout includes the complete pinned Go 1.27 `src/time` tree rather than
only the template packages. `packages/gotime/docs/api-scope.md` inventories the
full public API,
including serialization, monotonic clocks, timers, and tickers; the earlier
pygotpl-only subset is not treated as package completion.

The first implementation slices provide immutable Go and Python surfaces,
integer civil conversion, locations, Unix constructors and accessors, the zero
time, calendar and clock fields, comparison, duration and calendar arithmetic,
rounding, truncation, ISO weeks, all Go layout constants, diagnostic strings,
recorded TZif transition bounds, and the extracted formatting and parsing
foundation. Go binary v1/v2, gob, RFC 3339 text, and JSON serialization are
covered by a checked-in Go 1.27 oracle, including year zero, sub-minute offsets,
and legacy parse cases. Sprig now calls public `gotime.go.Time` APIs and no
longer owns duplicate civil, TZif, layout, or parsing implementations. Injected
wall and monotonic readings now cover Go's comparison, subtraction,
preservation, stripping, and diagnostic-string rules. The package-owned layout
parser has replaced the temporary `strptime` path and now covers the upstream
format, successful parse, range-error, day-of-year, optional-fraction, and
second-level-zone matrices under direct tests. Go-shaped timers and tickers use
explicit receive operations and deterministic injected clocks; the Python
surface adds synchronous scheduling and native asyncio sleep, deadline,
timeout, timer, and ticker APIs. Future `ZoneBounds` behavior beyond explicit
TZif transitions is checked against a Go 1.27 oracle. The standalone package
has 218 tests, 96% branch-aware coverage, independent Ruff and strict Pyright
gates, an isolated wheel test, and a reproducible surface benchmark. A bounded
compiled-layout cache reduced RFC 3339 Nano formatting from 24,886 ns/op to
3,145 ns/op without observable changes. Full evidence and explicit platform
limits are recorded in `docs/reports/m7-gotime-extraction.md`.

The intentionally narrow `gofmt` workspace extraction is also complete. It
owns only the template-facing `Sprintf` subset rather than the entire Go `fmt`
package. Explicit `gofmt.go` and `gofmt.python` surfaces, `GoPointer`, formatter
and integration protocols, 19 Go 1.27 oracle vectors, 50 direct tests, 98%
branch-aware coverage, Ruff, and strict Pyright all pass. pygotpl retains a thin
adapter for template missing/nil semantics. The M6 text/control workload moved
from 15,569 to 16,089 ns/render (+3.34%), below the 5% alert threshold. Scope,
correctness fixes, and benchmark evidence are recorded in
`docs/reports/m7-gofmt-extraction.md`.

The intentionally narrow `goregexp` extraction is complete as well. It owns
the Sprig-facing RE2 subset, a project-owned parser, an ordered Thompson NFA,
generated Go 1.27 Unicode tables, explicit compilation limits, and separate Go
and Python surfaces. It does not import CPython-private parser modules and does
not attempt to replace Python's richer regex ecosystem. Fourteen checked-in Go
oracle vectors, 47 standalone tests, 96% branch-aware coverage, Ruff, strict
Pyright, pure-wheel installation, and the full 1,755-test workspace suite pass.
The Sprig-heavy render is +3.62% against M6 and remains below the 5% alert
threshold. Full compatibility, security, packaging, and performance evidence
is recorded in `docs/reports/m7-goregexp-extraction.md`.

Like `gofmt`, this package boundary is not an independent product commitment.
Future milestones may add an API only for a concrete, pinned, oracle-backed
template-ecosystem requirement. The full Go `regexp` surface and a richer
Python regex facade remain explicit non-goals.

## Internal Architecture Direction

The template AST, compiler instructions, value adapter, sync and async VMs,
named-template association, and HTML contextual state machine remain integrated
inside gotpl.

Internal cleanup should:

- separate Go built-in registration from VM dispatch;
- distinguish compile-time immutable metadata from per-render mutable state;
- keep sync and async execution separate while sharing only coroutine-free
  semantic data and helpers;
- centralize registry layering, collision policy, and prepared callable slots;
- keep HTML analysis and rewriting at compile time and escaper transformations
  at runtime;
- reduce oversized module responsibilities without adding hot-path function
  boundaries merely to shorten files; and
- reserve explicit IR extension points for specialized instructions rather
  than embedding more semantic branching in the generic dispatcher.

The public top-level API remains small: `render`, `render_async`, `Template`,
`HTMLTemplate`, writer variants, named-template variants, documented adapters,
and explicit function registries.

## Performance Direction

Package extraction must not be treated as a performance optimization by itself.
Before and after measurements use the frozen M6 fixtures and reports.

Framework experiments should prioritize:

1. specialized compiled instructions for common constant, field, callable, and
   formatting shapes;
2. compile-time operand, function-slot, and HTML-context metadata;
3. exact-`dict` and common Python-object lookup paths behind the value adapter;
4. fewer repeated `isinstance` checks, enum hashes, and intermediate command
   argument lists; and
5. fused HTML filtering and escaping only where Go behavior and source
   attribution remain identical.

Async-specific optimization, a native extension, a complete Python-AST
backend, and a hand-written C or Rust VM remain deferred by the M6 evidence.

## Acceptance Gates

- [x] Every workspace package satisfies all in-repository gates in
  `docs/extraction-candidates.md`.
- [x] Each package builds and tests independently from its directory and from
  the root workspace on every supported CPython version and PyPy.
- [x] Editable workspace installs and built-wheel installs produce identical
  public behavior and typing results.
- [x] The workspace dependency graph is acyclic, automatically checked, and
  consistent with the documented direction.
- [x] The core pygotpl installation remains pure Python and requires no Go
  toolchain, subprocess, compiler, or platform-specific wheel.
- [x] Existing Go, Sprig, Slim-Sprig, HTML, sync, async, security, and Python
  adaptation suites pass without compatibility-only skips.
- [x] Package extraction introduces no unexplained representative regression
  above 5%; a regression above 10% is not accepted.
- [x] A framework optimization is retained only with output parity and a
  statistically credible improvement on at least two representative
  non-trivial workloads.
- [x] Public APIs use immutable typed value objects and pass standalone
  usability tests without template-specific concepts.
- [x] Sprout and Helm can be implemented using public workspace and pygotpl
  boundaries without importing private modules.
- [x] Architecture, dependency, extraction, testing, performance, build, and
  release documentation agree with the implemented workspace.

## Non-Goals

- Publishing any workspace package before the project license and ownership
  decisions are complete.
- Moving packages into separate repositories.
- Extracting the parser, AST, compiler, VM, value adapter, or HTML contextual
  state machine as independent distributions.
- Rewriting compatibility semantics in native code.
- Adding Sprout, Helm, sandbox, or new Python-extension behavior while package
  and execution boundaries are being established.
