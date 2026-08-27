# Release Process

Distribution ownership, version compatibility, supported runtimes, and
deprecation rules are defined in [the support policy](support.md). Security
releases also follow [the private reporting policy](https://github.com/Revolution1/pygotpl/blob/main/SECURITY.md).

## Release Readiness

A release candidate must satisfy the active release milestone and pass:

- Ruff and formatting checks.
- Strict Pyright.
- Unit, conformance, Python-native, property, and security suites applicable to
  the implemented feature set.
- Required CPython, PyPy, and operating-system jobs.
- Package build and isolated wheel installation.
- Go oracle verification at the pinned reference revision.
- Representative Python/Go benchmarks without an unaccepted regression.
- A strict documentation build, compatibility matrix, and changelog review.

No release may claim compatibility beyond measured conformance evidence.

## Hosted Workflow Policy

GitHub-hosted runners are intentionally release-only:

- a pull request runs hosted jobs only while it has the `release` label;
- a `v*` release tag runs the final CI, performance, and documentation jobs;
- `workflow_dispatch` remains available for an explicit maintainer decision;
- ordinary branch pushes and unlabeled pull requests allocate no runner.

Adding or synchronizing a release-labeled pull request runs the complete CI and
performance gates. Its documentation job builds the site but does not publish
it. Pages deployment occurs only for a release tag or a manual dispatch.

## Versioning

Before 1.0, minor releases may add or revise unstable API while patch releases
must preserve documented behavior. Version 1.0 freezes the documented public API
and follows semantic versioning.

Reference upgrades to Go or Sprig require their own compatibility report and are
never hidden inside an unrelated patch release.

## Procedure

1. Confirm that the milestone exit gates are checked with linked evidence.
2. Update versions in all three `pyproject.toml` files, coordinated dependency
   ranges, [`CHANGELOG.md`](https://github.com/Revolution1/pygotpl/blob/main/CHANGELOG.md),
   the compatibility report, and the benchmark report.
3. Open or update the release pull request and apply the `release` label.
4. Regenerate `uv.lock` with the required stable uv version.
5. Run `./scripts/check.sh` from a clean checkout.
6. Require the release PR's complete hosted gate to pass before merging.
7. Build all three distributions with `uv build --all-packages`.
8. Run `scripts/check_reproducible_builds.sh` with the release epoch and compare
   its artifacts with the publication build.
9. Install the wheel into an isolated environment and run the public smoke test.
   Use `python scripts/check_wheel_matrix.py` on every supported interpreter;
   the hosted matrix supplies the required operating-system coverage.
10. Create a signed `v*` release tag after the release PR passes and merge it.
11. Require the tag CI and documentation deployment to pass.
12. Publish through a trusted GitHub Actions environment using PyPI trusted
   publishing, in dependency order: `goduration`, then `gotime`, then `gotpl`.
13. Install all three packages from PyPI in a clean environment and verify
   package metadata, declared dependency bounds, imports, and a public render.
14. Publish release notes containing compatibility counts, known differences,
    security notes, and benchmark environment details.

Publishing automation will be added only after the PyPI projects and trusted
publishing environment are configured. The package license and upstream review
are complete.

## Rollback

Never replace an existing distribution artifact. If a release is defective,
yank it when appropriate, document the reason, fix forward with tests, and
publish a new version.
