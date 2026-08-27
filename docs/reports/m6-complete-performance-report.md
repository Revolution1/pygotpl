# M6 Complete Performance Report

## Executive Summary

This is the canonical consolidated performance report for M6. It combines the
Go comparison, Python-template-engine comparison, memory measurements,
deterministic and sampled profiles, retained optimizations, and native
accelerator decision. The narrower source reports remain available as evidence
ledgers and are linked at the end.

pygotpl is a pure Python compatibility engine, so Go remains the semantic and
native-performance reference while Jinja is the primary Python performance
reference. Mako and Chameleon provide supplementary ecosystem context.

The principal findings are:

- pygotpl is 7.28x to 35.74x slower than Go on the measured shared workloads;
- warm text control rendering is 3.28x Jinja, while contextual HTML rendering
  is 2.27x Jinja;
- synchronous callbacks and all measured async shapes are between 0.90x and
  0.99x Jinja, so async execution is not a current bottleneck;
- pygotpl uses less traced peak and retained memory than Jinja, Mako, and
  Chameleon on the comparable measured renders;
- remaining text cost is distributed across VM dispatch, operand and command
  evaluation, value lookup, dynamic type checks, and Go formatting;
- HTML adds substantial contextual URL, content-classification, escaping, and
  callable-boundary cost; and
- compiling the existing sync VM with Cython improved text by 9.39% and HTML by
  3.76%, failing the required 25% improvement on two workloads. No native
  accelerator is retained.

Performance work should next target fewer Python-level boundaries in compiled
pipelines and context-specialized HTML instructions. Parser work is secondary
to warm rendering, and further async or native-extension work is not currently
justified.

## Scope and Interpretation

The report covers parsing and compilation; warm, cold, writer, named-template,
Sprig-heavy, and contextual HTML renders; synchronous and asynchronous
callbacks; Python traced memory; Jinja 3.1.6, Mako 1.4.1, and Chameleon 4.6.0;
three profiling methods; and Python-AST and native feasibility decisions.

Go comparisons require identical output digests and use shared Go/Python
fixtures. Python-engine fixtures validate equivalent business output, but do
not claim syntax, escaping, cache, or compilation equivalence. pygotpl
implements Go-compatible contextual HTML rewriting, Jinja uses autoescape,
Mako uses an explicit MarkupSafe `h` filter in the benchmark, and Chameleon
uses `PageTemplate` context-aware escaping.

Developer-machine timings are evidence for prioritization, not portable
latency guarantees. Release-blocking claims require repetition on stable
hardware under the regression policy in `docs/performance.md`.

## Reference Environment

- Date: August 26, 2026.
- Hardware: Apple M5, 10 cores, 32 GB memory.
- Operating system: macOS 26.5.2, arm64.
- Python: CPython 3.14.7.
- Go: Go 1.27.0, darwin/arm64.
- Jinja: 3.1.6.
- Mako: 1.4.1.
- Chameleon: 4.6.0.
- Cython prototype: 3.3.0.
- Repository state: pre-initial-commit; historical metadata reports
  `uncommitted` until a Git revision exists.

Unless noted otherwise, headline latency is the median of seven independent
samples. The supplementary Mako and Chameleon rerun uses nine samples. Results
retain raw values, minimum, maximum, and population relative standard deviation
(RSD). Memory results use 25 samples.

## Go Parser and Compiler Comparison

Go's parse result includes the native parse and prepare work needed by its
template representation. Python parse and compile are also reported
independently.

| Phase | Median ns/op | RSD |
| --- | ---: | ---: |
| Python parse | 70,814 | 5.80% |
| Python compile of an existing tree | 12,484 | 0.96% |
| Python parse and compile | 86,161 | 1.28% |
| Go parse | 3,189 | 0.63% |

Python parse and compile is 27.02x Go parse on this fixture. Go reports 89
allocations and 5,496 bytes per operation. The parser profile shows distributed
cost rather than a dominant algorithmic hotspot: lexer construction, lexer
actions, token creation, enum hashing, parser advancement, semantic validation,
and compiler object construction all contribute.

## Go Shared Render Comparison

Every row renders the same checked-in request through Python and Go, validates
the output digest, and then measures the declared execution phase.

| Workload | Python ns/op | Python RSD | Go ns/op | Go RSD | Python / Go | Go allocs/op | Go B/op |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Literal | 1,036 | 0.37% | 29 | 0.00% | 35.74x | 2 | 128 |
| Text control | 15,569 | 2.96% | 1,102 | 1.09% | 14.13x | 35 | 808 |
| Contextual HTML | 121,746 | 0.58% | 13,239 | 1.20% | 9.21x | 335 | 7,162 |
| Sprig function-heavy | 65,692 | 0.23% | 9,048 | 0.71% | 7.28x | 160 | 8,363 |
| Cold text parse, compile, and render | 71,210 | 0.31% | 2,567 | 1.62% | 27.70x | 77 | 4,522 |
| Reused caller-owned writer | 10,953 | 0.73% | 692 | 0.83% | 15.90x | 17 | 384 |
| Small named-template set | 15,678 | 0.25% | 956 | 4.47% | 16.41x | 29 | 1,152 |
| Large named-template set | 25,637 | 0.54% | 1,845 | 1.71% | 13.91x | 68 | 4,258 |

The large ratio on a literal template reflects fixed Python call and runtime
setup overhead over almost no template work. The more representative complex
warm workloads narrow the ratio, but Go remains substantially faster as a
native compiled runtime.

## Jinja Comparison

Jinja is configured with optimization enabled, `auto_reload=False`, a 400-entry
template cache, strict undefined values, and autoescape for HTML. Cold timings
include environment/template construction and compilation; warm timings reuse
the compiled template.

| Workload | pygotpl ns/op | Jinja ns/op | pygotpl / Jinja | pygotpl RSD | Jinja RSD |
| --- | ---: | ---: | ---: | ---: | ---: |
| Warm callback | 2,547 | 2,795 | 0.90x | 0.79% | 3.63% |
| Warm HTML autoescape | 6,483 | 2,852 | 2.27x | 7.39% | 8.63% |
| Warm text control | 12,661 | 3,848 | 3.28x | 0.57% | 0.78% |
| Cold callback | 20,666 | 112,507 | 0.18x | — | — |
| Cold HTML autoescape | 270,776 | 121,095 | 2.23x | — | — |
| Cold text control | 72,426 | 239,817 | 0.30x | — | — |

The adopted native-deferral condition required pygotpl to be no more than
1.20x slower than Jinja on at least two representative non-trivial warm
workloads. Both text and HTML exceed that threshold, so profiling and a native
prototype were required. The HTML samples are noisier than the text samples,
but their observed range is not close enough to change the gate decision.

Cold results favor pygotpl on the callback and text fixtures because
construction and compilation strategies differ. Cold HTML remains slower
because pygotpl performs contextual analysis and rewriting.

### Async Comparison

| Path | pygotpl ns/op | Jinja ns/op | pygotpl / Jinja |
| --- | ---: | ---: | ---: |
| Sync function on sync runtime | 2,528 | 2,776 | 0.91x |
| Sync function on async runtime | 2,892 | 3,221 | 0.90x |
| Immediate coroutine | 2,975 | 3,329 | 0.90x |
| Yielding coroutine | 17,360 | 17,476 | 0.99x |
| Yielding coroutine, concurrency 32 | 6,670 | 7,019 | 0.96x |

The synchronous VM does not create or inspect an event loop unconditionally.
The async VM only awaits at boundaries that can produce awaitables. Profiles of
the yielding workload are dominated by event-loop waiting rather than pygotpl
execution, so further async optimization is deferred.

### Jinja Cache and Memory

Jinja cache-enabled lookup rendered in 3,052 ns/op versus 119,750 ns/op with
the cache disabled, a ratio of 0.025x. Cache configuration is therefore always
reported with timings.

| Workload | pygotpl peak bytes | Jinja peak bytes | pygotpl retained bytes | Jinja retained bytes |
| --- | ---: | ---: | ---: | ---: |
| Callback | 1,928 | 3,880 | 1,158 | 2,360 |
| HTML | 2,241 | 4,039 | 1,475 | 2,363 |
| Text | 2,902 | 4,283 | 1,506 | 2,354 |

These are `tracemalloc` single-render peak increments and retained snapshot
deltas, not total allocation traffic or Go-compatible allocation counts.

## Mako and Chameleon Comparison

These engines are supplementary references only. Neither exposes a directly
comparable async render path, so async support is reported as unsupported
rather than simulated.

| Workload | pygotpl ns/op | Mako ns/op | Chameleon ns/op | pygotpl / Mako | pygotpl / Chameleon |
| --- | ---: | ---: | ---: | ---: | ---: |
| Warm HTML escape | 3,727 | 2,377 | 1,870 | 1.57x | 1.99x |
| Warm text interpolation | 2,251 | 2,148 | 1,625 | 1.05x | 1.39x |
| Cold HTML | 215,566 | 121,733 | 1,975,312 | 1.77x | 0.11x |
| Cold text | 18,928 | 120,602 | 2,318,982 | 0.16x | 0.01x |

The supplementary rerun reduced pygotpl text RSD to 5.08%, but Mako HTML had a
29.47% RSD outlier. The medians provide ecosystem context, not a stable-hardware
release claim.

| Workload | pygotpl peak bytes | Mako peak bytes | Chameleon peak bytes | pygotpl retained bytes | Mako retained bytes | Chameleon retained bytes |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| HTML | 1,972 | 4,577 | 5,102 | 1,380 | 3,356 | 2,572 |
| Text | 1,696 | 4,430 | 3,942 | 1,006 | 3,326 | 2,550 |

## Python Async Runtime Baseline

The independent pygotpl runtime benchmark uses 20,000 operations per sample
and batches concurrent work in groups of 32.

| Path | Median ns/op | RSD |
| --- | ---: | ---: |
| Sync VM with sync callback | 1,976 | 1.36% |
| Async VM with sync callback | 2,287 | 1.59% |
| Async VM with immediate coroutine | 2,354 | 1.09% |
| Async VM with yielding coroutine | 16,006 | 0.80% |
| Yielding coroutine, concurrency 32 | 5,816 | 0.53% |

The no-await async/sync ratio is 1.157x. This overhead is isolated to callers
that choose the async API and is not paid by synchronous rendering.

## Python Memory Baseline

The shared representative operations also record Python-only memory history.

| Workload | Peak traced bytes/render | Peak RSD | Retained bytes/render | Retained blocks/render |
| --- | ---: | ---: | ---: | ---: |
| Text control | 3,933 | 0.32% | 2,447 | 38 |
| Contextual HTML | 8,911 | 0.14% | 7,561 | 72 |
| Large named-template set | 8,317 | 0.15% | 3,509 | 51 |

These larger shared fixtures differ from the smaller Python-engine comparison
fixtures above. Both datasets are appropriate for pygotpl trend tracking, but
neither should be compared directly with Go's allocator counters.

## Comprehensive Profile Results

Profiling runs outside headline timings. Each workload used 20,000
deterministic operations, at least one second of 1 ms stack sampling, and 25
allocation-diff operations.

| Workload | Deterministic total | Stack samples | Sampled ops | Peak traced bytes | Positive retained bytes |
| --- | ---: | ---: | ---: | ---: | ---: |
| Parse and compile | 9.178 s | 37 | 20,000 | 18,438 | 8,825 |
| Text control render | 1.545 s | 17 | 56,581 | 9,788 | 8,695 |
| Contextual HTML render | 14.819 s | 78 | 20,000 | 14,511 | 12,577 |
| Sprig function-heavy | 5.828 s | 33 | 20,000 | 11,816 | 7,632 |
| Scheduled async callback | 1.558 s | 787 | 20,000 | 5,750 | 2,190 |

Fast synchronous operations produce few stack samples, so sampling only
corroborates the stronger deterministic attribution. Allocation diffs identify
objects retained at snapshot time; they do not measure total transient
allocator traffic.

## Bottleneck Analysis

### Text Rendering

| Deterministic hotspot | Self-time share |
| --- | ---: |
| Sync VM instruction loop | 19.73% |
| Operand evaluation | 6.09% |
| Dynamic `isinstance` checks | 6.07% |
| Command evaluation | 5.08% |
| `sprintf` | 4.23% |
| `len` calls | 4.23% |
| Enum hashing | 3.68% |
| Single field lookup | 3.28% |
| Field-chain lookup | 3.13% |
| Pipeline evaluation | 2.90% |

The architectural cost is a chain of Python-level boundaries for each action:

```text
instruction dispatch
  -> pipeline evaluation
    -> command evaluation
      -> operand evaluation
        -> value lookup
          -> callable validation and invocation
            -> Go-compatible formatting
```

No one leaf function explains the Jinja gap. Jinja lowers templates into more
direct Python execution, while pygotpl retains a general compatibility VM.

### Contextual HTML Rendering

| Deterministic hotspot | Self-time share |
| --- | ---: |
| URL processing | 10.54% |
| Dynamic `isinstance` checks | 8.59% |
| Sync VM instruction loop | 5.94% |
| Value formatting | 5.59% |
| Command evaluation | 5.26% |
| Registered function invocation | 3.69% |
| Prepared callable invocation | 3.61% |
| Content classification | 3.54% |
| Escaping replacement | 3.19% |
| Character conversion | 2.51% |

HTML pays the shared VM cost plus Go-compatible contextual security work for
HTML text, attributes, URLs, CSS, JavaScript, `srcset`, and trusted content
types. Replacing the final string with a generic HTML escape would be faster
but incorrect and is prohibited by the compatibility contract.

### Sprig Rendering

Sprig cost is distributed across dynamic type checks, `sprintf`, operand and
command evaluation, function invocation, numeric conversion, SHA-256, regex,
semver, and dict helpers. Semver and regex also appear among retained allocation
locations. There is no common native primitive that can accelerate all Sprig
functions without changing their semantics.

### Parser and Async

Parser cost is spread across lexer state actions, token/dataclass creation,
enum hashing, parser navigation, semantic validation, and compiler IR creation.
It matters for cold rendering, but it is not the cause of warm-render gaps.

Async stack samples spend 99.87% of observed time in the event-loop selector
for the deliberately yielding workload. Together with the Jinja ratios, this
shows that async runtime work is not a current priority.

## Retained M6 Optimizations

M6 retained only changes that preserved output and passed conformance,
security, parity, and focused benchmark checks:

- callable signatures and trusted function metadata are prepared once;
- contextual HTML replacements use ordered C-level string replacements;
- immutable `printf` directives use a bounded 4,096-entry cache;
- immutable value-adapter modes are shared;
- scope, `with`, and range storage allocate lazily;
- named-template execution uses a lazy explicit caller stack rather than
  Python recursion; and
- the existing `StringIO` return buffer and caller-owned writer path remain
  after a list-backed alternative failed to improve representative workloads.

All source caches have finite bounds and concurrency coverage. Sync rendering
contains no unconditional coroutine or event-loop path.

## Rejected Backends and Native Prototype

The Python-AST feasibility study computed the generous upper bound obtained if
all synchronous dispatcher self time disappeared: 1.424x for literal, 1.247x
for text control, 1.063x for contextual HTML, and 1.644x for large named
templates. HTML is dominated by compatibility helpers that generated dispatch
alone cannot remove, so a full AST backend was not retained.

Because pygotpl failed the 1.20x Jinja deferral gate, M6 also compiled the exact
existing `sync_vm.py` implementation as a private Cython module. This avoided
duplicating formatting, lookup, escaping, error, and dispatch semantics.

| Workload | Pure Python ns/op | Cython ns/op | Median improvement | Pure RSD | Cython RSD |
| --- | ---: | ---: | ---: | ---: | ---: |
| Text control | 15,861 | 14,357 | 9.39% | 1.40% | 0.59% |
| Contextual HTML | 123,334 | 118,520 | 3.76% | 1.96% | 0.21% |

The retention gate required at least 25% median end-to-end improvement on both
workloads. Neither passed. Cython and setuptools remain benchmark-only tools;
the production package has no extension, optional native extra, binary wheel,
or conditional fallback. A hand-written C or Rust VM is also rejected for now
because current profiles do not identify a narrow cross-workload primitive
with sufficient opportunity, and moving compatibility rules into another
language would create a second semantic implementation.

## Optimization Priorities

Future performance work should proceed in this order:

1. Add more specialized compiled instructions so common field, constant,
   formatting, and callable shapes require fewer VM and helper boundaries.
2. Move safe decisions from render time to compile time, including operand
   shape, function metadata, output formatting shape, and HTML context-specific
   operations.
3. Add direct exact-`dict` and common Python object access paths while retaining
   the auditable value adapter for general mappings, descriptors, methods, and
   missing-key behavior.
4. Reduce repeated `isinstance`, enum hashing, and intermediate argument-list
   construction in command and pipeline execution.
5. Fuse compatible HTML classification, filtering, and escaping steps only
   where Go contextual behavior and error attribution remain identical.
6. Re-profile parser object construction after warm-render opportunities are
   exhausted.

Further async optimization, a native extension, a complete AST backend, or a
hand-written C/Rust VM should remain deferred until new evidence crosses the
existing objective gates.

## Regression Policy

- A statistically credible regression above 5% produces an alert.
- A regression above 10% on a representative hot path blocks a release unless
  explicitly accepted and documented.
- A performance claim requires a checked-in fixture, validated output, raw
  samples, variance, environment metadata, and a reproducible command.
- Hosted-runner history is trend evidence; stable hardware is required for a
  release-blocking decision.

The release-only performance workflow records Go comparisons, parser, async,
memory, Jinja, Mako, Chameleon, and profile artifacts for 90 days. It runs for
release-labeled pull requests, `v*` tags, or an explicit manual dispatch.

## Reproduction

Install all locked development groups and the optional crypto test capability:

```console
uv sync --frozen --all-groups --extra crypto
```

Run the consolidated evidence commands:

```console
uv run --python 3.14 --frozen python -m benchmarks.history --samples 7 --output benchmark-history.json
uv run --python 3.14 --frozen python -m benchmarks.parser_baseline --samples 7 --output parser-history.json
uv run --python 3.14 --frozen python -m benchmarks.async_runtime --samples 7 --iterations 20000 --warmup 1000 --concurrency 32 --output async-history.json
uv run --python 3.14 --frozen python -m benchmarks.memory benchmarks/fixtures/html_render.json --samples 25 --output memory-html.json
uv run --python 3.14 --frozen python -m benchmarks.jinja_compare --samples 7 --memory-samples 25 --output jinja.json
uv run --python 3.14 --frozen python -m benchmarks.python_engine_compare --samples 9 --memory-samples 25 --output python-engines.json
uv run --python 3.14 --frozen python -m benchmarks.profile_suite --iterations 20000 --sampling-seconds 1 --sampling-interval 0.001 --allocation-iterations 25 --top 20 --output profile.json
uv run --python 3.14 --frozen python -m benchmarks.native_accelerator --samples 7 --output native-prototype.json
```

Run the complete correctness and quality gate after any performance change:

```console
./scripts/check.sh
```

The M6 exit run passed 1,369 tests with 7,496 executable statements, zero
statement misses, 3,066 branches, and one partial lexer branch. Ruff, format,
strict Pyright, generated-artifact checks, `gofmt`, and the Go oracle passed.

## Supporting Evidence

- `m6-performance.md`: original Go comparison and retained optimizations.
- `m6-python-engine-comparison.md`: Jinja, Mako, and Chameleon details.
- `m6-profiling.md`: profiler-specific evidence and interpretation.
- `m6-native-accelerator-decision.md`: native retention gate.
- `m6-ast-backend-decision.md`: generated-backend feasibility.
- `m6-benchmark-inventory.md`: fixture and focused-benchmark inventory.
- `m6-acceptance-audit.md`: deliverable and exit-gate audit.
