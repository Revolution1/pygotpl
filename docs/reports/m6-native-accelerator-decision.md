# M6 Native Accelerator Decision

## Decision

Do not retain a native accelerator and do not add optional native packaging.
The complete pure Python implementation remains the only production runtime on
CPython and PyPy.

The near-Jinja deferral gate did not pass, so M6 built the required Cython
prototype. The prototype then failed the independent retention gate by a wide
margin: it did not improve two representative non-trivial workloads by 25%.

## Prototype

The benchmark compiles the existing `src/gotpl/runtime/sync_vm.py` source as
a private Cython module. It neither adds typed semantic shortcuts nor copies
formatting, lookup, escaping, error, or dispatch rules into a second source.
Both runtimes render and validate identical output before timing.

Environment: CPython 3.14.7, Cython 3.3.0, macOS 26.5.2 arm64. Each result is
the median of seven independently ordered samples.

| Workload | Pure Python ns/op | Cython ns/op | Median improvement | Pure RSD | Cython RSD |
| --- | ---: | ---: | ---: | ---: | ---: |
| Text control render | 15,861 | 14,357 | 9.39% | 1.40% | 0.59% |
| Contextual HTML render | 123,334 | 118,520 | 3.76% | 1.96% | 0.21% |

The retention requirement was at least 25% median end-to-end improvement on
both workloads. Neither workload passed. Shipping an extension would therefore
add compiler, wheel, ABI, platform, release, and fallback complexity for a
single-digit gain.

## C, Rust, and Packaging

A hand-written C or Rust VM could exceed unannotated Cython, but only by moving
dynamic dispatch and compatibility rules across the language boundary. Current
profiles do not identify a narrow primitive with enough end-to-end opportunity
on two workloads. That approach is not justified now.

Because no accelerator is retained:

- there is no runtime extra, extension import, platform wheel, or fallback
  branch to maintain;
- Cython and setuptools remain benchmark-group dependencies only;
- source and binary distributions remain pure Python; and
- CPython and PyPy continue to exercise the same implementation.

Reopen this decision only after a new profile identifies a self-contained path
whose Amdahl bound can clear the same two-workload 25% gate, or after a broader
backend design can share rather than duplicate compatibility semantics.

## Reproduction

```console
uv run --python 3.14 --frozen python -m benchmarks.native_accelerator --samples 7 --output native-prototype.json
```
