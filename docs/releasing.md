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

## Versioning

Before 1.0, minor releases may add or revise unstable API while patch releases
must preserve documented behavior. Version 1.0 freezes the documented public API
and follows semantic versioning.

Reference upgrades to Go or Sprig require their own compatibility report and are
never hidden inside an unrelated patch release.

## Procedure

1. Confirm that the milestone exit gates are checked with linked evidence.
2. Update the version, [`CHANGELOG.md`](https://github.com/Revolution1/pygotpl/blob/main/CHANGELOG.md), compatibility report,
   and benchmark report.
3. Regenerate `uv.lock` with the required stable uv version.
4. Run `./scripts/check.sh` from a clean checkout.
5. Verify the GitHub Pages preview or deployment for the release commit.
6. Build distributions with `uv build`.
7. Run `scripts/check_reproducible_builds.sh` with the release epoch and compare
   its artifacts with the publication build.
8. Install the wheel into an isolated environment and run the public smoke test.
   Use `python scripts/check_wheel_matrix.py` on every supported interpreter;
   the hosted matrix supplies the required operating-system coverage.
9. Create a signed release tag after CI passes on the release commit.
10. Publish through a trusted GitHub Actions environment using PyPI trusted
   publishing.
11. Verify package metadata and installation from PyPI.
12. Publish release notes containing compatibility counts, known differences,
    security notes, and benchmark environment details.

Publishing automation will be added only after the PyPI projects and trusted
publishing environment are configured. The package license and upstream review
are complete.

## Rollback

Never replace an existing distribution artifact. If a release is defective,
yank it when appropriate, document the reason, fix forward with tests, and
publish a new version.
