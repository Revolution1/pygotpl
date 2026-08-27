# M6 Performance Hardening Acceptance Audit

## Scope

This audit maps every M6 deliverable and acceptance gate to current repository
evidence. Local slice benchmarks guide implementation decisions; only sampled
public-API workloads with environment and variance metadata support headline
claims.

This report freezes the original Go-comparison and VM-hardening scope completed
on August 26, 2026. M6 was subsequently reopened for the Jinja comparison,
comprehensive profiling, and optional native-accelerator feasibility. That
follow-up scope is now complete and is audited below without rewriting the
historical measurements in the original sections.

The canonical reader-facing synthesis is
`m6-complete-performance-report.md`; this audit remains the gate-by-gate
evidence map.

## Reopened-Scope Audit

| Deliverable or gate | Status | Evidence |
| --- | --- | --- |
| Versioned Jinja comparison | passed | `m6-python-engine-comparison.md` covers cold and warm text and HTML, callbacks, five sync/async shapes, cache enabled/disabled, memory, output validation, samples, variance, and environment metadata using Jinja 3.1.6. |
| Supplementary Mako and Chameleon comparison | passed | The same report covers version-pinned text and HTML work and explicitly discloses escaping, compile, cache, and unsupported async differences. |
| Comprehensive profiles | passed | `m6-profiling.md` separates deterministic, stack-sampled, and allocation evidence for parser, text, HTML, Sprig, and async workloads from headline timing. |
| Near-Jinja decision | passed | Warm text and HTML measured 3.28x and 2.27x Jinja, so the 1.20x native-deferral gate did not pass and a prototype was required. |
| Native retention decision | passed | `m6-native-accelerator-decision.md` records a same-source Cython prototype at 9.39% text and 3.76% HTML improvement. It failed the two-workload 25% gate and was rejected. |
| Pure Python distribution | passed | No extension, runtime extra, binary wheel, conditional import, or compatibility fallback was added. Cython and setuptools are benchmark-only dependencies. CPython and PyPy retain one production implementation. |

## Deliverables

| Deliverable | Status | Evidence |
| --- | --- | --- |
| Representative stable benchmark suite | covered | Nine versioned fixtures cover parser, literal, warm text, contextual HTML, Sprig, cold construction, caller-owned writer, and small and large named-template paths. Output digests gate every shared render comparison. |
| Profile-guided VM and value-adapter optimization | covered | Callable metadata, HTML replacement, `printf` parsing, shared adapters, lazy execution storage, and explicit named caller stacks each have profiles, focused benchmarks, and regression tests. |
| Allocation and output-buffer optimization | covered | `benchmarks.memory` records explicitly named Python peak and retained metrics. Lazy context storage materially reduces named-template peak memory. A list-backed return buffer was measured and rejected; `StringIO` and direct writer streaming remain. |
| Bounded caches with concurrency tests | covered | All nine source caches declare finite `maxsize` values. The user-controlled `printf` cache is filled beyond its 4,096 limit and rendered concurrently across eight threads. Regex, Unicode, timezone, callable, and built-in registries retain explicit finite limits. |
| Python-AST feasibility decision | covered | `benchmarks.backend_feasibility` records dispatch-only Amdahl upper bounds. `m6-ast-backend-decision.md` retains the VM and defines objective reopening gates. |
| Automated historical tracking | covered | `performance-history.yml` runs sampled render, parser, async, and memory benchmarks for release-labeled PRs, `v*` tags, and manual dispatches; revision-named JSON artifacts are retained for 90 days. The workflow policy has an executable repository test, and every artifact-producing CLI has smoke coverage or a real local run. |
| Full Go comparison report | covered | `m6-performance.md` records CPython 3.14.7 / Go 1.27.0 parser and eight-render medians, raw-distribution RSD, Go allocations and bytes, async results, Python memory, environment, limitations, and reproduction commands. The dedicated Go 1.27 upgrade report records behavioral and baseline changes. |

## Acceptance Gates

| Gate | Status | Evidence |
| --- | --- | --- |
| Conformance, parity, and security remain green | passed | The final `./scripts/check.sh` runs the complete test corpus, strict types, formatting, generated-artifact verification, and pinned Go oracle. It passes 1,369 tests. Text, async, HTML security, Sprig, Slim-Sprig, Python-adaptation, Python-engine comparison, profiling, native-prototype, and per-fixture attribution tests are included with no optimization-only skips. |
| Variance and environment metadata | passed | Seven-sample parser, render, and async results preserve every value and population RSD. Twenty-five-sample memory results preserve raw values. All artifacts include Python, Go where applicable, platform, and machine metadata. |
| No unexplained representative regression above policy | passed | A root frame-object design with a 2-3% non-call cost and a list-backed buffer with no gain were discarded. Retained context/caller-stack changes improved or tied literal, text, HTML, and named checks. No statistically credible retained regression above 5% remains; noisy writer and small-named distributions are disclosed and support no fine-grained claim. |
| No unconditional sync async overhead | passed | The synchronous VM imports no `asyncio` or event-loop APIs. Awaitability is rejected only at values returned by callable boundaries. The sampled no-await async/sync ratio is reported separately rather than charged to sync rendering. |
| Cache growth bounded and measured | passed | Source audit finds only explicit `lru_cache(maxsize=...)` decorators. Capacity, hot reuse, and thread sharing are tested, and the cache benchmark records equivalent parsed output before timing. |
| Claims are reproducible | passed | Every claim names a checked-in benchmark command and fixture. The shared operation is used by timing, memory, and feasibility tools; CLI smoke tests and real Python 3.14 / Go 1.27 runs produced the final artifacts. No single-sample observation is promoted to a headline claim. |

## Final Gate

The final gate ran on CPython 3.14.7 and passed 1,369 tests. Coverage measured
7,496 executable statements with zero misses and 3,066 branches with one
pre-existing partial lexer branch, for 99% branch-aware coverage. Ruff, Ruff
format, strict Pyright, generated Unicode checks, `gofmt`, and the pinned Go
oracle module all passed.

The complete local CPython 3.11-3.14 and PyPy 3.11 results are recorded in
`m0-python-matrix.md`. Differing statement counts reflect interpreter-specific
executable-line accounting; every run had zero statement misses. The CPython
3.14 count above is the M6 exit evidence.

## Deferred Work

- Hosted-runner history is trend evidence, not stable-hardware release gating.
- A Python-AST backend remains conditional on the objective reopening gates in
  the decision report.
- Release-wide mutable template-set APIs and final compatibility classification
  remain assigned to M10.
