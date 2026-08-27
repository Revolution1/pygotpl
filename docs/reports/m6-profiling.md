# M6 Comprehensive Profiling

## Outcome

Independent deterministic, stack-sampling, and allocation profiles show that
the remaining warm-render cost is distributed across Python VM dispatch and
compatibility helpers. There is no single self-contained native helper that
explains the Jinja gap across both representative text and HTML workloads.

## Method

The profile suite ran on CPython 3.14.7, macOS 26.5.2 arm64. Each workload used
20,000 deterministic operations, at least one second of 1 ms stack sampling,
and 25 allocation-diff operations. Profiling is deliberately separate from the
headline timing runners.

| Workload | Deterministic total | Stack samples | Completed sampled ops | Peak traced bytes | Positive retained bytes |
| --- | ---: | ---: | ---: | ---: | ---: |
| Parse and compile | 9.178 s | 37 | 20,000 | 18,438 | 8,825 |
| Text control render | 1.545 s | 17 | 56,581 | 9,788 | 8,695 |
| Contextual HTML render | 14.819 s | 78 | 20,000 | 14,511 | 12,577 |
| Sprig function-heavy | 5.828 s | 33 | 20,000 | 11,816 | 7,632 |
| Scheduled async callback | 1.558 s | 787 | 20,000 | 5,750 | 2,190 |

The sampler is corroborating evidence, not a precise estimator for fast sync
operations: their small sample counts make `cProfile` the stronger attribution
source. Async samples mostly observe the event loop waiting in `kqueue`, as
expected for an intentionally yielding coroutine.

## Hotspots

- Parse/compile is spread across lexer action construction, tokenization,
  parser advancement, enum hashing, and compiler object creation. The largest
  single self-time share was lexer `build` at 8.56%.
- Text control render spends 19.73% of self time in the VM instruction loop,
  then roughly 3–6% each in operand evaluation, command evaluation, type tests,
  `sprintf`, field-chain lookup, and pipeline evaluation.
- Contextual HTML spends 10.54% in URL processing, 8.59% in type tests, 5.94%
  in VM dispatch, 5.59% in value formatting, and smaller shares in callable
  invocation, content classification, replacement, and character scanning.
- Sprig-heavy work is similarly distributed across formatting, VM evaluation,
  function invocation, numeric conversion, hashing, regex, semver, and dict
  helpers.
- Scheduled async rendering is dominated by the operating event-loop wait;
  pygotpl's async VM is already within the Jinja comparison gate.

The largest positive retained lines in text and HTML were callable-result
paths, but `tracemalloc` diffs describe objects still reachable at the snapshot,
not total allocation traffic. They do not justify replacing callable semantics
with a native implementation.

## Candidate Decision

Compiling the existing sync VM was selected as the least risky prototype. It
touches both text and HTML, preserves the exact Python implementation instead
of cloning Go compatibility behavior, and gives a realistic upper signal for
unannotated Cython compilation. Isolated HTML escapers were rejected as the
prototype target because they cannot satisfy the two-workload retention gate;
formatting and value adaptation were rejected because reimplementing them would
duplicate compatibility semantics.

## Reproduction

```console
uv run --python 3.14 --frozen python -m benchmarks.profile_suite --iterations 20000 --sampling-seconds 1 --sampling-interval 0.001 --allocation-iterations 25 --top 20 --output profile.json
```
