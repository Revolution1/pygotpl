# Performance

## Objective

pygotpl targets top-tier pure Python performance while publishing an honest,
reproducible comparison with Go's native template engines. Compatibility and
security take precedence over benchmark results.

The Go baseline, Python-engine comparison, comprehensive profiling, and native
accelerator feasibility work belong to M6. Later ecosystem milestones measure
their own representative workloads with this methodology and feed them back
into the continuing performance history.

The canonical combined M6 results are published in
[`reports/m6-complete-performance-report.md`](reports/m6-complete-performance-report.md).

## Current Measured Snapshot

On the report's Apple M5 / CPython 3.14.7 environment, representative warm
renders measured as follows. These are prioritization baselines, not latency
guarantees for other templates or machines.

| Workload | pygotpl compared with Go | pygotpl compared with Jinja |
| --- | ---: | ---: |
| Text control flow | 14.13x | 3.28x |
| Contextual HTML | 9.21x | 2.27x |
| Sprig-heavy | 7.28x | not measured in the Jinja fixture set |
| Synchronous callback | not measured in the Go fixture set | 0.90x |

The [complete report](reports/m6-complete-performance-report.md) owns the raw
measurements, environment, memory results, uncertainty, and interpretation.

## Reproduce in This Repository

Install the locked benchmark toolchain once, then keep every run in that
environment:

```console
uv sync --frozen --group benchmark
```

Go comparison commands also require the pinned Go toolchain and repository
fixtures. They verify output equality before reporting timing results.

## Benchmark Categories

Measure these phases independently:

- Lexing.
- Parsing.
- Compilation.
- Cold rendering, including parse and compile.
- Warm rendering with a reusable compiled template.
- Buffered and writer-based rendering.
- Text and contextual HTML rendering.
- Built-in-heavy and Sprig-heavy pipelines.
- Synchronous callbacks.
- Async callbacks and concurrent async rendering.
- Small and large named-template sets.
- Equivalent Jinja text, autoescaped HTML, sync, async, and cache workloads.
- Capability-matched Mako and Chameleon text and HTML workloads.

## Shared Fixtures

Python and Go benchmarks consume semantically equivalent checked-in fixtures.
The M1 parser/compiler comparison can be run with:

```console
uv run --frozen python -m benchmarks.parser_baseline
```

It reports Python parse, compile, and combined timings separately, alongside
Go's native `Template.Parse` timing on the same source fixture.
Warm benchmarks exclude process startup, fixture decoding, and compilation.
Cold benchmarks state exactly which phases are included.

The shared Sprig-heavy warm-render comparison can be run with:

```console
uv run --frozen python -m benchmarks.compare benchmarks/fixtures/sprig_render.json
uv run --frozen python -m benchmarks.compare benchmarks/fixtures/sprig_duration_render.json
```

Its request selects the explicit `sprig-v3.3.0` function profile. Benchmark
profiles are versioned so a future Sprig upgrade cannot silently change the
comparison target.

The contextual HTML comparison can be sampled independently with:

```console
uv run --frozen python -m benchmarks.compare benchmarks/fixtures/html_render.json --samples 7
```

The contextual URL hot path has a separate branching-versus-table comparison:

```console
uv run --frozen python -m benchmarks.url_processor \
  --samples 7 --iterations 100000
```

It verifies normalization and escaping output before timing representative
plain, query, path, percent-escape, and UTF-8 inputs.

Both runners hash a reference render before timing, and the comparison aborts
if Python and Go produce different output. Multi-sample output preserves raw
measurements and reports the median, range, and relative standard deviation.
The initial measured baseline is recorded in
[`reports/m5-html-performance.md`](reports/m5-html-performance.md).

The M6 Python-ecosystem comparison can be reproduced with:

```console
uv run --frozen python -m benchmarks.jinja_compare --samples 7 --memory-samples 25
uv run --frozen python -m benchmarks.python_engine_compare --samples 7 --memory-samples 25
```

The measured results and capability caveats are recorded in
[`reports/m6-python-engine-comparison.md`](reports/m6-python-engine-comparison.md).

The M8 cross-file runtime and Helm integration workload can be reproduced with:

```console
uv run --frozen python -m benchmarks.helm_runtime \
  --samples 7 --iterations 500 --memory-samples 25 \
  --profile-iterations 500 --top 20
go -C tools/helm_oracle test -run '^$' \
  -bench 'Benchmark(GoTextTemplate|Helm)' \
  -benchmem -benchtime=500ms -count=7
```

Both commands consume `benchmarks/helm/fixtures/runtime-v1.json`. The Python
runner separates core compilation, reusable warm batch execution, static Helm
example construction/rendering, and dynamic `tpl` rendering. The Go benchmark
uses the pinned Helm engine rather than a locally simulated function map. The
measured baseline and hotspot interpretation are recorded in
[`reports/m8-helm-performance.md`](reports/m8-helm-performance.md).

Complete unpacked charts can be measured with separate load, cold render,
manifest preparation, and end-to-end phases:

```console
uv run --frozen --extra all python -m benchmarks.helm_chart \
  /path/to/unpacked/chart -f /path/to/values.yaml \
  --samples 7 --profile-iterations 1 --top 15
```

The runner loads dependencies from the local chart and records the chart
version and output digest. Third-party charts are deliberately not checked in;
the tested chart versions, semantic comparison, measured medians, and remaining
hotspots are recorded in
[`reports/m10-helm-complex-charts.md`](reports/m10-helm-complex-charts.md).

Shared render fixtures may declare one of four modes:

- `warm_render` reuses a compiled template and returns a string;
- `cold_render` constructs, compiles, and renders a fresh template;
- `writer_render` reuses both the compiled template and caller-owned buffer;
- `named_render` executes an associated template selected by
  `execute_template`.

The complete M6 workload map, including Python-specific async and concurrent
measurements, is recorded in
[`reports/m6-benchmark-inventory.md`](reports/m6-benchmark-inventory.md).

Each report should include latency or throughput, relative Go ratio, and memory
or allocation data where the runtimes expose comparable measurements.

Go remains the primary compatibility and native-performance reference. Jinja,
Mako, and Chameleon are separate Python-ecosystem references and must not be
mixed into Go ratio or compatibility claims. Cross-engine fixtures validate
equivalent business output rather than claiming syntax or contextual-escaping
equivalence. Reports must identify optimization, escaping, async,
template-cache, bytecode-cache, and auto-reload capabilities and configuration,
separate cold construction from warm rendering, and mark unsupported features
instead of emulating them outside the engine.

Python memory can be sampled independently on the exact same prepared public
operation used by the timing runner:

```console
uv run --frozen python -m benchmarks.memory benchmarks/fixtures/html_render.json --samples 25
```

This reports the `tracemalloc` peak increment for one render and the retained
snapshot byte and block deltas while that render result remains reachable. It
does not populate Go-style `allocations_per_op` or `bytes_per_op`: Python's
standard tracer does not count total transient allocator traffic, so those
metrics are not directly comparable. Raw samples, variance, environment data,
and the reference output digest are retained under
`benchmarks/memory-schema.json`.

The generous upper bound from eliminating synchronous VM dispatcher self time
can be reproduced with:

```console
uv run --frozen python -m benchmarks.backend_feasibility benchmarks/fixtures/text_render.json
```

This is an Amdahl-style feasibility diagnostic, not a generated-backend
benchmark. The M6 production decision and reconsideration gates are recorded in
[`reports/m6-ast-backend-decision.md`](reports/m6-ast-backend-decision.md).

The retained linked-IR sync optimization can be compared directly with the
generic reference VM on paired, alternating samples:

```console
uv run --frozen python -m benchmarks.linked_ir \
  --samples 21 --iterations 3000 --warmup 500 --link-samples 51
```

The runner verifies output equality, reports generic and linked warm latency,
and measures link latency plus traced retained and peak bytes separately. Its
default fixtures cover text control flow, contextual HTML, Sprig-heavy calls,
and a 33-template named association. Explicit `writer_render` fixtures execute
the real caller-owned writer path. Cold construction is measured by the
canonical comparison runner because the linked A/B runner intentionally starts
from an already compiled generic program.

## Tooling

- Python timing: `pyperf`.
- Go timing and allocation: `go test -bench -benchmem`.
- Python retained allocations and peak memory: `tracemalloc` plus targeted
  profilers, with metric names distinct from Go's total allocations.
- Historical tracking: a dedicated, stable runner or a benchmark service.

Do not draw conclusions from a single run on a noisy shared CI worker.

## Optimization Order

1. Establish reference behavior and representative benchmarks.
2. Profile before changing the hot path.
3. Reduce repeated semantic work through compilation.
4. Reduce allocations and dynamic dispatch.
5. Add specialized value-access and output paths.
6. Consider a Python-AST code-generation backend only after VM parity is strong.
7. Prototype a native accelerator only for a measured, self-contained hot path
   after ordinary Python and backend opportunities are exhausted.

The M10 linked-IR and contextual URL follow-up is closed. Further attempts to
reduce Python-level control-flow interpretation belong to the planned
[`M12 generated synchronous backend`](milestones/m12-generated-sync-backend.md)
and must meet that milestone's feasibility and retention gates before changing
the production executor.

The sync path must not pay unconditional coroutine or event-loop costs. The
async path should inspect awaitability only at boundaries that can produce
awaitables.

The default distribution remains fully functional pure Python. Native
prototyping is deferred when pygotpl is no more than 1.20x slower than Jinja on
at least two representative non-trivial warm workloads and no adopted latency
budget is missed. Otherwise a Cython, C, or Rust accelerator must remain
optional, preserve the pure Python fallback, and avoid duplicating compatibility
semantics. It is retained only with output parity and at least a 25% median
end-to-end improvement on two representative non-trivial workloads. Profilers
locate candidate work; only sampled benchmark results can support the decision.

The comprehensive profiler and rejected Cython sync-VM prototype can be
reproduced with:

```console
uv run --frozen python -m benchmarks.profile_suite --iterations 20000 --sampling-seconds 1 --sampling-interval 0.001 --allocation-iterations 25 --top 20
uv run --frozen python -m benchmarks.native_accelerator --samples 7
```

See [`reports/m6-profiling.md`](reports/m6-profiling.md) and
[`reports/m6-native-accelerator-decision.md`](reports/m6-native-accelerator-decision.md).

## Environment and Extension Cost

`Environment` validates and prepares shared function configuration once, then
reuses it when constructing templates and associations. Retain an environment
when policy is shared, and retain the resulting `Template`, `HTMLTemplate`, or
`TemplateEngine` when sources are stable. Rebuilding either object for every
render turns construction cost into request latency.

Ordinary function-only templates do not allocate a runtime extension session.
A session is created only when the selected registry contains a
`ContextFunction`; nested calls then share budget counters, depth, extension
state, and the bounded dynamic-source cache for that top-level render.

On the Apple M5 / CPython 3.14.7 environment used for the extension design
follow-up, prepared-registry reuse reduced sampled static Helm cold rendering
from 0.692 ms to 0.497 ms and dynamic `tpl` cold rendering from 0.745 ms to
0.559 ms. Median traced peak memory fell from 86,449 to 72,929 bytes. These are
construction-path measurements, not latency guarantees. The exact command,
samples, and interpretation are recorded in the
[runtime extension design](reports/m10-unified-environment-design.md#implementation-evidence).

Helm's dynamic-source cache is scoped to one top-level render and one immutable
parent association. Repeated `tpl` strings within that render can reuse compiled
work; values, budgets, and extension state do not leak into later renders.

## Opt-in Policy Cost

M9 measures explicit policy cost separately from default rendering.
`benchmarks/sandbox.py` compares the same validated warm render with no policy,
an execution budget, and the strict mapping-only sandbox. It must not be used
to justify weakening a policy check. The current evidence and reproduction
command are in [`reports/m9-sandbox.md`](reports/m9-sandbox.md).

## Regression Policy

Release-labeled pull requests run smoke benchmarks and sampled comparisons.
Final comparisons run again for `v*` release tags. Ordinary development pushes,
unlabeled pull requests, and calendar schedules do not allocate benchmark
runners; maintainers may request an explicit manual run.

- A statistically credible regression above 5% produces an alert.
- A regression above 10% in a representative hot path blocks a release unless
  it is explicitly accepted and documented.
- Performance claims require a checked-in benchmark case and reproducible
  command.

Every release report records environment, Python version, Go version, fixture
revision, sample count, and uncertainty.

Headline Python comparisons use the latest stable CPython release. The benchmark
suite also tracks every supported Python minor version so a newer interpreter
does not conceal regressions for supported users.

The automated history workflow runs the full sampled render, parser, async, and
memory commands for release-labeled pull requests, `v*` tags, and manual
dispatches. It uploads revision-named JSON artifacts for 90 days.
Hosted-runner artifacts are for trend inspection; release blocking still
requires the stable-hardware methodology above.
