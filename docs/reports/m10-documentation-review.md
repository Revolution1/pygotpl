# M10 Documentation Review

## Result

The documentation is ready for a pre-1.0 user-facing site. The review replaced
the repository's flat documentation index with task-oriented navigation, added
the missing onboarding and language guides, generated API reference pages from
the shipped Python objects, and made documentation validation part of the local
and hosted quality gates.

GitHub Pages publication completed successfully from the release-candidate
branch on August 27, 2026.

## Full-Surface Follow-up Review

A second pass reviewed every Markdown document, generated evidence artifact,
and public API group for design clarity, user friendliness, and redundant
surface. It shortened the root README, removed the redundant “Why gotpl?”
section, corrected stale package and internal import paths, made PyPI install
and dependency guidance consistent across all three distributions, and added
runnable examples for async writers and reuse, contextual HTML, sandbox
budgets, function registries, compatibility adapters, Go formatting protocols,
time precision, and deterministic scheduling.

Generated signature pages remain deliberately low-redundancy: task guides own
examples and reference pages link to them. Every changed example was executed
directly or covered by its focused test suite, and the strict site still
generates 138 files.

## Reviewed Material

The review covered the root README, all top-level documents under `docs/`, both
standalone package READMEs, example guidance, public docstrings, milestone
documents, and reports. Historical reports remain evidence rather than primary
user guidance; they are generated into the site but excluded from the main
navigation unless a current maintainer workflow links to them.

## Findings and Resolutions

| Finding | Resolution |
| --- | --- |
| The README mixed onboarding, internals, benchmarks, reports, and release gates in one long index. | Keep a short task-oriented README index and move the full hierarchy into site navigation. |
| There was no standalone template-language guide. | Add values, pipelines, control flow, range, variables, associations, whitespace, delimiters, and built-ins. |
| Async behavior was spread across the README and API contract. | Add a focused guide covering mixed callbacks, writers, cancellation, concurrency, and the async-iterable boundary. |
| Contextual HTML behavior was described but not offered as a direct user journey. | Add a dedicated guide that separates contextual escaping, trusted types, and sandboxing. |
| Function profiles were hard to compare. | Add one guide for Sprig, Slim-Sprig, Sprout, Helm, Python-native functions, hermetic choices, and extras. |
| The API reference was maintained only by hand. | Retain the curated API overview and add mkdocstrings pages generated from gotpl, registry, goduration, and gotime objects. |
| Some user examples imported `TemplateEngine` from its implementation owner. | Use the package-root export as the canonical user import. |
| Links from the docs tree to root security and changelog files failed static-site validation. | Use canonical repository links for files outside the MkDocs documentation root. |

## Information Architecture

The primary navigation follows user intent:

1. Home and installation.
2. Template, async, HTML, function-library, sandbox, multi-file, and migration
   guides.
3. Curated and generated API reference.
4. Compatibility, performance, and support expectations.
5. A separate maintainer section for architecture, testing, dependencies,
   references, licensing, releasing, and milestones.

The compatibility contract remains authoritative for behavior claims. The API
overview defines the stability boundary. Reports record evidence at a point in
time and must not silently override either current contract.

## Site Tooling

- MkDocs 1.6.1 generates the static site.
- MkDocs Material 9.7.7 supplies responsive navigation, search, code copying,
  and light/dark palettes.
- mkdocstrings 1.0.6 with mkdocstrings-python 2.0.7 generates typed Python API
  pages from all three workspace distributions.
- `mkdocs build --strict` is run by `scripts/check.sh`, the CI quality job, and
  the Pages build job.
- `site/` is generated and ignored; source Markdown and configuration are the
  reviewable artifacts.

These packages live only in the `docs` dependency group and do not affect any
runtime wheel.

## GitHub Pages Design

`.github/workflows/pages.yml` builds for release-labeled pull requests, `v*`
release tags, or a manual dispatch. A release PR validates documentation without
publishing it. The deploy job runs only for a tag or manual dispatch, receives
`pages: write` and `id-token: write`, targets the protected `github-pages`
environment, and publishes the generated artifact. Official Pages actions are
pinned to immutable commits for their current stable major releases.

Pages uses GitHub Actions and the account's configured Pages domain, producing
the project URL `http://blog.kyonr.com/pygotpl/`. The account-level custom
domain does not currently enforce HTTPS; enabling it requires a valid
certificate for `blog.kyonr.com` in the owner Pages configuration.

## Verification

- The strict site build completes and generates 138 files.
- All expected landing, guide, manual API, and generated API pages exist.
- mkdocstrings resolves the public render helpers, template classes, policies,
  function maps, duration objects, and time objects.
- GitHub Actions run `33039273688` built and deployed the site successfully,
  and the public page returned HTTP 200 with the expected description.
- Ruff, formatting, strict Pyright, 1,973 tests, coverage thresholds, generated
  artifacts, and all pinned Go oracles pass in `scripts/check.sh`.
