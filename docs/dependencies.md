# Dependency and Standards Policy

## Principles

The project prefers current stable releases and current standardized project
metadata. Reproducibility and compatibility evidence remain mandatory, so
"latest" means the newest stable release that passes the full applicable suite,
not an unpinned environment.

Previews, release candidates, nightly interpreters, and development branches may
run in forward-looking non-blocking jobs. They do not become the compatibility
or release baseline until stable.

## Python Policy

- Public support begins at Python 3.11.
- Development, profiling, and headline Python benchmarks use the latest stable
  CPython feature release, currently Python 3.14.
- CI covers every supported CPython minor version.
- PyPy is tested when it provides a compatible release for the supported range.
- Syntax and typing remain valid on the minimum supported Python version.

Supporting older maintained Python releases broadens library usability without
preventing development on the latest stable runtime. Raising the minimum is a
documented compatibility decision.

## Packaging Standards

- PEP 517 build isolation with Hatchling.
- PEP 621 project metadata in `pyproject.toml`.
- PEP 735 dependency groups for development-only dependencies.
- PEP 561 `py.typed` marker for typed-package distribution.
- A checked-in, cross-platform `uv.lock` for exact development resolution.
- uv 0.12.5 or newer for project environment and lock-file operations.

Published runtime requirements belong in `project.dependencies`. Test, quality,
and benchmark tools belong in dependency groups and must not be exposed as
package extras.

## Workspace Package Policy

The uv workspace contains independently buildable `goduration` and `gotime`
distributions alongside `gotpl`. The deliberately narrow formatting and
RE2-compatible implementations are private modules in the gotpl wheel rather
than independent product commitments. The root `uv.lock` coordinates
development and CI, while each retained leaf has its own PEP 621 metadata,
build configuration, declared dependencies, typing marker, tests, and wheel
verification.

Workspace dependency direction is intentionally narrow: `gotime` may depend on
`goduration`; gotpl may depend on both leaves, but neither leaf may depend on
gotpl. Sprout and Helm are owned opt-in modules in `gotpl.funcs`. External
Python-extension packages consume stable public boundaries rather than private
workspace modules.

Workspace source mappings are development configuration, not a publication
claim. Before any external release, every coordinated constraint
must resolve against built artifacts without workspace overrides, and the
license, package-index ownership, versioning, release order, and rollback gates
in `docs/extraction-candidates.md` must pass.

Jinja, Mako, and Chameleon are comparison engines in the benchmark group.
Cython and setuptools are also benchmark-only tools used to reproduce the M6
native feasibility prototype. None is imported by the installed production
runtime or included as an optional runtime capability.

MkDocs Material and mkdocstrings with its Python handler are development-only
documentation tools in the `docs` dependency group. MkDocs produces the static
site, Material supplies the user-facing theme and navigation, and mkdocstrings
generates API reference pages from the same typed public objects that ship in
the wheels. None is a runtime dependency.

`tzdata` and `tzlocal` are the unconditional runtime dependencies. Python's
`zoneinfo` uses tzdata as the IANA database fallback on systems without a
system database, notably Windows. tzlocal discovers the system's IANA local
zone across Unix, macOS, and Windows so Sprig's `Local` behavior retains DST
transitions instead of freezing the current UTC offset. Named and local-zone
behavior are part of the default Sprig date API, so making either dependency
optional would make the core compatibility profile vary by platform. Their
lower bounds track the current stable releases reviewed by the project.

The `helm` extra provides PyYAML and tomli-w for Helm's YAML and TOML
serialization functions and the miniature chart CLI. Deserialization uses
Python's standard-library `json` and `tomllib` modules. The module remains
importable without the extra; serializer use reports `gotpl[helm]`.

Optional runtime capabilities use PEP 621 `project.optional-dependencies`.
Heavy or specialized packages, including cryptography implementations, must not
become unconditional dependencies merely because one registry function needs
them. The `crypto` extra provides bcrypt, AES, private-key, and certificate
backends through bcrypt and cryptography. Future extra names are capability
based, such as `helm`, rather than being named after an incidental
implementation package. An `all`
extra may aggregate stable capability extras after their dependency sets exist.

The public module for an optional capability remains importable without its
extra. The first explicit use reports the exact extra
to install, for example `gotpl[crypto]`; unrelated functions continue to
work. Extras are added to `pyproject.toml` only when their first implementation
lands, at which point the runtime-dependency review below is required.

## Version Strategy

`pyproject.toml` records reviewed lower bounds for direct tools. `uv.lock`
records exact direct and transitive versions. At project initialization, lower
bounds are set to the current stable direct versions.

Dependency updates must:

1. Select the latest stable release.
2. Regenerate the lock file with the supported uv workflow.
3. Run formatting, linting, strict type checks, unit tests, and conformance tests.
4. Run security tests for parser, HTML, crypto, or serialization changes.
5. Run representative benchmarks when runtime behavior or tooling can affect
   measured results.
6. Record required migration or compatibility changes.

Avoid upper bounds unless an observed incompatibility requires one or a
coordinated workspace dependency must exclude an unknown future major version.
Runtime dependencies require an architecture decision that explains why the
standard library is insufficient and assesses performance, security,
maintenance, and platform impact.

## Reference Dependencies

Go, Sprig, Slim-Sprig, Sprout, and Helm are special reference inputs. Their exact
revisions remain pinned even when newer releases appear. Updating a reference
changes the claimed compatibility baseline and requires the upgrade process in
`docs/references.md`. Reference oracle modules are isolated when their pinned
upstreams require conflicting transitive versions; “latest dependency” policy
must never turn one pinned compatibility target into a mixed module graph.

## Current Audit Snapshot

The August 27, 2026 dependency audit established:

- CPython 3.14.7 and Go 1.27.0 as the latest stable interpreter and reference
  toolchain;
- PyPy 3.11.15 / 7.3.23 as the current compatible alternative interpreter;
- Sprig v3.3.0, Slim-Sprig v3.0.0, and Sprout v1.1.1 as the latest remote
  repository tags;
- Jinja 3.1.6, Mako 1.4.1, and Chameleon 4.6.0 as the current comparison
  engines, plus Cython 3.3.0 and setuptools 84.0.0 for the rejected native
  prototype;
- uv 0.12.5 as the current project tool satisfying the required version; and
- MkDocs Material 9.7.7, mkdocstrings 1.0.6, and mkdocstrings-python 2.0.7 for
  the generated documentation site;
- a valid frozen lock under uv 0.12.5; and
- no outdated direct runtime, optional, test, quality, or benchmark dependency
  reported by `uv tree --outdated --depth 1`.

The primary evidence is the official Python and Go release history, direct
upstream tag queries, and the uv resolver. This snapshot is dated evidence, not
a promise that versions cannot change; a future audit must repeat the same
checks.

## Automation

Automated update tooling may propose dependency and action updates. It must not
merge them without the same required checks as a manual update. Lock-file-only
changes must remain reviewable and traceable to direct dependency changes.
