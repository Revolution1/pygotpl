# M6 Benchmark Inventory

## Purpose

This inventory freezes the representative workloads that guide M6 profiling
and optimization. Shared fixtures execute through public Python APIs and Go's
native template packages. Every timed comparison renders a reference output
first and refuses to report latency when the SHA-256 digests differ.

Single-sample numbers in this document confirm that a workload is runnable;
they are not performance claims. Claims require the seven-sample methodology,
environment metadata, and variance required by `docs/performance.md`.

## Shared Go/Python Workloads

| Fixture | Mode | Primary behavior |
| --- | --- | --- |
| `parser.json` | parse, compile, parse+compile | Control-flow and associated-definition construction. |
| `literal.json` | warm render | Minimum fixed overhead for a reusable text template. |
| `text_render.json` | warm render | Range, branch, field lookup, formatting, and output. |
| `html_render.json` | warm render | Contextual HTML, URL, CSS, JavaScript, and `srcset` escaping. |
| `sprig_render.json` | warm render | Versioned Sprig registry with maps, lists, regex, crypto hashes, semver, numeric functions, and JSON. |
| `sprig_duration_render.json` | warm render | Duration-heavy Sprig adapter parsing, formatting, coercion, overflow, invalid input, and unit rounding. |
| `text_cold.json` | cold render | Construction, parsing, compilation, and rendering through a fresh template. |
| `text_writer.json` | writer render | Reusable template rendering into a reset, caller-owned buffer. |
| `named_render.json` | named render | A small associated set with nested named calls and iteration. |
| `named_large_render.json` | named render | A 33-template association with 32 nested calls. |

The fixture loader rejects unknown modes, malformed iteration counts, and a
named workload without `execute_template`. Tests freeze unique identifiers and
exercise every public Python path. The Go runner supports the same four render
modes and reports native allocations and bytes per operation.

## Python Async and Boundary Workloads

`python -m benchmarks.async_runtime` measures:

- synchronous rendering with a synchronous callback;
- async-VM rendering with that same callback;
- an immediately completing coroutine callback;
- a coroutine that yields to the event loop; and
- scheduled coroutine renders in bounded concurrent batches.

`python -m benchmarks.sync_guard` isolates the mandatory synchronous
awaitable-result guard. These Python-specific workloads have no Go comparison
because Go's template runtime does not expose Python coroutine semantics.

`python -m benchmarks.call_dispatch` compares the former per-call cached
signature lookup with construction-time signature metadata reuse against a
real contextual HTML escaper.

`python -m benchmarks.html_replacements` compares the former per-character
generator with the ordered C-level replacement path. `python -m
benchmarks.printf_cache` compares repeated Go directive parsing with a hot
lookup in the bounded directive cache. `python -m benchmarks.url_processor`
compares the former branching contextual URL loop with its immutable byte-table
replacement. All three refuse to time unequal results.

## Initial Runnable Baselines

The August 26, 2026 smoke run produced matching Python and Go output digests
for all new shared modes:

| Workload | Python ns/op | Go ns/op | Ratio |
| --- | ---: | ---: | ---: |
| Cold text render | 76,148 | 2,932 | 25.97x |
| Reused text writer | 14,168 | 762 | 18.59x |
| Small named set | 28,433 | 1,105 | 25.73x |
| Large named set | 80,376 | 2,136 | 37.63x |

These are intentionally retained as smoke observations rather than regression
thresholds. The final M6 report will replace them with independent sample
distributions on the recorded reference environment.

## Profile-Guided Next Slice

CPython cumulative profiles of the frozen warm workloads identify pipeline and
registered-function dispatch as the first optimization target. In the HTML
fixture, generic callable adaptation is repeatedly applied to internal trusted
escapers; in the text fixture, `printf` parsing and dispatch are prominent.

The first profile-guided slice benchmarked a prevalidated callable-dispatch
design and then changed its runtime representation. The implementation prepares
immutable signature metadata once, reuses a complete built-in registry across
renders, and skips validation only for signatures whose arity and annotations
cannot reject a positional call. An August 26, 2026 seven-repeat run of the
checked-in dispatch benchmark measured the real escaper path at approximately
1,001 ns for repeated cached lookup and 920 ns for prepared dispatch, a 1.09x
local speedup. End-to-end samples remain the authority for deciding whether to
retain further dispatch changes.

The audit also corrected `text_render.json` to use a cross-runtime string
formatting workload. JSON numbers decode as Python integers but Go `float64`
values, so the former `%04d` case did not represent equal typed inputs and was
properly rejected by the output-digest gate.

The second profile-guided slice replaced per-character HTML escaping with
ordered `str.replace` calls while preserving ampersand-first entity handling.
An August 26, 2026 seven-repeat local benchmark measured approximately 2,699 ns
for the former generator and 449 ns for the replacement path, a 6.00x local
speedup. The contextual HTML and security suites retained complete branch
coverage and matching Go/Python benchmark output. No end-to-end speedup is
claimed from a noisy three-sample observation.

The third slice adds a 4,096-entry cache for immutable `printf` directive
parses. Its checked seven-repeat benchmark measured approximately 928 ns for a
repeated parse and 27.5 ns for a hot lookup, a 33.7x local speedup. A unit test
fills the cache with 4,200 distinct formats and verifies that it remains at its
declared limit; another renders concurrently through eight threads and checks
both output and shared-cache state. The cache stores only format syntax, never
rendered values.

The accompanying cache audit removed the remaining unbounded decorators.
Unicode property caches are capped at 256 entries, the two-key built-in
function registry is explicitly capped at two, and the existing callable,
regular-expression, and timezone caches retain their declared finite limits.
All source caches now expose an explicit `maxsize`.

## Python Memory Baseline

`python -m benchmarks.memory` prepares the same public operation as the timing
runner and measures one render per sample. It reports a `tracemalloc` peak
increment plus retained snapshot bytes and blocks while the returned result is
reachable. These fields deliberately do not reuse Go's `allocs/op` or `B/op`
names because the standard Python tracer cannot observe total transient
allocator traffic.

An August 26, 2026 run on CPython 3.13.7, macOS 26.5.2, and arm64 produced the
following 25-sample medians:

| Workload | Peak traced bytes/render | Retained bytes/render | Retained blocks/render |
| --- | ---: | ---: | ---: |
| Warm text control render | 3,666 | 2,151 | 31 |
| Reused text writer | 2,568 | 1,272 | 19 |
| Warm contextual HTML render | 8,815 | 7,289 | 65 |

The writer result demonstrates the expected lower peak when the caller owns
and reuses the output buffer. Retained samples show allocator warm-up drift, so
the report preserves every raw value and treats the median as diagnostic
evidence rather than a cross-runtime allocation claim.

## Execution Context and Named-Call Optimization

Profiles of `named_large_render.json` showed that recursive public runtime
entry, context construction, and eagerly empty scope/range stacks dominated
the 32-call chain; output writes accounted for approximately one percent of
profiled time. Three retained changes address that evidence:

- the three immutable `ValueAdapter` modes are shared rather than rebuilt per
  template call;
- variable scopes, `with` dot stacks, and range stacks allocate only when an
  instruction needs them; and
- sync and async template calls use a lazily created tuple caller stack instead
  of Python recursion. Root execution remains in locals and therefore pays no
  caller-frame allocation.

The frame change also closes the recorded compatibility gap with Go:
both VMs execute a tested 1,500-template finite chain and enforce Go's non-wasm
maximum depth of 100,000 with the corresponding diagnostic. Each callee still
gets an isolated root scope, and innermost source locations remain intact.

On August 26, 2026, seven-sample local slice measurements produced the
following medians:

| Slice | Before | After | Change |
| --- | ---: | ---: | ---: |
| Fresh versus shared adapter, named-large | 75,473 ns | 71,951 ns | -4.7% |
| Eager versus lazy context storage, named-large | 56,011 ns | 53,645 ns | -4.2% |
| Recursive versus explicit caller stack, named-large | 53,645 ns | 35,314 ns | -34.2% |

The final caller-stack sample retained matching output and measured literal,
text control, and contextual HTML medians of 1,311 ns, 18,450 ns, and 144,462
ns respectively. This avoids the 2-3% non-call regression observed in a
discarded design that allocated a frame object for every root render.

The final 25-sample named-large memory median is 8,093 peak traced bytes per
render. The original eager/fresh-context path measured 21,069 bytes, a 61.6%
reduction under the explicitly non-Go-comparable `tracemalloc` metric. A
list-backed string builder was also measured and rejected: it was 1.5% slower
on text, effectively tied on HTML, and within 0.2% noise on named-large, so the
runtime retains `StringIO` for returned strings and direct writes for
caller-owned buffers.

## Python-AST Backend Feasibility

The checked-in `benchmarks.backend_feasibility` profiler computes the generous
Amdahl upper bound obtained by making all VM dispatcher self time free. The
literal, text control, contextual HTML, and named-large bounds were 1.424x,
1.247x, 1.063x, and 1.644x respectively. Real generated code would achieve
less while still needing sync/async parity, the explicit caller stack, source
locations, short-write behavior, and every HTML security invariant.

M6 therefore retains the instruction VM as the sole production backend. The
evidence, maintenance analysis, and objective reconsideration gates are frozen
in `reports/m6-ast-backend-decision.md`.

The optimization must continue to preserve caller-function arity and
annotation errors, exception chaining, async await boundaries, HTML security,
and every frozen conformance fixture. Python allocation measurement remains a
separate deliverable because `tracemalloc` peak or surviving-block counts must
not be mislabeled as Go-style total allocations per operation.

The CPython 3.14 exit gate passes 1,345 tests and reports 7,496 executable
statements with zero misses and 99% branch-aware coverage. Ruff, strict
Pyright, all contextual security tests, the pinned Go oracle module,
generated-artifact checks, and output-digest checks pass. Reusable templates
inspect an unhashable callable signature once across repeated sync and async
renders.
