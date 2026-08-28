# M8 Acceptance Audit

> Historical architecture note: this audit predates M10 decisions D012 and
> D015. Its five-wheel and standalone `goregexp` evidence remains valid for M8,
> while the current release has three distributions, keeps the regex engine
> private under `gotpl._compat`, and provides Helm late-bound execution through
> `gotpl.exts.helm.HelmTemplateEngine`.

## Outcome

M8 is complete for its declared ecosystem scope. Sprout raw registries and
groups, reusable Helm functions, the core cross-file runtime engine, and the
miniature Helm example have executable compatibility, security, packaging, and
performance evidence.

Sprout's optional generated safe-function feature is an explicit excluded
surface under D010. The Helm chart runtime remains an example; reusable
functions live in `gotpl.funcs.helm`, and reusable cross-file execution lives in
package-root `gotpl.TemplateEngine`.

## Deliverable Evidence

| Deliverable | Evidence |
| --- | --- |
| Sprout inventory and groups | Generated 20-registry inventory, exact `all`/`hermetic` membership, packaged-resource check |
| Sprout behavior | 234 raw function evidence routes, 45 alias routes, 26 conformance tests, direct unit suites |
| Helm function map | Exact 222-name map, lazy optional serializers, missing-extra tests |
| Core multi-source runtime | Immutable `TemplateEngine`, sync/async unit tests, Helm consumer |
| Helm globals and runtime | Example-only chart/release/capability models and ten pinned Helm cases |
| Miniature CLI | Directory loader, values merge, render and output-path tests |
| Performance | Shared v1 fixture, CPython latency/memory/profile runner, native Helm benchmark |
| Security handoff | Executable ecosystem capability tests and explicit M9 matrix |

## Acceptance Gates

| Gate | Result | Evidence |
| --- | --- | --- |
| Every exposed Sprout function has an evidence route | passed | 50 exact Sprig callables, 159 direct cases, 25 supplemental contracts; aliases resolve to originals |
| Helm fixtures agree with v4.2.3 | passed | ten integration cases plus the Go fixture-parity test |
| Core wheel works without optional dependencies | passed | isolated five-wheel install with only mandatory timezone dependencies; YAML/TOML modules absent |
| Registry isolation | passed | architecture and security tests reject leakage into Go and Sprig maps |
| Sensitive capabilities are explicit | passed | environment, network, DNS, lookup, filesystem, crypto, serializer, and dynamic-source tests/matrix |
| M9 allow/deny inventory exists | passed | `docs/reports/m8-capability-matrix.md` |
| Helm profiling follows M6 boundaries | passed | compile, warm batch, static cold, dynamic cold, peak memory, Go allocations, and hotspots separated |
| Import graph uses public boundaries | passed | executable AST import-layer policy and wheel graph tests |
| Regexp work remains consumer-driven | passed | Sprout regex/regexp differential cases use the narrow `goregexp` package; no standalone expansion |

## Final Verification

The M8 full verification on CPython 3.14.7 and Go 1.27.0 produced:

- Ruff lint and format: passed;
- strict Pyright: zero errors and warnings;
- Python and workspace suite: 1,886 passed;
- combined statement/branch-aware coverage: 96%, above the active 95% gate;
- generated artifacts and all four extracted-package oracle checks: passed;
- Sprout inventory regeneration: passed;
- combined Go/Sprout, isolated Sprig, and Helm oracle module tests: passed; and
- isolated pure-Python wheel build/import/render: passed without Helm, YAML, or
  cryptography extras.

CI repeats the Python suite across CPython 3.11 through 3.14 on Linux, macOS,
and Windows, plus PyPy 3.11. It installs the `all` extra for behavioral tests,
while the package job deliberately installs no optional extras.

## Reproduction

```console
./scripts/check.sh

uv build --offline --all-packages --wheel
uv run --frozen python -m benchmarks.helm_runtime \
  --samples 7 --iterations 500 --memory-samples 25 \
  --profile-iterations 500 --top 20
go -C tools/helm_oracle test -run '^$' \
  -bench 'Benchmark(GoTextTemplate|Helm)' \
  -benchmem -benchtime=500ms -count=7
```

Generated benchmark JSON, coverage data, build directories, and isolated
environments remain uncommitted artifacts.
