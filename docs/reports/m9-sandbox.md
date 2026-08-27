# M9 Sandbox and Python Extension Report

## Scope

M9 adds opt-in execution policy without changing the default Go-compatible
runtime. The implementation covers text and contextual HTML templates, both
VMs, associated templates, dynamic sources, and the reusable cross-file
`TemplateEngine`.

## Public Surface

- `SandboxPolicy.strict()` is immutable and mapping-only by default.
- Attributes, descriptor-backed properties, bound methods, custom lookup, and
  registered functions require separate explicit grants.
- The strict runtime removes the data-callable `call` built-in.
- `ExecutionBudget` limits output characters, range items, active associated
  template calls, and registered-function or method calls.
- Strict construction supplies conservative defaults unless `budget=` is
  explicit. Every render receives fresh counters.
- `PythonExtensions(re_match=True)` adds only Python `reMatch`; no compatibility
  or ecosystem registry receives the name.

## Security Evidence

`tests/security/test_sandbox_policy.py` covers mappings, attributes,
properties, methods, custom lookup, data callables, registered-function
allowlists, full Sprig/Slim-Sprig/Sprout/Helm maps, mutation, cryptography,
eager CIDR expansion, writer mutation ordering, every budget dimension, source
length, HTML escaping, immutability, and fresh render state.

`tests/async/test_sandbox_budget.py` proves async output, range, callback, and
associated-template depth accounting. `tests/unit/test_python_extensions.py`
proves explicit selection, Python search/lookbehind behavior, actionable regex
errors, the bounded 256-entry cache, immutable configuration, collision
rejection, strict-policy admission, and registry isolation.

The implementation does not claim process isolation. CPU-bound callbacks,
blocking native code, large allocations inside one admitted function, and
Python regex backtracking require a resource-limited worker. This boundary and
deployment guidance are in `docs/sandbox.md` and decision D011.

## Performance Evidence

The sandbox benchmark renders 20 mapping records through one range using a
reused template. On Apple M5 arm64, macOS 26.5.2, and CPython 3.14.7, seven
samples of 2,000 warm renders produced:

| Mode | Median | Relative to default |
| --- | ---: | ---: |
| Default Go-compatible runtime | 31.646 us | 1.00x |
| Explicit execution budget | 35.604 us | 1.13x |
| Strict mapping-only sandbox and default budget | 41.790 us | 1.32x |

The default path does not create budget counters or wrap the writer. The
measured overhead is confined to the explicitly selected policy. Reproduce
with:

```console
uv run python -m benchmarks.sandbox --iterations 2000 --samples 7
```

Results are machine-local evidence rather than a cross-machine regression
threshold. `tests/performance/test_sandbox_benchmark.py` keeps the benchmark's
correctness and result schema in the normal suite.

## Python-Native Helper Decision

M9 adds no Python-native numeric helpers. Python formatting remains the
existing explicit `format_mode="python"` surface; adding overlapping numeric
functions without a demonstrated use case would expand collision and semantic
policy unnecessarily. Future helpers must remain immutable opt-ins, avoid all
Go and ecosystem names, and receive direct sync, async, security, and cache
identity tests.

## Verification

The local M9 gate on CPython 3.14.7 completed with:

- 1,900 tests passing after the M10 package-layout migration;
- Ruff formatting and lint clean;
- strict Pyright with zero errors;
- branch-aware aggregate coverage at 96%;
- all generated-artifact checks and pinned Go, Sprig, Sprout, and Helm oracles
  passing;
- all three workspace wheels built offline and installed together in an empty
  environment with only mandatory timezone dependencies; and
- the installed wheel exercising the strict policy, execution budget, Python
  extension, and `gotpl.runtime.engine.TemplateEngine` path without optional
  extras.

The configured multi-interpreter and multi-platform CI matrix remains the
hosted evidence gate. It is not represented as a local macOS result.
