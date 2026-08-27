# M10 Release Performance Report

## Decision

The M10 package and API changes retain the pure Python VM. No native extension,
generated AST backend, or isolated single-opcode specialization is shipped.
Current callback and async workloads remain at Jinja latency, while text and
contextual HTML remain materially slower than Jinja and substantially slower
than Go. Those gaps stay visible as post-1.0 optimization work; they are not
hidden by weakening compatibility or escaping behavior.

Seven Go-shared fixtures cross the 5% alert line relative to their M6 or M7
local baselines, but none crosses the 10% release-blocking threshold. D014
explicitly accepts these M10 alerts because output hashes agree, an independent
eleven-sample rerun brought the noisiest large named-template result to +5.37%,
and earlier specialized-opcode and Cython prototypes did not meet their
retention gates. Hosted history must continue to track them.

## Environment and Method

- Date: August 27, 2026
- Hardware: Apple M5, 10 cores, 32 GB memory
- Operating system: macOS 26.5.2, arm64
- Python: CPython 3.14.7
- Go: Go 1.27.0, darwin/arm64
- Jinja: 3.1.6
- Samples: seven for every complete timing suite; eleven for independent
  callback, text, Sprig, and large named-template stability reruns
- Memory: 25 samples for each shared and cross-engine memory workload

Every runner validates output or its digest before timing. Cold and warm phases
retain the definitions in `docs/performance.md`. Raw JSON remains an uncommitted
build artifact; commands and medians are recorded here.

## Go-Shared Rendering

| Workload | gotpl median | Go median | gotpl / Go | M6 gotpl median | gotpl change |
| --- | ---: | ---: | ---: | ---: | ---: |
| Literal | 1.094 us | 0.029 us | 37.69x | 1.036 us | +5.59% |
| Text control | 16.641 us | 1.124 us | 14.97x | 15.569 us | +6.88% |
| Contextual HTML | 125.419 us | 13.479 us | 9.30x | 121.746 us | +3.02% |
| Sprig-heavy | 69.419 us | 9.155 us | 7.62x | 65.692 us | +5.67% |
| Duration-heavy | 37.721 us | 3.305 us | 11.41x | 36.796 us (M7) | +2.51% |
| Cold text | 77.262 us | 2.675 us | 29.49x | 71.210 us | +8.50% |
| Reused writer | 11.559 us | 0.697 us | 16.70x | 10.953 us | +5.53% |
| Small named set | 16.572 us | 1.008 us | 16.23x | 15.678 us | +5.70% |
| Large named set | 27.888 us | 1.863 us | 14.92x | 25.637 us | +8.78% |

All fixture output digests match Go. The large named set had a 5.41% RSD in
the complete run. Its independent eleven-sample rerun measured 27.014 us, or
+5.37% from M6, confirming that the earlier 29.299 us observation was noise
rather than a reproducible release blocker. These alerts span accumulated
M7-M10 behavior on a repository without a historical commit boundary, so they
cannot be attributed to one change.

## Parser and Compiler

| Phase | Median | RSD | M6 median | Change |
| --- | ---: | ---: | ---: | ---: |
| Python parse | 71.662 us | 8.20% | 70.814 us | +1.20% |
| Python compile | 12.582 us | 2.44% | 12.484 us | +0.78% |
| Python parse and compile | 85.795 us | 2.54% | 86.161 us | -0.42% |
| Go parse | 3.301 us | 1.49% | 3.189 us | +3.51% |

The parser/compiler path has no alert-level Python regression. The isolated
parse series contains one high sample, which is disclosed by its RSD and does
not change the combined result.

## Python Ecosystem Comparison

| Workload | gotpl median | Jinja median | gotpl / Jinja | M6 gotpl median | gotpl change |
| --- | ---: | ---: | ---: | ---: | ---: |
| Warm callback, 11-sample rerun | 2.659 us | 2.757 us | 0.96x | 2.547 us | +4.40% |
| Warm HTML autoescape | 6.614 us | 2.850 us | 2.34x | 6.483 us | +2.02% |
| Warm text control, 11-sample rerun | 12.881 us | 3.811 us | 3.38x | 12.661 us | +1.74% |
| Cold callback | 21.390 us | 112.920 us | 0.19x | 20.666 us | +3.50% |
| Cold HTML | 279.360 us | 122.622 us | 2.28x | 270.776 us | +3.17% |
| Cold text | 73.510 us | 240.050 us | 0.31x | 72.426 us | +1.50% |

D013's unified immutable HTML association construction remains below the 5%
alert threshold on the cold HTML workload. It therefore needs no special-case
single-source constructor.

The complete supplementary rerun measured gotpl at 2.393 us for warm text
interpolation, versus 2.149 us for Mako and 1.633 us for Chameleon. On the
capability-matched HTML escape fixture, gotpl measured 3.884 us, versus 2.376 us
and 1.855 us respectively. These comparisons remain ecosystem context rather
than Go compatibility evidence: each engine uses a different syntax, compiler,
and escaping model.

## Async Comparison

| Path | gotpl median | Jinja median | gotpl / Jinja |
| --- | ---: | ---: | ---: |
| Sync callback on sync runtime | 2.663 us | 2.806 us | 0.95x |
| Sync callback on async runtime | 3.018 us | 3.229 us | 0.93x |
| Immediate coroutine | 3.116 us | 3.338 us | 0.94x |
| Yielding coroutine | 17.340 us | 17.382 us | 1.01x |
| Yielding coroutine, concurrency 32 | 6.812 us | 7.024 us | 0.95x |

Async execution is in the Jinja comparison band. Further async optimization is
deferred unless supported workloads regress or profiling moves away from event
loop waiting.

## Policy, Package, and Ecosystem Baselines

The post-layout sandbox rerun measured 31.812 us for the default path, 36.464 us
with an explicit budget, and 44.801 us with the strict preset. Policy cost is
paid only when selected. The default path differed by 0.52% from the immediately
preceding layout baseline.

The main wheel imports in a fresh CPython process in a 128.473 ms median with a
5.27 MiB median traced peak on this machine. Installation now resolves three
workspace wheels instead of five. The M8 Helm results remain 15.792 us for a
reused two-source core batch, 0.415 ms for a static cold chart render, and
0.441 ms for a dynamic-`tpl` cold render.

## Memory and Profile Verification

| Shared workload | Peak traced bytes | Retained bytes | Retained blocks |
| --- | ---: | ---: | ---: |
| Text control | 4,061 | 2,559 | 40 |
| Contextual HTML | 8,959 | 7,561 | 72 |
| Large named set | 8,845 | 3,509 | 51 |

These are Python `tracemalloc` single-render measurements, not Go allocator
counters. The smaller cross-engine fixtures continue to show lower traced peak
and retained memory for gotpl than Jinja, Mako, and Chameleon.

The complete 20,000-iteration deterministic profiles, one-second stack samples,
and 25-operation allocation diffs also completed. Text self time remains spread
across VM dispatch, lookup, operand evaluation, type checks, callable handling,
and formatting. The observed profile has no newly dominant function that would
justify an isolated release-time specialization.

## Bottlenecks

The M6 profiles remain representative:

- text work is distributed across VM dispatch, pipeline/command/operand
  evaluation, lookup, dynamic type checks, callable validation, and Go
  formatting;
- HTML adds URL processing, trusted-content classification, context-specific
  escaping, and more callable boundaries;
- Sprig adds conversion, regex, semver, hashing, and collection helpers; and
- cold Helm work is dominated by namespace construction, function preparation,
  and parsing rather than `tpl` itself.

No narrow primitive accounts for enough end-to-end time. A Cython compilation
of the real VM improved text by 9.39% and HTML by 3.76%, below the required 25%
on both. A `WRITE_FIELD` prototype changed text by +0.07% and large named
templates by -1.53%. The next credible experiment must fuse operand,
lookup/control, prepared-call, and formatting shapes as a family without adding
dispatch cost to generic instructions.

## Reproduction

```console
uv run --frozen python -m benchmarks.compare benchmarks/fixtures/text_render.json --samples 7
uv run --frozen python -m benchmarks.compare benchmarks/fixtures/html_render.json --samples 7
uv run --frozen python -m benchmarks.compare benchmarks/fixtures/sprig_render.json --samples 7
uv run --frozen python -m benchmarks.history --samples 7
uv run --frozen python -m benchmarks.parser_baseline --samples 7
uv run --frozen python -m benchmarks.async_runtime --samples 7 --iterations 20000 --warmup 1000 --concurrency 32
uv run --frozen python -m benchmarks.memory benchmarks/fixtures/text_render.json --samples 25
uv run --frozen python -m benchmarks.memory benchmarks/fixtures/html_render.json --samples 25
uv run --frozen python -m benchmarks.memory benchmarks/fixtures/named_large_render.json --samples 25
uv run --frozen python -m benchmarks.jinja_compare --samples 7 --memory-samples 25
uv run --frozen python -m benchmarks.python_engine_compare --samples 7 --memory-samples 25
uv run --frozen python -m benchmarks.profile_suite --iterations 20000 --sampling-seconds 1 --sampling-interval 0.001 --allocation-iterations 25 --top 20
uv run --frozen python -m benchmarks.sandbox --iterations 2000 --samples 7
```

The complete methodology, stable-hardware rules, allocation caveats, and full
profiling commands remain in `docs/performance.md` and the M6 report.
