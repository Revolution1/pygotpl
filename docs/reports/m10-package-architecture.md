# M10 Package Architecture Review

## Decision

The repository remains named `pygotpl`; the distribution and import package are
now named `gotpl`. Both PyPI JSON project endpoints returned HTTP 404 on August
27, 2026. That is useful collision evidence, but only an authenticated first
publication can prove that the name is claimable rather than reserved.

The supported import layout is:

```text
gotpl
├── funcs
│   ├── sprig
│   ├── slim_sprig
│   ├── sprout
│   └── helm
├── pythonic
├── runtime
├── html
├── parse
├── compile
└── _compat
    ├── gofmt
    └── goregexp
```

`gotpl.funcs` owns explicit compatibility function libraries.
`gotpl.pythonic` owns opt-in Python-native functions such as `reMatch`.
`gotpl._compat` is private and may be consumed only by the import owners in
`docs/architecture.md`; it is not a standalone or stable public API.

## Distribution Reduction

The coordinated install contains three wheels:

- `gotpl`
- `goduration`
- `gotime`

The pre-freeze review retired the separate `gofmt` and `goregexp` wheels. Their
complete adopted Go compatibility engines, generated tables, direct tests, Go
oracles, and relevant benchmarks remain in the repository. Only their redundant
packaging metadata, release lifecycle, and unused Python-regex facade were
removed. Python-native regex behavior remains in `gotpl.pythonic` and calls the
standard library directly.

## Redundancy Review

The reintegration removes two build configurations, two dependency-resolution
edges, two release lifecycles, and their distribution-local `py.typed` markers.
The single `gotpl/py.typed` marker covers the complete main distribution.

An implementation-level review did not merge the similarly named optional
dependency errors, YAML loaders, conversion helpers, or numeric functions under
`gotpl.funcs`. Helm, Sprout, Slim-Sprig, and Sprig expose different error
channels, return shapes, coercion rules, overflow behavior, and type
preservation. Those modules are independently checked against different pinned
upstreams. Sharing them without proof of full behavioral identity would reduce
line count while weakening the compatibility boundary. Sprout already delegates
to the public Sprig map where its pinned implementation genuinely adopts Sprig
behavior; that remains the preferred form of proven reuse.

Future consolidation must start with common differential fixtures and prove
identical success values, result types, and failure behavior before introducing
a shared helper. It must not add an abstraction call to a measured hot path
without benchmark evidence.

No `pygotpl`, `gofmt`, or `goregexp` top-level import alias is shipped. The
project is pre-1.0 and none of those distributions was published, so maintaining
dual module identities would impose permanent documentation, typing, traceback,
cache, and support ambiguity without protecting an established stable API.

## Dependency and Import Evidence

The root metadata depends on `goduration` and `gotime`; `gotime` alone depends
on `goduration`. The executable architecture test verifies:

- the three-wheel metadata and source paths;
- absence of retired top-level packages and directories;
- all internal owner-to-owner imports;
- no reverse dependency from either retained leaf into gotpl; and
- an acyclic workspace metadata graph.

The direct formatting and regex suites moved under `tests/internal/`. Their Go
oracle tools moved under `tools/gofmt_oracle` and `tools/goregexp_oracle`.
Generated Unicode verification now compares against
`src/gotpl/_compat/goregexp/_unicode_tables.py`.

## Verification

The post-migration local gate on CPython 3.14.7, followed by the M10 coverage
gate, completed with:

- 1,973 tests passing;
- Ruff formatting and lint clean;
- strict Pyright with zero errors;
- exact statement coverage at 98.1002% and branch coverage at 96.0893%;
- generated Unicode, duration, time, formatting, regex, Sprout inventory, Go
  template, Sprig, and Helm oracle checks passing; and
- all three wheels built offline, installed together in a fresh environment,
  and exercised without optional extras; and
- the installed public smoke suite passed with `go` absent from `PATH`,
  including text, contextual multi-source HTML, Sprig regex, sandbox,
  Python-native extension, Helm map, duration, and time paths.

The same sandbox fixture used immediately before and after the move measured
31.646 us and 31.812 us for the default warm path, a 0.52% difference within
ordinary local benchmark noise. The implementation and call graph did not
change. Fresh-process `gotpl` import measured a 128.473 ms median and 5.27 MiB
median traced peak on the current Apple M5/CPython 3.14.7 environment. These are
new layout baselines, not direct release-regression comparisons with the older
M7 codebase.

## Compatibility and Migration

Template behavior and the Go/Sprig compatibility profiles are unchanged. The
Python import migration is mechanical:

```python
from gotpl import Template
from gotpl.funcs.sprig import text_func_map
from gotpl.pythonic import PythonExtensions
```

Applications must not import `gotpl._compat`. Formatting is available through
template output, `printf`, `format_mode`, and root formatting protocols. Regex
functions are available through Sprig/Sprout registries or the explicit
Python-native extension.

The rationale, simplification, performance effect, and revisit conditions are
recorded in implementation decision D012.
