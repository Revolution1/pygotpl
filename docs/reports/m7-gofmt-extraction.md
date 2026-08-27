# M7 gofmt Extraction Report

> Historical evidence: M10 decision D012 reintegrated this implementation into
> `gotpl._compat.gofmt` and retired the independent wheel. Paths and commands
> below describe the M7 extraction state.

## Decision and Scope

`gofmt` is a deliberately narrow, dependency-free workspace package. It owns
the value-formatting boundary used by pygotpl, but it is not intended to become
a general Python reimplementation of the whole Go `fmt` standard-library
package.

The adopted scope is Go 1.27 `Sprintf` behavior needed by Go templates, Sprig,
and pygotpl's public formatting modes: directive parsing, operand indexes,
flags, dynamic width and precision, in-band diagnostics, scalar and complex
values, strings, bytes, sequences, mappings, explicit pointers, and a Python
adaptation of `fmt.Formatter`. Explicit non-goals are scanning, `Errorf`,
stdout/stderr functions, `io.Writer` emulation, and exhaustive reconstruction
of Go's static type system.

This smaller boundary still matters architecturally. It removes formatting
semantics from the VM, permits direct differential tests, and lets both Go and
Python value rendering be selected through imports without a mutable global
mode. It does not claim that standalone formatter demand justifies a broader
product.

## Public Boundary

- `gofmt.go.sprintf` is the Go-compatible surface.
- `gofmt.python.sprintf` keeps the same directive language but uses Python
  `str`, `repr`, type names, and object identities where value rendering is not
  dictated by a numeric or string verb.
- Top-level `gofmt.sprintf` defaults to the Go surface.
- `GoPointer` supplies explicit typed-pointer behavior.
- `GoFormatSpec` and `__go_format__` adapt Go's formatter protocol.
- Narrow `__go_format_value__` and `__go_map_type__` protocols let integrating
  packages provide sentinel and static-map metadata without a reverse import.

pygotpl retains its missing-value, untyped-nil, and typed-map concepts. Its
adapter implements those protocols and selects the requested surface. The
independent package imports no pygotpl AST, compiler, VM, sentinel, registry,
or exception.

## Compatibility and TDD Evidence

The pinned Go 1.27 `src/fmt` implementation and tests are available in the
ignored reference checkout. A checked-in, independently authored 19-vector Go
oracle covers normal formatting, flags, width, precision, dynamic and reordered
operands, Unicode precision, bytes, floats, complex values, nil, slices, maps,
missing arguments, bad indexes, bad widths, and extra arguments.

The first oracle run exposed two differences that the earlier template tests
had missed:

- Default `%g` incorrectly used six significant digits instead of Go's shortest
  round-trippable representation.
- Non-ASCII control characters below U+0100 incorrectly used `\xNN` rather
  than Go's `\uNNNN` representation.

Both oracle cases failed before their fixes. Direct tests additionally cover
the bounded directive cache across threads, all adopted scalar branches,
quotes and escapes, pointer forms, Python-mode bypass of Go formatters,
mapping-order policies, integration protocols, and invalid protocol results.

Evidence on CPython 3.14.7:

| Gate | Result |
| --- | ---: |
| Standalone tests | 50 passed |
| Statement and branch-aware coverage | 98% |
| Go oracle vectors | 19 passed; regeneration identical |
| Ruff | passed |
| Strict Pyright | passed |
| Complete workspace tests | 1,755 passed |
| Isolated wheel import and both surfaces | passed |

## Packaging and Dependency Evidence

The package has independent PEP 621 metadata, a `src` layout, `py.typed`, API
documentation, tests, a Go oracle, and a benchmark. It has no runtime
dependencies. pygotpl now declares `gofmt` as a workspace/runtime dependency,
and `GoPointer` is owned by and re-exported from that leaf. The template adapter
contains only surface selection and template-`None` adaptation.

`uv build --all-packages` produced pure-Python sdists and wheels for all four
current distributions. Installing only the `gofmt` wheel, without dependency
resolution, into an empty CPython environment successfully exercised both
public surfaces.

## Performance Evidence

The frozen M6 text/control render is the representative extraction control
because it exercises template output formatting. On the same CPython 3.14.7,
Go 1.27.0, and macOS arm64 environment, seven samples produced:

| Measurement | M6 before | M7 after | Change |
| --- | ---: | ---: | ---: |
| Python median ns/render | 15,569 | 16,089 | +3.34% |
| Go median ns/render | 1,102 | 1,113 | +1.00% |
| Python / Go | 14.13x | 14.46x | +2.34% |
| Go allocations/render | 35 | 35 | unchanged |
| Go bytes/render | 808 | 808 | unchanged |

An initial post-move sample was 16,382 ns/render. Profiling the adapter found
an unconditional tuple copy on every `sprintf` call. Restricting allocation to
the uncommon direct-`None` case reduced the median to 16,089 ns/render. The
remaining 3.34% difference is below the M7 5% alert threshold and is not
statistically attributed solely to extraction from two historical snapshots.

The independent surface benchmark uses seven samples of 100,000 operations:

| Operation | Go surface ns/op | Python surface ns/op | Python / Go |
| --- | ---: | ---: | ---: |
| Integer formatting | 1,071 | 1,062 | 0.99x |
| Quoted string | 1,572 | 1,565 | 1.00x |
| Default mapping | 2,866 | 894 | 0.31x |
| Dynamic operands | 3,483 | 3,483 | 1.00x |

Mapping is the only material surface difference in this set because the Go
surface sorts keys and recursively emits Go map syntax, while Python mode uses
the mapping's native string representation. These are current trend baselines,
not evidence for expanding the package's scope.

## Reproduction

```console
./scripts/check_gofmt_oracle.sh
uv run --directory packages/gofmt --frozen pytest -q
uv run --directory packages/gofmt --frozen coverage run -m pytest -q
uv run --directory packages/gofmt --frozen coverage report
uv run --directory packages/gofmt --frozen ruff check .
uv run --directory packages/gofmt --frozen pyright
uv run --directory packages/gofmt --frozen python \
  benchmarks/compare_surfaces.py --samples 7 --iterations 100000
uv run --frozen python -m benchmarks.compare \
  benchmarks/fixtures/text_render.json --samples 7
```

## M7 Integration Status

The API, adapter, direct oracle, coverage, typing, performance, workspace-wide
build, and isolated-wheel parity gates are complete. See
`m7-package-architecture-audit.md`. No broader Go `fmt` surface is planned
unless pygotpl gains a concrete need for it.
