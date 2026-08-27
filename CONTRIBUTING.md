# Contributing

## Before Starting

Read `AGENTS.md`, the active milestone, and the relevant architecture,
compatibility, testing, performance, dependency, and reference documents.

Read `docs/licensing.md` before using upstream material. Do not mechanically
copy upstream source or tests. Copyrightable upstream expression or substantial
data requires a specific notice and review. Local upstream checkouts are
created with `./scripts/sync_references.sh` and remain ignored by Git.

By intentionally submitting a contribution for inclusion, you license it under
Apache License 2.0 unless you explicitly state otherwise. You must have the
right to submit the work and identify any third-party material with separate
terms or attribution requirements.

## Environment

Install a current uv release satisfying `pyproject.toml`, Go 1.27.0, and a
supported Python version. Python 3.14 is the primary development runtime.

```console
uv sync --frozen --all-groups
./scripts/sync_references.sh
./scripts/check.sh
```

Preview documentation with `uv run --group docs mkdocs serve`. The full check
builds it with `--strict`, so broken internal links and unresolved API objects
fail CI.

## Test-Driven Workflow

Behavioral changes use red-green-refactor:

1. Find the relevant upstream behavior or define the Python-specific contract.
2. Add a focused test or conformance fixture.
3. Run it and confirm that it fails for the intended reason.
4. Implement the smallest complete behavior that makes it pass.
5. Run the focused suite and then `./scripts/check.sh`.
6. Refactor only while the suite remains green.

Compatibility fixtures record their reference revision and source metadata.
Python-native behavior requires its own tests, especially for asyncio,
cancellation, concurrency, exceptions, writers, and value adaptation.

## Change Requirements

- Keep changes within the active milestone.
- Add regression tests for every bug fix.
- Do not reduce coverage or weaken strict type checking.
- Add benchmarks for hot-path changes or performance claims.
- Update compatibility and milestone documents with behavior changes.
- Keep runtime dependencies at zero unless an architecture decision approves
  one.
- Keep public APIs small, typed, and documented.

## Pull Requests

Describe the behavior, the red test, the implementation, compatibility evidence,
and performance impact. CI must pass on all required platforms. Known gaps must
be explicit and assigned to a milestone.

Hosted runners are reserved for release validation. Ordinary pull requests do
not allocate a runner. Apply the `release` label when a pull request is ready to
be treated as a release candidate; every subsequent synchronization reruns the
full hosted gates until that label is removed. Maintainers may use a manual
workflow dispatch for exceptional validation.
