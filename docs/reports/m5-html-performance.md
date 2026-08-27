# M5 Contextual HTML Performance Baseline

## Scope

This report records the first reproducible warm-render comparison between
pygotpl's `HTMLTemplate` and Go's native `html/template`. It is a compatibility
baseline, not an optimization claim. M6 owns profiling and performance
hardening.

The shared `html/contextual-render` fixture renders three records through HTML
text, quoted attributes, CSS values, URL paths and queries, JavaScript event
attributes, structured JavaScript values, and `srcset`. Parse, contextual
analysis, process startup, and fixture decoding are excluded from warm-render
timings.

Before recording timings, both runners render once and compare a SHA-256 digest
of their output. The comparison aborts if the digests differ. The measured
output digest was
`463df65d73abff94c07d45b409d32becdcb9aa2804278007d52c9c98b1689387`.

## Reproduction

Run from the repository root with the pinned environments installed:

```console
python -m benchmarks.compare benchmarks/fixtures/html_render.json --samples 7
```

The command preserves every raw sample and reports the median, range, and
population relative standard deviation. Each Python sample performs 500 warmup
renders followed by 5,000 measured renders. Go uses the same warmup count and
`testing.Benchmark` chooses the measured iteration count adaptively.

## Environment

- Date: August 26, 2026.
- Hardware: Apple M5, 10 cores, 32 GB memory.
- Operating system: macOS 26.5.2, arm64.
- Python: CPython 3.13.7.
- Go: Go 1.26.5, darwin/arm64.

## Results

| Runtime or ratio | Median | Minimum | Maximum | Relative standard deviation |
| --- | ---: | ---: | ---: | ---: |
| Python | 149,061 ns/op | 148,235 ns/op | 150,236 ns/op | 0.42% |
| Go | 14,248 ns/op | 14,105 ns/op | 14,948 ns/op | 1.89% |
| Python / Go | 10.45x | 9.97x | 10.63x | 1.98% |

The seven paired Python-to-Go ratios were 9.9744, 10.4619, 10.4472, 10.6153,
10.6347, 10.4411, and 10.3108. On this fixture and machine, pygotpl therefore
requires approximately 10.45 times Go's warm-render latency at the median.
That number is a baseline for M6 work, not a general claim about other
templates, Python versions, or hardware.

Go reports allocations and allocated bytes through `testing.Benchmark` in each
single-run result. Python results currently leave those fields null because a
directly comparable per-operation allocation measurement has not been added.
M6 must add Python memory measurements before making cross-runtime allocation
claims.

## Interpretation

The fixture deliberately exercises contextual escaping rather than literal
copy throughput. The current Python engine performs contextual rewriting once
at construction and executes the rewritten VM for each render. Future
optimization work should profile value lookup, function dispatch, escaper
composition, and output buffering on this fixture while preserving its output
digest and the complete conformance and security suites.
