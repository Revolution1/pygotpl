# M6 Performance Hardening Report

## Outcome

M6 establishes a reproducible Go/Python benchmark suite, adds honest Python
memory metrics, removes measured VM overhead, bounds every source cache, closes
the named-template recursion gap, and records an evidence-based decision not to
add a Python-AST backend at this time.

This report is the completed August 26, 2026 Go-comparison baseline. The
milestone was later reopened for a separate Jinja comparison, broader profiling,
and optional native-accelerator feasibility work. Those follow-up results are
recorded in `m6-python-engine-comparison.md`, `m6-profiling.md`, and
`m6-native-accelerator-decision.md` rather than rewriting this baseline.
The canonical combined view is `m6-complete-performance-report.md`.

The final implementation passes the complete compatibility, async, contextual
HTML security, type, formatting, generated-artifact, and Go-oracle gates.

## Reference Environment

- Date: August 26, 2026.
- Hardware: Apple M5, 10 cores, 32 GB memory.
- Operating system: macOS 26.5.2, arm64.
- Python: CPython 3.14.7.
- Go: Go 1.27.0, darwin/arm64.
- Worktree: pre-initial-commit project state; the historical runner records
  `uncommitted` until the repository has a Git revision.

Every headline latency is the median of seven independent samples. Tables
include population relative standard deviation (RSD). Each shared render
comparison hashes a reference result and aborts before reporting timings when
Python and Go outputs differ.

## Parser and Compiler

The Python parser and compiler are measured separately and together. Go's
native parse benchmark includes its corresponding parse/prepare work.

| Phase | Median ns/op | RSD |
| --- | ---: | ---: |
| Python parse | 70,814 | 5.80% |
| Python compile of an existing parse tree | 12,484 | 0.96% |
| Python parse + compile | 86,161 | 1.28% |
| Go parse | 3,189 | 0.63% |

The paired Python parse+compile / Go parse median is 27.02x. Go reports 89
allocations and 5,496 bytes per operation on this fixture.

The isolated Python parse distribution contains one high sample and has 5.80%
RSD. Its median is retained, but no fine-grained parser-regression claim is
based on this run.

## Shared Render Comparisons

| Workload | Python median ns/op | Python RSD | Go median ns/op | Go RSD | Python / Go | Go allocs/op | Go B/op |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Literal | 1,036 | 0.37% | 29 | 0.00% | 35.74x | 2 | 128 |
| Text control | 15,569 | 2.96% | 1,102 | 1.09% | 14.13x | 35 | 808 |
| Contextual HTML | 121,746 | 0.58% | 13,239 | 1.20% | 9.21x | 335 | 7,162 |
| Sprig function-heavy | 65,692 | 0.23% | 9,048 | 0.71% | 7.28x | 160 | 8,363 |
| Cold text parse + compile + render | 71,210 | 0.31% | 2,567 | 1.62% | 27.70x | 77 | 4,522 |
| Reused caller-owned writer | 10,953 | 0.73% | 692 | 0.83% | 15.90x | 17 | 384 |
| Small named-template set | 15,678 | 0.25% | 956 | 4.47% | 16.41x | 29 | 1,152 |
| Large named-template set | 25,637 | 0.54% | 1,845 | 1.71% | 13.91x | 68 | 4,258 |

The text Python and small-named Go distributions have the two highest render
RSD values, 2.96% and 4.47%. Their medians are reported, but no fine-grained
claim is based on those distributions. The output digest matched in every
sample for all eight workloads. The Go 1.27 baseline is faster than the former
Go 1.26.5 baseline on every shared workload; `go-1.27-upgrade.md` records the
migration effect.

## Python Async Runtime

These Python-specific measurements have no Go equivalent. Each result uses
20,000 operations per sample; the concurrent case schedules bounded batches of
32 renders.

| Path | Median ns/op | RSD |
| --- | ---: | ---: |
| Sync VM with sync callback | 1,976 | 1.36% |
| Async VM with sync callback | 2,287 | 1.59% |
| Async VM with immediate coroutine | 2,354 | 1.09% |
| Async VM with yielding coroutine | 16,006 | 0.80% |
| Yielding coroutine, concurrency 32 | 5,816 | 0.53% |

The async VM's no-await path is 1.157x the synchronous path at the paired
median. The synchronous VM performs no event-loop creation, coroutine polling,
or unconditional async dispatch; it only rejects an awaitable at a boundary
that produced one.

## Python Memory

Python's standard tracer cannot report Go-compatible total `allocs/op` or
`B/op`. The Python fields therefore use distinct names and measure one render
per sample: peak traced-byte increment, plus retained snapshot bytes and blocks
while the result remains reachable.

| Workload | Peak traced bytes/render | Peak RSD | Retained bytes/render | Retained blocks/render |
| --- | ---: | ---: | ---: | ---: |
| Text control | 3,933 | 0.32% | 2,447 | 38 |
| Contextual HTML | 8,911 | 0.14% | 7,561 | 72 |
| Large named-template set | 8,317 | 0.15% | 3,509 | 51 |

The memory command preserves all 25 raw samples. These values are suitable for
tracking pygotpl against itself, not for direct comparison with Go's allocator
counters.

## Retained Optimizations

M6 retained only changes supported by profiles, equivalent-output checks, and
focused benchmarks:

- callable signatures and trusted function metadata are prepared once;
- contextual HTML replacement uses ordered C-level string replacements;
- immutable `printf` directives use a bounded 4,096-entry cache;
- immutable value-adapter modes are shared;
- scope, `with`, and range storage allocate lazily;
- named-template execution uses a lazy explicit caller stack rather than
  Python recursion; and
- the existing `StringIO` return buffer and direct caller-writer path remain
  after a list-backed alternative failed to improve representative workloads.

The named-template work also matches Go's non-wasm maximum depth of 100,000.
Both sync and async VMs execute a tested 1,500-template finite chain while
preserving isolated callee variables and innermost error locations.

Local slice measurements, commands, rejected alternatives, cache limits, and
memory deltas are detailed in `m6-benchmark-inventory.md`. Those slice results
are not mixed with the CPython 3.14 headline table above.

## Backend Decision

The checked-in feasibility profiler computes the impossible upper bound where
all VM dispatcher self time disappears. Bounds were 1.424x for literal, 1.247x
for text control, 1.063x for contextual HTML, and 1.644x for large named
templates. The complex HTML workload is dominated by semantic and security
helpers, while a generated named backend must still preserve the explicit
100,000-depth caller stack.

M6 therefore retains the instruction VM as the sole production backend. The
maintenance analysis and objective reopening gates are in
`m6-ast-backend-decision.md`.

## Historical Tracking

`.github/workflows/performance-history.yml` runs on relevant pushes to `main`,
weekly, and on manual dispatch. Its fixed Python 3.14 and Go 1.27 job records:

- seven-sample distributions for all eight shared render workloads;
- seven-sample parser and compiler distributions;
- seven-sample sync and async runtime distributions; and
- 25-sample Python memory results for text, HTML, and large named templates.

The artifact name includes the Git revision and is retained for 90 days.
Hosted-runner results are trend evidence only because hardware noise is not
controlled; the 5% regression alert and 10% release block require stable
hardware and statistically credible samples.

## Reproduction

From the repository root with the locked environments installed:

```console
python -m benchmarks.history --samples 7 --output benchmark-history.json
python -m benchmarks.parser_baseline --samples 7 --output parser-history.json
python -m benchmarks.async_runtime --samples 7 --iterations 20000 --warmup 1000 --concurrency 32 --output async-history.json
python -m benchmarks.memory benchmarks/fixtures/html_render.json --samples 25 --output memory-html.json
python -m benchmarks.backend_feasibility benchmarks/fixtures/html_render.json
```

Use `uv run --python 3.14 --frozen` before each Python command to reproduce the
reported interpreter and lockfile selection. The complete project gate is
`./scripts/check.sh`.
