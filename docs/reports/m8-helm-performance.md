# M8 Cross-file Runtime and Helm Performance

## Result

The core multi-source runtime has a clear reusable warm path. On the measured
fixture, `TemplateEngine` renders two associated sources in 15.8 microseconds
after compilation. The miniature Helm example intentionally exposes a cold
chart-render operation: its static case takes 0.415 milliseconds and its
dynamic `tpl` case takes 0.441 milliseconds.

The Python implementation remains substantially slower than Go, as expected
for a pure Python compatibility engine, but dynamic `tpl` is not the dominant
M8 problem. It adds 6.3% over the Python static chart case. The larger cost is
rebuilding the chart template namespace and validating its 222-function map on
every example render.

No further Helm-example optimization is required for M8. D009 in
`docs/implementation-decisions.md` keeps prepared-chart caching out of the
example until a real embedding application establishes an API and latency
budget. Applications can already retain the immutable core `TemplateEngine`.

## Workload

Both implementations consume `benchmarks/helm/fixtures/runtime-v1.json`, a
versioned `helm-v4.2.3` fixture containing:

- three associated template files and one named helper;
- independent per-source contexts for the core runtime;
- `include`, `range`, `.Files.Get`, and Helm globals;
- a static expansion and an equivalent dynamic `tpl` expansion; and
- output equality checks before timing.

The Go benchmark invokes the pinned Helm v4.2.3 `pkg/engine` through
`tools/helm_oracle`. It does not substitute a reduced local function map.

## Environment and Method

- Machine: Apple M5, arm64
- Operating system: macOS 26.5.2
- Python: CPython 3.14.7
- Go: 1.27.0
- Python timing: seven samples of 500 operations, median reported
- Go timing: seven samples, 500 ms per benchmark sample, median reported
- Python memory: 25 `tracemalloc` peak-increment samples
- Go memory: `go test -benchmem` total bytes and allocations per operation
- Profile: 500 Python dynamic-`tpl` renders with the top 20 cumulative entries

Process startup, fixture decoding, correctness validation, and report encoding
are outside timed operations. Cold operations include chart collection,
function-map construction, parse, compile, and render. Warm core execution
reuses one immutable compiled engine.

## Latency

| Operation | Python median | Go median | Python / Go |
| --- | ---: | ---: | ---: |
| Core compile, three sources | 95.961 us | 5.545 us | 17.31x |
| Core warm batch, two outputs | 15.792 us | 1.497 us | 10.55x |
| Helm static cold render | 415.116 us | 47.812 us | 8.68x |
| Helm dynamic `tpl` cold render | 441.326 us | 76.497 us | 5.77x |

The ratios compare equivalent output and lifecycle boundaries, not identical
internal implementations. Go's Helm engine performs its own chart model,
function-map, parse, and execution work; the Python result measures the example
runtime built on gotpl.

Dynamic `tpl` costs 1.063x the Python static case and 1.600x the Go static
case. The smaller Python relative increment does not mean its dynamic parser is
faster: Python already pays a much larger fixed compilation and registry setup
cost in both cold cases.

## Memory and Allocations

| Operation | Python median peak increment | Go bytes/op | Go allocs/op |
| --- | ---: | ---: | ---: |
| Core compile | 8,651 B | 10,408 B | 125 |
| Core warm batch | 1,825 B | 1,473 B | 35 |
| Helm static cold | 71,999 B | 72,140 B | 344 |
| Helm dynamic `tpl` cold | 72,335 B | 116,537 B | 424 |

These columns are not direct allocator equivalents. `tracemalloc` reports the
peak traced Python increment for one operation and may omit allocations made by
native dependencies. Go reports total allocation traffic per operation. The
numbers are useful within each runtime and must not be used as a cross-runtime
memory ratio.

## Hotspots

The cumulative Python profile for the dynamic case attributes:

- 79.5% of total time to `_build_template` and `TemplateEngine.from_sources`;
- 51.9% to the first `Template` construction;
- 42.2% to function-registry validation and preparation;
- 35.5% to parsing four sources, including the dynamic source; and
- 18.9% to rendering the selected source programs.

Cumulative percentages overlap because callers include their callees. The
profile nevertheless identifies the dominant boundary: cold namespace and
function preparation, not writer output or the batch mapping wrapper.

The most promising future optimization would be a correctly scoped prepared
application runtime or reusable prepared function registry. It is not a safe
local micro-optimization: cache keys and invalidation must include functions,
options, source definitions, async behavior, and security budgets.

## Reproduction

```console
python -m benchmarks.helm_runtime \
  --samples 7 --iterations 500 --memory-samples 25 \
  --profile-iterations 500 --top 20 \
  --output /tmp/pygotpl-m8-helm-python.json

GOCACHE="$PWD/.cache/go-build" \
GOMODCACHE="$PWD/.cache/go-mod" \
go -C tools/helm_oracle test -run '^$' \
  -bench 'Benchmark(GoTextTemplate|Helm)' \
  -benchmem -benchtime=500ms -count=7
```

Raw generated results remain build artifacts and are not committed. The
versioned fixture, runners, measured medians, environment, interpretation, and
decision are checked in.
