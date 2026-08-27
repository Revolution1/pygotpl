# M0: Foundation

## Outcome

Create the repository contracts and tooling needed to measure all later work.

## Deliverables

- [x] Root agent instructions.
- [x] Architecture, compatibility, testing, and performance contracts.
- [x] Acceptance-gated milestone plan.
- [x] Minimal `src`-layout Python package.
- [x] Ignored, pinned local upstream reference checkouts.
- [x] Reproducible upstream-reference bootstrap script and documentation.
- [x] Test-driven development workflow documented for agents.
- [x] Current packaging and dependency policy documented.
- [x] Milestone-ordered upstream test map with Python companion coverage.
- [x] Project license and upstream attribution policy.
- [x] Cross-platform uv development environment lock file.
- [x] Ruff, strict Pyright, pytest, and coverage CI configuration.
- [x] Go oracle module pinned to an exact Go 1.27 patch release.
- [x] Independently authored conformance fixture schema.
- [x] Shared Go/Python benchmark fixture schema.
- [x] Minimal smoke benchmark and comparison report.
- [x] Contribution and release-process documents.

## Acceptance Gates

- [x] A fresh checkout can install the development environment and run all
  checks using documented commands.
- [ ] CI passes on the initial supported Python and operating-system matrix.
- [x] One text template case runs through both Go and Python harnesses, even if
  the Python side is initially an explicit expected failure.
- [x] The first oracle case is developed red-green-refactor and records its
  upstream source metadata.
- [x] One benchmark case produces machine-readable Go and Python results.
- [x] License review permits the planned upstream-test adaptation strategy.
- [x] No runtime package dependency on Go exists.

## Non-Goals

- Parsing the Go template language.
- Implementing rendering behavior.
- Publishing compatibility percentages.

## Exit Artifact

An M0 completion note must record pinned tool versions, commands, initial CI
matrix, fixture formats, and the first benchmark environment.
