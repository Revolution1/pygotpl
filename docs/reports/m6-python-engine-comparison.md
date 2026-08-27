# M6 Python Engine Comparison

## Outcome

The versioned comparison covers Jinja 3.1.6 as the primary Python baseline and
Mako 1.4.1 plus Chameleon 4.6.0 as supplementary capability-matched baselines.
pygotpl is near or ahead of Jinja for callbacks and every measured async path,
but it is not near Jinja on the two non-trivial warm text and HTML workloads.
The adopted 1.20x deferral gate therefore does not pass.

## Environment and Method

- Date: August 26, 2026.
- Python: CPython 3.14.7.
- Platform: macOS 26.5.2, arm64.
- Samples: seven for Jinja and nine for the supplementary rerun.
- Memory: 25 single-render `tracemalloc` samples.
- Every fixture validates expected output before timing and retains raw sample,
  median, range, and population-RSD fields in the machine-readable result.

Jinja used optimization, `auto_reload=False`, and a 400-entry template cache.
HTML compares pygotpl contextual escaping with Jinja autoescape; it does not
claim that the escaping models are identical.

## Jinja Results

| Workload | pygotpl ns/op | Jinja ns/op | pygotpl / Jinja | pygotpl RSD | Jinja RSD |
| --- | ---: | ---: | ---: | ---: | ---: |
| Warm callback | 2,547 | 2,795 | 0.90x | 0.79% | 3.63% |
| Warm HTML autoescape | 6,483 | 2,852 | 2.27x | 7.39% | 8.63% |
| Warm text control | 12,661 | 3,848 | 3.28x | 0.57% | 0.78% |
| Cold callback | 20,666 | 112,507 | 0.18x | — | — |
| Cold HTML autoescape | 270,776 | 121,095 | 2.23x | — | — |
| Cold text control | 72,426 | 239,817 | 0.30x | — | — |

The HTML timing has elevated variance, but even the observed ranges cannot
bring the warm result within the 1.20x gate. The stable text-control result is
also well outside that gate.

The async ratios range from 0.90x to 0.99x: sync callable 0.91x, callable on
the async VM 0.90x, immediate coroutine 0.90x, yielding coroutine 0.99x, and
32-way concurrent yielding render 0.96x. These results support deferring more
async-specific optimization; they do not offset the failed text and HTML gate.

Jinja cache-enabled lookup rendered in 3,052 ns/op versus 119,750 ns/op with
the cache disabled. Cache size and auto-reload are therefore explicit fixture
metadata rather than hidden defaults.

Median pygotpl traced peaks were 1,928, 2,241, and 2,902 bytes for callback,
HTML, and text respectively. Jinja medians were 3,880, 4,039, and 4,283 bytes.
These are Python tracer metrics, not total allocator traffic.

## Mako and Chameleon Results

| Workload | pygotpl ns/op | Mako ns/op | Chameleon ns/op | pygotpl / Mako | pygotpl / Chameleon |
| --- | ---: | ---: | ---: | ---: | ---: |
| Warm HTML escape | 3,727 | 2,377 | 1,870 | 1.57x | 1.99x |
| Warm text interpolation | 2,251 | 2,148 | 1,625 | 1.05x | 1.39x |
| Cold HTML | 215,566 | 121,733 | 1,975,312 | 1.77x | 0.11x |
| Cold text | 18,928 | 120,602 | 2,318,982 | 0.16x | 0.01x |

Mako HTML used MarkupSafe's `h` default filter. Chameleon used `PageTemplate`
context-appropriate escaping with auto-reload disabled. Neither supplementary
engine exposes a directly comparable async render API, so async is reported as
unsupported rather than simulated.

The second supplementary run reduced pygotpl text RSD to 5.08%, but Mako HTML
had a 29.47% RSD outlier. These medians remain exploratory ecosystem context;
release claims require a stable-hardware rerun. Median traced peaks were 1,972
versus 4,577 and 5,102 bytes for HTML, and 1,696 versus 4,430 and 3,942 bytes
for text, in pygotpl/Mako/Chameleon order.

## Reproduction

```console
uv run --python 3.14 --frozen python -m benchmarks.jinja_compare --samples 7 --memory-samples 25 --output jinja.json
uv run --python 3.14 --frozen python -m benchmarks.python_engine_compare --samples 9 --memory-samples 25 --output python-engines.json
```

The checked-in schemas and fixtures live under `benchmarks/jinja` and
`benchmarks/python_engines`. Jinja, Mako, and Chameleon are benchmark-only
dependencies and never become pygotpl runtime requirements.
