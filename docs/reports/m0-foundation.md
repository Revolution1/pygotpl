# M0 Foundation Report

## Status

M0 is technically complete except for external CI evidence. The owner selected
Apache-2.0, and the approved upstream adaptation policy, canonical license
files, PEP 639 metadata, third-party notices, and review evidence are recorded
in `docs/licensing.md` and `docs/reports/m0-license-review.md`. The repository
has not yet been pushed, so the GitHub Actions matrix cannot be claimed as
passing.

## Pinned Baselines

- Go oracle toolchain: Go 1.27.0.
- Go template reference: tag `go1.27.0`.
- Sprig reference and oracle module: v3.3.0.
- Supported Python: 3.11 and newer.
- Primary development Python: latest stable release, Python 3.14.7.
- Required uv: 0.12.5 or newer.

Exact Python development dependencies and transitive dependencies are recorded
in `uv.lock`.

## Commands

```console
uv sync --frozen --all-groups
./scripts/sync_references.sh
./scripts/check.sh
uv run --frozen python -m benchmarks.compare
```

## Fixture Formats

- `tests/conformance/schema.json` defines source-attributed template requests and
  expected output or failure.
- `benchmarks/schema.json` defines fixtures shared by Python and Go.
- `benchmarks/result-schema.json` defines the machine-readable comparison.

The initial `text/literal` fixture is independently authored and records the Go
test area used to verify the behavior. It passes through Go and Python.

## Initial Local Evidence

Environment:

- macOS on ARM64.
- CPython 3.13.7 available locally.
- Go 1.26.5.

Results:

- 13 tests passed.
- 100% statement coverage and 97% branch coverage.
- Ruff and formatting checks passed.
- Strict Pyright passed with no errors or warnings.
- Go oracle module built and tested.
- The `text/literal` smoke benchmark produced machine-readable results.

One local smoke sample measured approximately 88 ns/op for warm Python rendering
and 34 ns/op for Go, a ratio of approximately 2.6. This is not a stable
performance claim; it validates the comparison pipeline only.

## Initial CI Matrix

The configured matrix covers CPython 3.11 through 3.14 on Linux, macOS, and
Windows, plus PyPy 3.11 on Linux. Separate Linux jobs verify quality, Go
formatting and oracle builds, wheel construction and isolated installation,
and a benchmark smoke run. The current local interpreter evidence is recorded
in `m0-python-matrix.md`; hosted evidence remains pending.

## Remaining Exit Evidence

- Push the repository and observe every required GitHub Actions job passing.
