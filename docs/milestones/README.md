# Milestones

Milestones are acceptance-gated. Dates are planning estimates, not completion
criteria. Work should remain inside the active milestone unless it removes a
documented prerequisite.

For current release blockers, use the
[M10 release-readiness report](../reports/m10-release-readiness.md); completed
milestone pages remain historical scope and evidence ledgers.

| Milestone | Outcome | Estimate | Status |
| --- | --- | --- | --- |
| [M0](m0-foundation.md) | Repository, contracts, oracle, and benchmark foundation | 1 week | awaiting hosted CI evidence |
| [M1](m1-parser-ir.md) | Compatible lexer/parser and executable IR | 2-3 weeks | complete |
| [M2](m2-text-template-sync.md) | Reusable synchronous `text/template` engine | 3-5 weeks | complete |
| [M3](m3-async-runtime.md) | First-class async function execution | 2-3 weeks | complete |
| [M4](m4-sprig.md) | Versioned Sprig 3.3.0 compatibility | 4-7 weeks | complete |
| [M5](m5-html-template.md) | Contextually safe `html/template` engine | 8-12 weeks | complete |
| [M6](m6-performance.md) | Go/Python comparisons, profiling, and performance hardening | 6-9 weeks | complete |
| [M7](m7-package-architecture.md) | Workspace packages and architecture foundation | 8-12 weeks | complete |
| [M8](m8-ecosystem.md) | Sprout and Helm ecosystem integrations | 4-7 weeks | complete |
| [M9](m9-python-platform.md) | Sandbox and bounded Python extensions | 4-7 weeks | implementation complete; awaiting hosted matrix |
| [M10](m10-v1.md) | Stable API and evidence-backed 1.0 release | 3-4 weeks | active; awaiting hosted CI and external release gates |

## Tracking Rules

- Only one milestone is active by default.
- Check boxes represent verified repository state, not intent.
- An exit gate may not be checked while its required CI job is skipped.
- Deferred work must name the destination milestone.
- Compatibility counts and benchmark baselines must link to reproducible data.
- Scope changes update both this index and the affected milestone document.
