# Packaging, Release, and Support Policy

## Distributions

The repository releases three pure Python distributions:

- `gotpl`, the template engine and opt-in function libraries;
- `goduration`, the standalone duration value API; and
- `gotime`, the standalone time API, which depends on `goduration`.

`gotpl` depends on both value packages. Formatting and RE2 compatibility are
private `gotpl._compat` implementation modules and are never published as
independent distributions. Sprig, Slim-Sprig, Sprout, Helm functions and
runtime extensions, and Python-native helpers ship in the `gotpl` wheel and do
not create separate release lifecycles.

The three distributions use coordinated compatibility testing and semantic
versioning. Their patch versions need not remain numerically identical, but a
published `gotpl` release declares bounded dependency ranges that exclude an
incompatible future major version. A breaking change in a shared value contract
requires coordinated major releases and a migration guide.

## Python and Platform Support

The 1.0 line supports CPython 3.11 through 3.14 and PyPy 3.11. Required CI
covers:

- CPython 3.11 through 3.14;
- PyPy 3.11; and
- Linux, macOS, and Windows.

A new stable Python minor is adopted after the applicable full suite passes;
`Requires-Python >=3.11` is an installation floor, not an automatic support
promise for every future Python release.
Dropping a Python minor is a documented compatibility change and will not occur
in a patch release. Pure Python wheels are the normal artifacts; runtime use
does not require Go, a subprocess, a compiler, or a native extension.

## Compatibility References

Template compatibility is measured against the exact Go, Sprig, Slim-Sprig,
Sprout, and Helm versions listed in [Compatibility](compatibility.md). Updating
a reference is an explicit change with regenerated evidence, full conformance
tests, and a compatibility report. It is not bundled silently into maintenance
work.

## Versioning and Deprecation

After 1.0, documented public APIs follow semantic versioning:

- patch releases contain compatible fixes and performance improvements;
- minor releases may add compatible APIs and deprecations; and
- major releases may remove or change documented behavior.

A normal public API removal is deprecated for at least one minor release before
the next major release. Immediate removal is reserved for behavior that cannot
be retained safely; the security advisory and release notes must explain the
exception. Private modules, undocumented internals, examples, benchmarks, and
oracle tools do not receive this stability guarantee.

## Optional Dependencies

Core import and rendering remain usable without extras. Specialized functions
load dependencies lazily and report the installation extra when unavailable.
Installing an extra does not inject its functions into a template registry and
does not weaken a sandbox policy. Supported extras and their locked development
versions are maintained in [Dependencies](dependencies.md).

## Releases and Rollback

Release candidates follow [the release process](releasing.md), including the
full platform matrix, exact coverage thresholds, oracle verification, isolated
wheel installation, and benchmark review. Artifacts are immutable. A defective
release is yanked when appropriate and fixed forward with a new version; an
existing wheel or source archive is never replaced.

`gotpl`, `goduration`, and `gotime` are tested together before publication. A
release note identifies minimum and maximum compatible major versions and any
coordinated rollback requirement.

## Getting Help

Use [GitHub issues](https://github.com/Revolution1/pygotpl/issues) for
reproducible bugs, compatibility gaps, documentation problems, and feature
proposals. Include the Python and package versions, platform, minimal template
and data, selected function maps, format and missing-key modes, and the complete
error chain. Compatibility reports should include native Go output when
practical.

Use the private process in
[SECURITY.md](https://github.com/Revolution1/pygotpl/blob/main/SECURITY.md) for
vulnerabilities.
The project does not promise a fixed feature or release cadence. Security,
correctness, and regressions in documented stable APIs take priority over new
function libraries and speculative optimizations.
