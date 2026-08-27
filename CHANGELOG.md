# Changelog

All notable changes to this project are documented in this file. The project
uses [Semantic Versioning](https://semver.org/) for stable releases.

## Unreleased

### Added

- Pure Python `text/template` and contextual `html/template` parsing,
  compilation, synchronous execution, and asynchronous execution.
- Immutable single-source and multi-source template APIs, including named
  execution, streaming writers, dynamic source rendering, and reusable
  cross-file namespaces.
- Explicit Go-compatible and Python-native formatting modes.
- Sprig 3.3.0, Slim-Sprig 3.0.0, Sprout 1.1.1, and Helm function profiles that
  remain separate from the default Go registry.
- Opt-in Python functions, sandbox policies, and per-render execution budgets.
- Standalone `goduration` and `gotime` distributions with Go-compatible and
  Python-native object APIs.
- A miniature Helm CLI example and reusable core multi-source engine.
- Differential Go oracles, security and property suites, exact coverage gates,
  cross-engine benchmarks, reproducible builds, and compiler-free wheel smoke
  tests across supported local interpreters.
- A task-oriented MkDocs Material site, generated API reference, strict local
  documentation gate, and GitHub Pages deployment workflow.

### Changed

- The import package is `gotpl`; `pygotpl` remains the repository name only.
- Sprig, Slim-Sprig, Sprout, Helm, and Python-native helpers live under explicit
  `gotpl.funcs` and `gotpl.pythonic` namespaces.
- Narrow Go formatting and regular-expression compatibility support is private
  under `gotpl._compat` instead of being published as separate distributions.
- Contextual HTML convenience functions expose the same explicit typed options
  as their text equivalents.

### Compatibility

- Parser, runtime, HTML, Sprig, Slim-Sprig, Sprout, and Helm evidence is
  classified in `docs/reports/m10-compatibility.md`.
- Unqualified compatibility claims remain prohibited for areas whose complete
  upstream conformance suite has not yet been ported.

### Release blockers

- Pass the hosted operating-system and interpreter matrix.
- Publish and verify the GitHub Pages documentation site.
- Sign and attest release artifacts.
- Publish and verify the coordinated `gotpl`, `goduration`, and `gotime`
  distributions.
