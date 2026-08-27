# M10 Public API Design Review

## Result

The public API is suitable for the 1.0 release candidate after one corrective
change: the four contextual HTML convenience functions now expose the same
explicit, typed construction options as their text equivalents. No public name
was removed or renamed.

## Review Criteria

The review considered first-use ergonomics, repeated rendering, asyncio,
text/HTML symmetry, multi-source execution, compatibility versus Python-native
behavior, capability isolation, typing, discoverability, and the cost of future
evolution.

## Stable Layers

| Layer | Canonical API | Decision |
| --- | --- | --- |
| One-shot text | `render*` | Keep at package root; explicit options are readable and type-checkable. |
| One-shot HTML | `render_html*` | Keep at package root with signatures matching text helpers. |
| Reusable templates | `Template`, `HTMLTemplate` | Primary API for compile-once use; immutable association methods remain explicit. |
| Multi-source batch | `TemplateEngine` | Keep at package root; prefer `from_sources()` for application construction. |
| Safety | `SandboxPolicy`, `ExecutionBudget` | Keep explicit and immutable; never infer a sandbox from HTML mode. |
| Ecosystem functions | `gotpl.funcs.*` | Keep opt-in and outside the default function namespace. |
| Python extensions | `PythonExtensions` | Keep separately opt-in; Python semantics never replace Go defaults. |
| Compatibility values | root exports | Retain for discoverability where Python lacks the needed Go metadata. |
| Parser, compiler, VM, `_compat` | internal modules | Exclude from the stability promise. |

## Findings

### Resolved

- `render_html`, `render_html_to`, `render_html_async`, and
  `render_html_async_to` previously accepted `**options: object`. Runtime
  behavior worked, but IDE completion, strict typing, introspection, and
  generated documentation could not discover valid options. Their signatures
  now exactly mirror the corresponding text helpers, and a public contract test
  prevents regression.
- User documentation previously mixed onboarding, maintainer contracts,
  milestone history, and performance evidence in one flat list. The MkDocs
  navigation now starts from user tasks and places maintainer material in a
  separate section.
- Examples used both the root `TemplateEngine` export and its implementation
  module. User documentation now uses `from gotpl import TemplateEngine` as the
  canonical import.
- `gotpl.parse`, `gotpl.compile`, and `gotpl.runtime` advertised internal
  implementation objects through wildcard imports even though the stability
  contract excludes those modules. Their existing explicit attributes remain
  importable for internal compatibility, but their empty `__all__` no longer
  presents them as stable public surfaces.
- The `goduration` and `gotime` distribution roots exposed `__version__` as an
  attribute but omitted it from wildcard exports. Both now follow the same
  version-export policy as `gotpl`, with direct contract tests.
- The public typed Sprout inventory had no schema discriminator. Its generator,
  report, packaged resource, loader, and tests now agree on schema version 1
  and reject an unsupported version.
- Compiled templates had no immutable way to extend or replace their callback
  registry. `Template`, `HTMLTemplate`, and `TemplateEngine` now expose
  `with_functions()`: text programs and namespaces are reused, HTML context is
  reanalyzed, and extension collisions and sandbox allowlists remain enforced.

### Accepted without change

- Construction uses explicit keyword options instead of a shared mutable
  configuration object. This keeps one-shot and reusable APIs easy to read and
  makes semantic selection immutable.
- Async methods have an `_async` suffix rather than returning an optionally
  awaitable result. The sync path therefore remains free of an event loop and
  raises `AsyncRequiredError` when required.
- File discovery is application-owned. `from_sources()` accepts a mapping and
  avoids coupling the core API to filesystem or framework policy.
- Function names referenced by the original source still need to be registered
  before its first compilation. A derived registry can replace functions used
  by existing programs and can add names for subsequently compiled sources.
- Go-compatible formatting remains the default. Python formatting requires
  `format_mode="python"`; it is never a mutable global switch.
- Function libraries remain constructors that return mappings. A universal
  implicit registry would obscure collisions, capabilities, and compatibility
  profiles.
- `goduration` and `gotime` retain explicit Go and Python surfaces. Top-level
  imports keep the Go-compatible default required by gotpl.

## Deferred Candidates

- A richer high-level loader may be considered only after real applications
  demonstrate repeated filesystem or package-resource boilerplate. It must be
  built over `from_sources()` and must not make the core engine mutable.
- Additional Python-native helpers require concrete user demand and remain
  isolated under `gotpl.pythonic`.
- Public parser or instruction APIs remain deferred until a third-party tool
  has a stable use case that cannot be served by documented rendering APIs.

## Evidence

- `tests/unit/test_public_api_contract.py` freezes root exports, exception
  relationships, reusable method surfaces, function-library exports, and
  text/HTML convenience option parity. Standalone package tests also freeze
  their root version exports.
- Strict Pyright validates source and isolated wheel consumers.
- `mkdocs build --strict` resolves the user guide and generated reference
  against the current source tree.
