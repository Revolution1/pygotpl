# M10 Release Performance Report

## Decision

The M10 package and API changes retain the pure Python VM and now ship an
immutable linked sidecar for synchronous execution. No native extension,
generated AST backend, or isolated single-opcode specialization is shipped.
The generic instruction stream remains the compatibility reference and the
async executor remains generic. The sync linker fuses coherent lookup and unary
call shapes only when static arity and type-validation rules prove the shortcut
safe; every other shape falls back to generic evaluation.

Seven Go-shared fixtures cross the 5% alert line relative to their M6 or M7
local baselines, but none crosses the 10% release-blocking threshold. D014
explicitly accepts these M10 alerts because output hashes agree, an independent
eleven-sample rerun brought the noisiest large named-template result to +5.37%,
and earlier isolated specialized-opcode and Cython prototypes did not meet their
retention gates. The later linked-family result below meets the two-workload
gate. Its initial cold-construction alert was attributed to the measured
one-time link cost, and the final control-sidecar rerun returned below 5%. No
unexplained regression crosses 5%. Hosted history must continue to track it.

## Linked Write IR Follow-up

On August 28, 2026, twenty-one paired, alternating samples compared the retained
sidecar with the generic sync VM on the same compiled programs and data:

| Workload | Generic median | Linked median | Change | Link time | Retained sidecar |
| --- | ---: | ---: | ---: | ---: | ---: |
| Text control | 15.624 us | 13.879 us | -11.17% | 3.333 us | 376 B |
| Contextual HTML | 126.555 us | 90.173 us | -28.75% | 15.875 us | 1,792 B |
| Sprig-heavy | 70.623 us | 68.536 us | -2.95% | 13.542 us | 1,448 B |
| Large named set | 25.853 us | 25.968 us | +0.44% | 45.375 us | 7,632 B |

Every pair produced identical output. Link peak increments were 872 B, 2,416 B,
1,944 B, and 8,016 B respectively. The large named association contains one
linked write behind 32 template calls, so the association-level cost model
executes it through the generic VM; its +0.44% result is below the 5% alert
threshold. Sync `Template` and `HTMLTemplate` string and writer APIs own the
sidecar, while async APIs continue to use the generic program.

A separate seven-sample canonical public-API run also verified every output
digest against Go. The retained entry points measured 12.953 us for text
control (11.75x Go), 89.423 us for contextual HTML (6.62x Go), 68.277 us for
Sprig-heavy rendering (7.41x Go), and 26.318 us for the generic-fallback large
named set (14.03x Go).

The phase-specific public paths make the construction tradeoff explicit. Reused
writer rendering measured 8.717 us, down 24.59% from the 11.559 us M10 result.
Cold text measured 83.517 us, up 8.10% from 77.262 us and therefore above the 5%
alert threshold but below the 10% release blocker. The same cold fixture's
isolated median link cost was 4.833 us, accounting for most of that delta. The
optimization remains eager and immutable because `Template` is principally a
reusable compiled object; introducing mutable first-versus-second-render state
solely to conceal cold link cost would weaken its concurrency model.

## Linked Control IR Follow-up

The retained second stage adds a sparse, PC-aligned sidecar for lookup-only
`ITERATE`, `JUMP_IF_FALSE`, and `ENTER_WITH` pipelines. It leaves the jump,
truth, dot-stack, range-state, binding, budget, and diagnostic machinery in the
generic VM. Logical calls and other control shapes remain generic. Programs
without a linkable control shape store `None` rather than an all-empty tuple.

Twenty-one paired, alternating samples on August 28, 2026 measured the final
write-plus-control implementation:

| Workload | Generic median | Linked median | Change | Link time | Retained sidecar |
| --- | ---: | ---: | ---: | ---: | ---: |
| Text control | 15.945 us | 12.830 us | -19.54% | 5.542 us | 536 B |
| Contextual HTML | 127.286 us | 90.779 us | -28.68% | 18.167 us | 2,128 B |
| Sprig-heavy | 73.358 us | 71.339 us | -2.75% | 14.416 us | 1,464 B |
| Small named set | 15.639 us | 13.400 us | -14.31% | 17.125 us | 2,288 B |
| Large named set | 26.401 us | 26.269 us | -0.50% | 53.083 us | 8,176 B |
| Reused writer | 10.630 us | 8.179 us | -23.06% | 4.541 us | 400 B |

The canonical public-API rerun again matched every Go output digest. Text
control measured 12.350 us (10.89x Go), contextual HTML 91.163 us (6.53x Go),
and the newly enabled small named set 13.733 us (13.50x Go). Reused writer
rendering measured 7.776 us, down 32.73% from the pre-linked M10 result. Cold
text measured 79.969 us, only 3.50% above the pre-linked M10 result and below
the alert threshold; its isolated final link cost was 5.000 us. Large named
templates remain on the generic execution path and showed no warm regression.

## Linked Constant Operand Follow-up

The retained third stage decodes nil, Boolean, number, complex, string, and
character operands into immutable sidecar values during linking. The generic IR
continues to store the original operand spelling for async execution,
diagnostics, and reference-VM parity. Dynamic dot, field, variable, function,
and subpipeline operands retain runtime evaluation.

Twenty-one paired, alternating samples on August 28, 2026 measured the combined
write, control, and constant-operand sidecar:

| Workload | Generic median | Linked median | Change | Link time | Retained sidecar |
| --- | ---: | ---: | ---: | ---: | ---: |
| Text control | 14.768 us | 11.465 us | -22.36% | 5.834 us | 576 B |
| Contextual HTML | 120.824 us | 86.483 us | -28.42% | 17.000 us | 2,128 B |
| Sprig-heavy | 67.932 us | 60.439 us | -11.03% | 19.292 us | 2,064 B |
| Large named set | 25.212 us | 25.194 us | -0.07% | 52.500 us | 8,176 B |

The Sprig fixture improved from the preceding sidecar's roughly 3% reduction to
11.03% because its static format strings, regexes, map keys, Boolean values,
and numeric literals no longer repeat generic operand-kind dispatch and numeric
decoding on every render. Its sidecar retained 600 additional bytes and linked
about 5 us more slowly than the preceding stage. The tradeoff remains scoped to
construction of a reusable synchronous template.

An independent seven-sample public-API run matched the pinned Go oracle output
digest. Sprig-heavy rendering measured 63.405 us (6.76x Go), down from the
68.277 us (7.41x Go) write-only public baseline. The complete 2,003-test suite,
Ruff, Pyright, and strict documentation build passed after the change.

## Linked Dynamic Operand Follow-up

The retained fourth stage links dot, field-chain, and variable-chain arguments
inside multi-argument function calls. A single-field argument now calls the
existing value adapter directly; longer chains retain the generic chain helper
and its intermediate-method behavior. Unsupported and malformed operand shapes
continue through generic evaluation.

Twenty-one paired, alternating generic-versus-linked samples measured:

| Workload | Generic median | Linked median | Change | Link time | Retained sidecar |
| --- | ---: | ---: | ---: | ---: | ---: |
| Text control | 14.968 us | 11.171 us | -25.36% | 5.792 us | 616 B |
| Contextual HTML | 121.609 us | 88.102 us | -27.55% | 16.833 us | 2,128 B |
| Sprig-heavy | 71.259 us | 61.038 us | -14.34% | 19.916 us | 2,312 B |
| Large named set | 24.959 us | 25.132 us | +0.69% | 51.708 us | 8,176 B |

Because absolute machine speed moved between the constant and dynamic runs, a
second twenty-one-sample test alternated the two linked stages in one process.
On Sprig-heavy rendering, constant-only linking measured 63.066 us and dynamic
operand linking measured 60.612 us, an incremental 3.89% reduction. The dynamic
sidecar retained 248 additional bytes for that fixture; large named templates
remain behind the existing generic-fallback cost model.

The independent seven-sample public-API rerun matched the pinned Go output
digest and measured 64.352 us (6.60x Go). Cross-run absolute timing was noisy,
so the paired staged comparison, rather than the public-run delta, supports the
incremental optimization claim. The complete 2,004-test suite, Ruff, and
Pyright passed after the change.

### Rejected Fixed-Arity Call Prototype

A follow-up prototype split prevalidated direct calls into a separate linked
command and invoked total arities zero through three without constructing an
argument list. Calls with more arguments retained the list path. Twenty-one
same-sidecar alternating samples isolated the dispatcher change on the
Sprig-heavy fixture: the existing list-direct path measured 59.904 us and the
fixed-arity path measured 60.588 us, a 1.14% regression. Extra Python branches
and dispatch outweighed the avoided small-list allocation, so the prototype and
its additional IR type were removed.

### Rejected Complete Format-Plan Cache

A bounded complete-format cache replaced repeated literal and `%` scanning
while retaining dynamic width, precision, indexes, diagnostics, and values at
execution time. Twenty-one same-template alternating samples measured a 1.69%
text-control reduction and a 2.51% Sprig-heavy reduction. However, a
3,000-format high-cardinality run measured 1.709 us per unique format through
the retained scanner and 2.201 us through plan construction, a 28.75% cold-path
regression. The modest warm gain did not justify changing dynamic-format
behavior or retaining another cache, so the prototype was removed and the
existing bounded directive cache remains.

## Table-Driven Contextual URL Processing

The retained HTML follow-up replaces per-byte `ord`, range, safe-set, and hex
formatting branches with immutable 256-entry escape and normalization tables
plus a byte-valued hex classifier. Valid existing percent escapes remain
untouched only in normalization mode; invalid escapes and UTF-8 bytes retain
the same lowercase percent encoding.

Seven alternating primitive samples measured the former branching processor at
984.352 ns per operation and the table processor at 476.396 ns, a 2.07x ratio
or 51.60% reduction. Twenty-one same-template alternating samples measured the
complete contextual HTML fixture at 91.590 us with branching and 86.372 us with
tables, a 5.70% end-to-end reduction.

An independent seven-sample public-API rerun matched the pinned Go output digest
and measured 88.567 us (6.21x Go). The complete 2,005-test suite, all targeted
HTML and URL conformance/security tests, Ruff, and Pyright passed.

## Performance Follow-up Closure

The August 28, 2026 performance follow-up is closed after retaining the linked
sync sidecar and table-driven contextual URL processing described above. The
fixed-arity direct-call and complete-format-plan prototypes were removed after
failing their retention tradeoffs. No further isolated instruction, formatter,
or escaper micro-optimization remains in the M10 scope.

A final seven-sample comparison on CPython 3.14.7 against Jinja 3.1.6 measured:

| Reused workload | gotpl median | Jinja median | Ratio |
| --- | ---: | ---: | ---: |
| Callback | 1.926 us | 2.750 us | 0.70x |
| HTML autoescape | 4.434 us | 2.852 us | 1.55x |
| Text control | 8.088 us | 3.856 us | 2.10x |

The HTML row compares context-appropriate output but not equivalent escaping
architectures: gotpl retains Go-style contextual HTML, JavaScript, CSS, and URL
analysis while Jinja performs its configured autoescape behavior. Callback and
async results no longer justify broad interpreter work; the remaining
control-heavy text gap requires a higher-level experiment rather than more
small hot-path branches.

That experiment is deferred to the planned
[`M12 generated synchronous backend`](../milestones/m12-generated-sync-backend.md).
M12 is not active, does not change the M10 release scope, and must meet its
30%-on-two-workloads retention gate before any generated backend is kept.

## Environment and Method

- Date: August 27-28, 2026
- Hardware: Apple M5, 10 cores, 32 GB memory
- Operating system: macOS 26.5.2, arm64
- Python: CPython 3.14.7
- Go: Go 1.27.0, darwin/arm64
- Jinja: 3.1.6
- Samples: seven for complete public timing suites, eleven for independent
  stability reruns, and twenty-one for paired linked and staged comparisons
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
uv run --frozen python -m benchmarks.linked_ir --samples 21 --iterations 3000 --warmup 500 --link-samples 51
uv run --frozen python -m benchmarks.linked_ir benchmarks/fixtures/named_render.json benchmarks/fixtures/text_writer.json --samples 21 --iterations 3000 --warmup 500 --link-samples 51
uv run --frozen python -m benchmarks.url_processor --samples 7 --iterations 100000
```

The complete methodology, stable-hardware rules, allocation caveats, and full
profiling commands remain in `docs/performance.md` and the M6 report.
