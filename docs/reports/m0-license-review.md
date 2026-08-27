# M0 License and Upstream Adaptation Review

## Decision

The project owner selected Apache License 2.0 on August 27, 2026. Original
gotpl, goduration, and gotime work is distributed under SPDX identifier
`Apache-2.0`. The root and both workspace distributions contain the canonical
Apache license text byte-for-byte as published by the Apache Software
Foundation.

This repository review permits the planned upstream-informed compatibility
workflow subject to the controls below. It records project policy and evidence;
it is not a substitute for legal advice about a future exceptional artifact.

## Reviewed Inputs

| Input | Pinned revision | License | Distributed material |
| --- | --- | --- | --- |
| Go standard library | Go 1.27.0 | BSD 3-Clause | Generated Unicode tables and independently expressed conformance fixtures |
| Masterminds Sprig | v3.3.0 | MIT | Independently expressed fixtures and compatibility behavior |
| Slim-Sprig | v3.0.0 | MIT | Independently expressed fixtures and profile inventory |
| Sprout | v1.1.1 | MIT | Independently expressed fixtures, function inventory, aliases, and notices |

The checked-out license texts under `.references/` were compared with
`THIRD_PARTY_NOTICES.md`. The Go copyright, three redistribution conditions,
endorsement restriction, and warranty/liability disclaimer are retained. The
Sprig-family copyright, permission grant, notice condition, and disclaimer are
retained.

## Adaptation Boundary

- `.references/` is ignored and never included in a distribution.
- Reference source and tests determine observable behavior, edge cases, error
  meaning, and test selection; they are not mechanically translated.
- Conformance fixtures use the project's own schema and Python test structure.
  Each upstream-informed fixture records its project, pinned revision, source,
  behavior statement, and `derived` status.
- Copyrightable upstream expression, substantial tables, comments, or copied
  test bodies require an artifact-specific review and notice before inclusion.
- `src/gotpl/_compat/goregexp/_unicode_tables.py` is generated from the Go
  Unicode tables. Its generator, pinned source, and data version are documented,
  and the complete Go BSD notice is distributed with it.
- The goduration and gotime implementations, tests, and oracle clients are
  independently authored. They compare behavior with Go but do not distribute
  Go's `time` source or standard-library test bodies.

## Distribution Controls

- `gotpl` declares `license = "Apache-2.0"` and packages `LICENSE` plus
  `THIRD_PARTY_NOTICES.md` as PEP 639 license files.
- `goduration` and `gotime` each declare `license = "Apache-2.0"` and package
  their own canonical `LICENSE` file.
- A conformance test verifies the selected SPDX expression, required license
  files, identical Apache text, patent-grant section, and upstream fixture
  attribution.
- Wheel and source-distribution inspection verifies that installed metadata
  contains the declared license files. Reproducibility checks cover the same
  artifacts.

No Apache `NOTICE` file is created. `THIRD_PARTY_NOTICES.md` is a project
license file carrying third-party obligations, not an Apache Section 4(d)
project NOTICE. Redistributors must retain the license files shipped in package
metadata and comply with each included license.

## Review Result

The project license and current attribution strategy are approved for the
pinned M0-M10 scope. M0's project-license deliverable and upstream-adaptation
license gate may close. A reference upgrade, copied upstream expression,
additional generated dataset, or new third-party source requires a new review
before distribution.
