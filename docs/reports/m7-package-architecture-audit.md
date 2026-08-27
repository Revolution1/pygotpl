# M7 Package Architecture Acceptance Audit

## Outcome

M7 is complete. The repository is a coordinated uv workspace with five
independently buildable distributions: `pygotpl`, `goduration`, `gotime`, and
the intentionally narrow `gofmt` and `goregexp` boundaries. The four extracted
packages expose explicit Go and Python surfaces, while pygotpl keeps template
coercion, registries, errors, parsing, compilation, execution, and contextual
HTML policy.

No extracted package imports gotpl. The only workspace leaf-to-leaf edge is
`gotime -> goduration`; an AST-based import test and metadata graph test reject
new reverse edges and cycles. pygotpl internal owners and permitted imports are
defined in `docs/architecture.md` and enforced by the same test suite.

## Deliverable Audit

| Deliverable | Evidence | Result |
| --- | --- | --- |
| uv workspace and independent metadata | Root lock plus five PEP 621 projects | passed |
| Dual Go/Python package surfaces | Direct API, typing, and wheel consumer tests | passed |
| `goduration` extraction | 74 package tests, 100% coverage, Go oracle | passed |
| `gotime` extraction | 218 package tests, 96% coverage, Go oracle | passed |
| Narrow `gofmt` extraction | 50 package tests, 98% coverage, Go oracle | passed |
| Narrow `goregexp` extraction | 47 package tests, 96% coverage, Go oracle | passed |
| Thin pygotpl adapters | Sprig date/duration/regex and runtime format suites | passed |
| Import and ownership policy | `tests/architecture/test_import_layers.py` | passed |
| Specialized-instruction framework | Measured and rejected `WRITE_FIELD` prototype | passed |
| Packaging and performance evidence | This audit and the four extraction reports | passed |

The extracted value objects and compiled regex patterns are immutable and
typed. Top-level package exports default to Go behavior; `.python` imports are
explicit and there is no mutable process-global mode.

## Runtime, Test, and Type Matrix

The complete repository suite was run in fresh isolated environments on every
locally available supported runtime:

| Runtime | Result |
| --- | ---: |
| CPython 3.11.16 | 1,755 passed |
| CPython 3.12.14 | 1,755 passed |
| CPython 3.13.15 | 1,755 passed |
| CPython 3.14.7 | 1,755 passed |
| PyPy 3.11.15 | 1,751 passed, 4 skipped |

The four PyPy skips are memory/profiling assertions guarded by the absence of
`tracemalloc`; they are not compatibility, security, sync, async, HTML, Sprig,
or package skips. CI repeats the matrix on Linux, macOS, and Windows for all
CPython versions and on Linux for PyPy. It also invokes every package suite
from its member directory.

On CPython 3.14.7, `scripts/check.sh` passed Ruff, Ruff formatting, strict
Pyright, 1,755 tests, 99% aggregate statement-and-branch coverage, generated
Unicode verification, four package Go oracles, and the main Go template
oracle. Pyright reports 100% type completeness for all five typed packages.

## Build and Wheel Parity

`uv build --all-packages --offline` produced only `py3-none-any` wheels:

| Distribution | Wheel bytes |
| --- | ---: |
| `goduration` | 12,664 |
| `gotime` | 27,633 |
| `gofmt` | 9,181 |
| `goregexp` | 47,429 |
| `pygotpl` | 100,089 |

All five wheels were installed together with `--no-deps` into an empty
environment. `scripts/check_wheel_install.py` exercised both surfaces of every
leaf and pygotpl text and HTML rendering, while asserting imports came from
`site-packages`. A copied external consumer was then checked in strict mode
against the isolated interpreter, proving that the wheel `py.typed` markers
and annotations work without the editable source tree.

The core wheel has no extension and needs no Go executable, subprocess, shared
library, or platform wheel. Go is used only by development oracles and
benchmarks. Cryptography remains an optional extra and is lazily imported by
the relevant Sprig functions.

## Cold Import Evidence

`benchmarks.package_imports` measured each import in 15 fresh CPython 3.14.7
processes with `tracemalloc` enabled. "Editable" is the workspace environment
before packaging; "wheel" is the isolated post-build environment.

| Import | Editable median ms | Wheel median ms | Change | Editable peak bytes | Wheel peak bytes |
| --- | ---: | ---: | ---: | ---: | ---: |
| `goduration` | 22.191 | 22.086 | -0.48% | 2,363,216 | 2,363,616 |
| `gotime` | 51.182 | 50.454 | -1.42% | 4,917,352 | 4,916,226 |
| `gofmt` | 23.167 | 23.098 | -0.30% | 2,333,737 | 2,334,450 |
| `goregexp` | 28.713 | 28.963 | +0.87% | 2,933,807 | 2,932,401 |
| `pygotpl` | 112.780 | 113.681 | +0.80% | 5,121,361 | 5,123,049 |

No editable/wheel import difference reaches 1.5%. These numbers establish the
first reproducible package-import baseline; M6 did not record cold imports, so
the report does not invent a pre-extraction historical comparison.

## End-to-End Latency and Allocation

Final M7 medians use the unchanged M6 fixtures and CPython 3.14.7. Every output
digest matches Go and the M6 reference.

| Workload | M6 Python ns/render | M7 Python ns/render | Change | Go allocations | Go bytes |
| --- | ---: | ---: | ---: | ---: | ---: |
| Text control | 15,569 | 15,811 | +1.55% | 35 | 808 |
| Contextual HTML | 121,746 | 121,465 | -0.23% | 335 | 7,162 |
| Sprig function-heavy | 65,692 | 68,071 | +3.62% | 160 | 8,363 |
| Large named templates | 25,637 | 25,867 | +0.90% | 68 | 4,258 |

All differences remain below the 5% alert threshold. Go allocation counts and
bytes are unchanged from M6. Package-specific microbenchmarks and limitations
are recorded in the four extraction reports.

## Python Memory Evidence

Twenty-five single-render `tracemalloc` samples use the same prepared public
operations as M6:

| Workload | M6 peak | M7 peak | Change | M6 retained | M7 retained | M6/M7 blocks |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Text control | 3,933 | 4,045 | +2.85% | 2,447 | 2,559 | 38 / 40 |
| Contextual HTML | 8,911 | 8,911 | unchanged | 7,561 | 7,561 | 72 / 72 |
| Large named templates | 8,317 | 8,317 | unchanged | 3,509 | 3,509 | 51 / 51 |

The text retained-byte difference is +4.58%, below the alert threshold. Python
traced allocations are not presented as equivalent to Go's total allocator
counters.

## Specialized Instruction Decision

The measured `WRITE_FIELD` prototype retained output parity but changed text
control by +0.07% and large named templates by -1.53%. Because it did not
credibly improve two representative workloads, it was removed from the
production compiler and both VMs. The proposed operand, lookup/control,
prepared-callable, formatting, and HTML escape-plan families and their future
retention gates are documented in
`m7-specialized-instruction-prototype.md`.

## Ecosystem Readiness

Sprout and Helm work can remain outside the default registries as opt-in
pygotpl modules:

- standalone Go-compatible values come from the explicit leaf `.go` APIs;
- Python-native opt-ins come from leaf `.python` APIs;
- functions are supplied through public immutable `Template` and
  `HTMLTemplate` registries;
- Helm globals are ordinary render data rather than VM state; and
- contextual output uses the public HTML template boundary.

They do not need to import parser nodes, compiler instructions, runtime
sentinels, VM functions, or private leaf internals. M8 may add those opt-in
modules with an explicit owned-module import graph without creating more
workspace distributions.

## Reproduction

```console
./scripts/check.sh
uv build --all-packages --frozen
python -m benchmarks.package_imports --python .venv/bin/python --samples 15
python -m benchmarks.compare benchmarks/fixtures/text_render.json --samples 11
python -m benchmarks.compare benchmarks/fixtures/html_render.json --samples 11
python -m benchmarks.compare benchmarks/fixtures/sprig_render.json --samples 11
python -m benchmarks.compare benchmarks/fixtures/named_large_render.json --samples 11
python -m benchmarks.memory benchmarks/fixtures/text_render.json --samples 25
python -m benchmarks.memory benchmarks/fixtures/html_render.json --samples 25
python -m benchmarks.memory benchmarks/fixtures/named_large_render.json --samples 25
```

The wheel consumer and runtime-matrix commands are automated in
`.github/workflows/ci.yml`.
