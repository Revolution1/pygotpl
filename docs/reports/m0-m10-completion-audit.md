# M0-M10 Completion Audit

## Conclusion

Every locally implementable milestone deliverable and acceptance gate passes on
the current workspace. M1 through M8 are complete. M0, M9, and M10 remain open
only where their documents explicitly require observed external GitHub/PyPI
state. No unchecked implementation, license, or local test gate is hidden
behind those external items.

## Milestone Evidence

| Milestone | Current status | Primary evidence | Remaining gate |
| --- | --- | --- | --- |
| M0 Foundation | local scope complete | `m0-foundation.md`, `m0-license-review.md`, `m0-python-matrix.md`, root contracts, frozen lock, and passing local gate | hosted CI |
| M1 Parser and IR | complete | `m1-conformance.md`, parser differential/property suites, and parser/compiler coverage | none |
| M2 Synchronous text runtime | complete | `m2-acceptance-audit.md`, 68 differential fixtures, public API tests, and text benchmarks | none |
| M3 Async runtime | complete | `m3-async-runtime.md`, sync/async parity, cancellation, writer, concurrency, and latency suites | none |
| M4 Sprig and Slim-Sprig | complete | `m4-sprig-evidence.json`, 211-function Sprig ledger, 164-name Slim matrix, security profiles, and benchmarks | none |
| M5 Contextual HTML | complete | `m5-acceptance-audit.md`, 34 differential fixtures, contextual security corpus, and HTML benchmarks | none |
| M6 Performance | complete | `m6-complete-performance-report.md`, Jinja/Mako/Chameleon comparisons, profiles, history workflow, and backend decisions | none |
| M7 Package architecture | complete | `m7-package-architecture-audit.md`, D012, import-layer tests, three coordinated wheels, and standalone package suites | none |
| M8 Ecosystem | complete | `m8-acceptance-audit.md`, Sprout inventory/oracle evidence, Helm integration fixtures, CLI example, and integration profiles | none |
| M9 Python platform | local scope complete | `m9-sandbox.md`, adversarial security suite, current local interpreter matrix, and wheel-only smoke | hosted Linux/macOS/Windows matrix |
| M10 Version 1.0 | local scope complete | M10 API design, documentation, compatibility, performance, package, reproducibility, and release-readiness reports | earlier external gates, signing, and publication |

All referenced report paths are relative to this directory unless the artifact
is a root contract or test suite.

## Current Verification

- CPython 3.11.16, 3.12.14, 3.13.15, and 3.14.7 each pass 1,970 tests.
- PyPy 3.11.15 passes 1,966 tests and skips only four unavailable
  `tracemalloc` sampling tests.
- CPython 3.14 coverage is 98.1002% statement and 96.0893% branch.
- PyPy 3.11 coverage is 98.1214% statement and 96.1114% branch.
- Ruff, formatting, strict Pyright, generated artifacts, and all pinned Go
  oracles pass.
- The strict MkDocs site build, generated API reference, and hosted Pages
  deployment pass.
- The full M10 benchmark suite contains no unaccepted regression above policy.
- `gotpl`, `goduration`, and `gotime` build as `py3-none-any` wheels and pass
  compiler-free installation smoke tests on every locally supported
  interpreter.

## Open External Sequence

1. Resolve the first hosted matrix's cross-platform failures, then apply the
   `release` label to a release PR and require all jobs to pass.
2. Configure trusted publishing, signing, and provenance attestations.
3. Publish the three distributions and verify a clean installation from PyPI.

The authoritative owner checklist is
[`m10-release-readiness.md`](m10-release-readiness.md). A milestone remains open
until its own unchecked gate has direct evidence; workflow configuration or a
local substitute is not enough.
