# M6: Performance Hardening

## Outcome

Measure and reduce execution overhead against both Go and relevant Python
engines while preserving VM, async, compatibility, and security parity.

## Deliverables

- [x] Representative stable benchmark suite.
- [x] Profile-guided VM and value-adapter optimizations.
- [x] Allocation and output-buffer optimizations.
- [x] Bounded caches with concurrency tests.
- [x] Feasibility decision for a Python-AST code-generation backend.
- [x] Code-generation backend decision: not justified by measured opportunity.
- [x] Automated historical performance tracking.
- [x] Full benchmark report against Go.
- [x] Version-pinned Jinja comparison covering cold and warm text rendering,
  autoescaped HTML, sync and async calls, memory, and cache configuration.
- [x] Supplementary version-pinned Mako and Chameleon comparisons on their
  semantically comparable text and HTML capabilities, with unsupported
  capabilities reported rather than simulated.
- [x] Comprehensive deterministic, sampling, and allocation profiles for the
  representative parser, text, HTML, Sprig, sync, and async workloads.
- [x] Profile report that separates hotspot evidence from benchmark results and
  identifies optimization candidates by end-to-end opportunity.
- [x] Evidence-based decision to defer native work at near-Jinja performance or
  prototype Cython on one measured, self-contained hot path when the trigger is
  exceeded, including whether C, Rust, or no native implementation is justified.
- [x] Conditional optional-accelerator packaging decision: not required because
  the native prototype failed its retention gate; the complete pure Python
  installation remains the sole production path.

## Acceptance Gates

- [x] Every optimization passes conformance, backend parity, and security suites.
- [x] Performance results include variance and environment metadata.
- [x] No representative hot path has an unexplained regression above policy.
- [x] Sync rendering has no unconditional event-loop or coroutine overhead.
- [x] Cache growth is bounded and measured.
- [x] Performance claims in documentation are reproducible.
- [x] Jinja comparisons use semantically equivalent work, versioned fixtures,
  warm/cold separation, output validation, samples, and variance metadata.
- [x] Mako and Chameleon results disclose escaping, compilation, caching, and
  async capability differences and are not used as compatibility claims.
- [x] Profiles are captured outside headline timing runs and corroborated by
  sampled benchmarks before an optimization claim is accepted.
- [x] Native prototyping is deferred when pygotpl is no more than 1.20x slower
  than Jinja on at least two representative non-trivial warm workloads and no
  adopted latency budget is missed.
- [x] If that near-Jinja gate is not met, a native accelerator is not retained
  unless it improves at least two representative non-trivial end-to-end
  workloads by 25% or more without duplicating compatibility semantics.
- [x] The full pure Python implementation remains tested and installable on
  CPython and PyPy without a compiler or platform-specific wheel.

## Non-Goals

- Beating Go on every workload.
- Native extensions in the default runtime.
- Benchmark-only semantic shortcuts.

## Reopened Scope

The original Go comparison, VM hardening, memory work, and backend decision are
complete and remain frozen in the M6 reports. M6 was reopened for the
Python-ecosystem comparison, comprehensive profiling, and optional accelerator
decision above; that scope is now complete. Ecosystem-specific workloads such
as Helm are measured when their integration milestone lands and may then be
added to the ongoing M6 history suite.

## Evidence

The canonical combined result, bottleneck analysis, optimization priorities,
and reproduction commands are recorded in
[`../reports/m6-complete-performance-report.md`](../reports/m6-complete-performance-report.md).
The narrower Go, Python-engine, profiling, backend, native-prototype, inventory,
and acceptance reports remain supporting evidence for that consolidated view.
