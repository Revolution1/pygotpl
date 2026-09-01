# Changelog

All notable changes to this project are documented in this file. The project
uses [Semantic Versioning](https://semver.org/) for stable releases.

## Unreleased

### Fixed

- Stabilize Sprig rounding conformance at the three-decimal half-threshold
  across amd64 and arm64 Go oracle hosts.

### CI

- Replace the full operating-system/interpreter Cartesian product with a
  tiered release matrix: one complete Linux conformance and coverage job,
  focused alternate-interpreter and macOS runtime jobs, and a Windows installed
  wheel smoke test.
- Remove repeated workspace-package tests and the duplicate CI benchmark smoke;
  pinned Go checks, reproducible builds, Windows wheel installation, and the
  dedicated sampled performance workflow remain release gates.

## [0.1.0] - 2026-08-28

### Added

- Pure Python `text/template` and contextual `html/template` parsing,
  compilation, synchronous execution, and asynchronous execution.
- Immutable single-source and multi-source template APIs, including named
  execution, streaming writers, dynamic source rendering, and reusable
  cross-file namespaces. `with_functions()` derives a compiled template or
  engine with added or replaced callbacks without mutating its parent.
- Explicit Go-compatible and Python-native formatting modes.
- Sprig 3.3.0, Slim-Sprig 3.0.0, Sprout 1.1.1, and Helm function profiles that
  remain separate from the default Go registry.
- Opt-in Python functions, sandbox policies, and per-render execution budgets.
- Standalone `goduration` and `gotime-py` distributions with Go-compatible and
  Python-native object APIs.
- A miniature Helm CLI example and reusable core multi-source engine.
- Differential Go oracles, security and property suites, exact coverage gates,
  cross-engine benchmarks, reproducible builds, and compiler-free wheel smoke
  tests across supported local interpreters.
- A task-oriented MkDocs Material site, generated API reference, strict local
  documentation gate, a per-function built-in reference, and GitHub Pages
  deployment workflow.

### Changed

- The import package is `gotpl`; `pygotpl` remains the repository name only.
- Sprig, Slim-Sprig, Sprout, Helm, and Python-native helpers live under explicit
  `gotpl.funcs` and `gotpl.pythonic` namespaces.
- Narrow Go formatting and regular-expression compatibility support is private
  under `gotpl._compat` instead of being published as separate distributions.
- Contextual HTML convenience functions expose the same explicit typed options
  as their text equivalents.
- Published `gotpl` metadata resolves `goduration` and `gotime-py` from PyPI with
  compatible pre-2.0 version bounds; workspace sources remain development-only
  overrides.

### Compatibility

- Parser, runtime, HTML, Sprig, Slim-Sprig, Sprout, and Helm evidence is
  classified in the
  [M10 compatibility report](docs/reports/m10-compatibility.md).
- Unqualified compatibility claims remain prohibited for areas whose complete
  upstream conformance suite has not yet been ported.

### Known limitations

- Complete `text/template`, `html/template`, and `gotime` compatibility remains
  classified as partial beyond the measured scopes above.
- The original tag CI exposed hosted-workflow and platform-fixture issues that
  were corrected after the release; the published pure Python wheels passed
  their trusted-publishing workflows.
