# M7 goregexp Extraction Report

> Historical evidence: M10 decision D012 reintegrated this implementation into
> `gotpl._compat.goregexp`, removed its unused Python facade, and retired the
> independent wheel. Paths and commands below describe the M7 extraction state.

## Decision and Scope

`goregexp` is a deliberately narrow, dependency-free workspace package. It
owns the regex compatibility and security boundary required by pygotpl and
Sprig; it is not intended to reproduce every API in Go's `regexp` package or
to compete with Python's richer standard-library `re` module.

The adopted Go surface covers immutable compilation, search, find, find-all,
replacement expansion, literal replacement, split, and quoting. Reader and
index APIs without a pygotpl consumer are explicit non-goals. The Python
surface is a small immutable wrapper over public `re`, provided only to keep
Python syntax and behavior visibly separate from Go compatibility.

## Public and Security Boundary

- `goregexp.go` accepts the adopted RE2 syntax and uses Go matching,
  replacement, split, count, and no-match conventions.
- `goregexp.python` preserves Python syntax, flags, replacement expansion,
  split captures, count rules, and exceptions.
- Top-level exports default to the Go surface; no global semantic switch
  exists.
- General Go patterns execute with a project-owned parser and ordered Thompson
  NFA. A standard-library fast path is restricted to audited single-atom
  shapes that cannot introduce alternative backtracking paths.
- `Limits` bounds pattern length, repeat counts, compiled instructions, and
  captures on the Go surface. Pattern length and captures are enforceable on
  the Python surface through public `re`; Python does not expose a stable
  instruction representation.

The package imports no pygotpl module and no CPython-private regex parser or
constant. Generated Unicode category, script, alias, complement, and assigned
rune tables are pinned to the Go 1.27 Unicode 17.0.0 data. pygotpl retains only
Sprig registry names and `FunctionResult` error adaptation.

## Compatibility and TDD Evidence

The extraction began from the existing Sprig and adversarial regression tests,
then moved the engine behind a standalone compiled object. A checked-in
14-vector Go 1.27 oracle covers ASCII Perl classes, leftmost-first matching,
empty-match progression, zero counts, named and literal replacement, split,
quoting, Unicode properties, ungreedy mode, and Go octal escapes.

The direct public API tests exposed a previously hidden difference: `\1` was
being translated as a one-digit octal escape. Go RE2 accepts exactly three
octal digits in this form, so `\1` is now rejected as invalid syntax while
`\123`, `\400`, and `\777` remain compatible. Earlier template tests observed
only a false match and therefore did not prove compilation behavior.

Evidence on CPython 3.14.7:

| Gate | Result |
| --- | ---: |
| Standalone package tests | 47 passed |
| Statement and branch-aware coverage | 96% |
| Go 1.27 oracle vectors | 14 passed; regeneration identical |
| Focused package, Sprig, and Unicode tests | 85 passed |
| Ruff | passed |
| Strict Pyright | passed |
| Complete workspace tests | 1,755 passed |
| Isolated wheel import and both surfaces | passed |

The adversarial `^(a|aa)+$` case rejects a 4,097-character non-match through
the ordered NFA. Direct tests also cover nullable and lazy repetition,
leftmost-first thread priority, named and unmatched captures, ASCII and Unicode
classes, flags and scopes, empty matches, cache bounds, parser failures, and
explicit compilation limits.

## Packaging and Dependency Evidence

The distribution has independent PEP 621 metadata, a `src` layout, `py.typed`,
API documentation, tests, generated tables, a Go oracle, and a benchmark. It
has no runtime dependencies. pygotpl declares it as a workspace/runtime leaf;
the leaf does not import gotpl or any other workspace package.

`uv build --package goregexp --offline` produced a pure-Python sdist and
`goregexp-0.0.0-py3-none-any.whl`. Installing only that wheel without dependency
resolution into an empty CPython environment exercised compilation and named
replacement on both surfaces successfully.

## Performance Evidence

The Go surface deliberately pays for pure-Python RE2 semantics and linear-time
safety. Python `re` is substantially faster and is the recommended direct API
when Go behavior and untrusted-pattern safety are not requirements.

Seven samples of 20,000 independent surface operations produced:

| Operation | Go surface ns/op | Python surface ns/op | Python / Go |
| --- | ---: | ---: | ---: |
| Compile general pattern | 26,855 | 309 | 0.012x |
| Atomic search | 324 | 133 | 0.41x |
| General search | 12,660 | 90 | 0.007x |
| Capturing replacement | 14,025 | 236 | 0.017x |

The M6 Sprig function-heavy fixture contains one regex replacement and is the
representative extraction control. Eleven post-extraction samples produced a
68,071 ns/render median. This is +3.62% against the frozen M6 median of 65,692
ns/render and +1.93% against the 66,784 ns/render M7 post-duration control, both
below the 5% alert threshold. Output digests remained identical. The benchmark
also contained one high outlier and a 3.84% relative standard deviation, so the
small difference is not attributed solely to the adapter.

## Reproduction

```console
./scripts/check_goregexp_oracle.sh
uv run --directory packages/goregexp --frozen pytest -q
uv run --directory packages/goregexp --frozen coverage run -m pytest -q
uv run --directory packages/goregexp --frozen coverage report
uv run --directory packages/goregexp --frozen ruff check .
uv run --directory packages/goregexp --frozen pyright
uv run --directory packages/goregexp --frozen python \
  benchmarks/compare_surfaces.py --samples 7 --iterations 20000
uv run --frozen python -m benchmarks.compare \
  benchmarks/fixtures/sprig_render.json --samples 11
uv build --package goregexp --frozen
```

## M7 Integration Status

The narrow package extraction, workspace import-layer audit, built-wheel
parity matrix, internal ownership rules, and specialized-instruction decision
are complete. See `m7-package-architecture-audit.md`. Expanding the package
into a complete Go `regexp` clone is not planned without a concrete pygotpl
consumer.
