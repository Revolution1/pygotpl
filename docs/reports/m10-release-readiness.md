# M10 Release Readiness

## Current State

All release gates that can be completed in the local pre-publication workspace
pass as of August 27, 2026. The project is Apache-2.0 licensed and the upstream
adaptation review is approved. The repository is not yet releasable because the
remaining gates require external GitHub and PyPI state.

## Verified Locally

- `scripts/check.sh` passes with 1,973 tests, Ruff, formatting, strict Pyright,
  generated-file checks, and every Go oracle.
- Exact coverage is 98.1002% statement and 96.0893% branch.
- Six wheel and source-distribution artifacts from two independent builds are
  byte-for-byte reproducible with a fixed source epoch.
- The coordinated `gotpl`, `goduration`, and `gotime` wheels install together
  in an isolated environment and render without Go or a compiler on `PATH`.
- The current suite and wheel-only smoke pass locally on CPython 3.11-3.14 and
  PyPy 3.11; hosted Linux, macOS, and Windows execution remains outstanding.
- The complete release benchmark suite has no unaccepted regression above the
  published 10% blocking threshold.
- Public APIs, exception classes, compatibility counts, support policy,
  security policy, and known differences are documented and tested.
- The task-oriented MkDocs site and generated API reference pass strict local
  validation and deploy successfully through GitHub Pages.
- All three distributions declare Apache-2.0 with canonical license files; the
  main distribution also carries the reviewed BSD/MIT third-party notices.

## External Gates

| Gate | Why it remains open | Required owner action |
| --- | --- | --- |
| Hosted platform matrix | The first hosted run exposed missing ignored reference setup, wheel-smoke PATH isolation, and Windows encoding, path, and timezone differences. It is evidence of unresolved gates, not a passing matrix. | Resolve the recorded cross-platform failures, apply the `release` label to a release PR, and require every job to pass. |
| Signed artifacts and provenance | Local reproducibility does not create a signed tag, GitHub attestation, or publication provenance. | Configure signing and attest the artifacts built from the release commit. |
| Distribution publication | `gotpl`, `goduration`, and `gotime` have not been published and tested from PyPI. | Create the projects, configure trusted publishing, publish together, and run the post-publication smoke test. |

No milestone checkbox is closed merely because its workflow is configured.
Hosted execution, signing, and package-index installation must be observed on
the release commit before those gates pass.

## Owner Sequence

1. Resolve the failures exposed by the initial hosted matrix.
2. Open a release PR, apply the `release` label, and observe the full CPython
   3.11-3.14, PyPy 3.11, Linux, macOS, Windows, Go oracle, package, and
   benchmark-smoke jobs.
3. Configure PyPI trusted publishing for all three distributions.
4. Build from the signed release commit, publish attestations and checksums,
   upload the coordinated distributions, and verify a clean PyPI installation.

The detailed command order and rollback policy are defined in
[`docs/releasing.md`](../releasing.md).
