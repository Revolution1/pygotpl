# Unified Environment and Runtime Extension Design

## Status

The initial public design is implemented. `Environment`, `ContextFunction`,
sync and async render contexts, `Extension`, generic per-render sessions,
and `HelmExtension` are public. Consolidating duplicated orchestration data into
a private `CompiledAssociation` remains a later internal refactor.

## Decision Summary

Add three generic concepts to the core library:

1. An immutable `Environment` that owns reusable construction policy.
2. A `ContextFunction` descriptor for functions that need a read-only sync or
   async render context supplied by the VM.
3. An internal per-render session that owns budgets, nested rendering, bounded
   dynamic-source caches, and extension-local state.

`Template.from_sources()` remains the deterministic association primitive.
`TemplateEngine` becomes the convenient multi-source facade created by an
environment. File discovery, chart loading, dependency resolution, and cluster
access remain application responsibilities.

Helm then becomes an ordinary opt-in extension built from these concepts.
`include` renders an associated name through `RenderContext`, and `tpl` renders
a dynamic source through the same context. The current Helm-specific
`ContextVar` runtime becomes a compatibility facade and can eventually be
deprecated after the generic path is proven.

## Why the Earlier Decision Changes

The M10 API review intentionally rejected a mutable Jinja-style environment
because `Template.from_sources()`, `with_source()`, and `TemplateEngine` already
covered immutable multi-file association and batch rendering. At that point no
real application needed a loader or shared runtime object.

The Helm integration adds a different requirement. `include` and `tpl` are not
source loaders and are not ordinary functions: they must execute against the
currently active association, reuse the current policy, preserve sync/async
semantics, and isolate mutable state to one render. Implementing that lifecycle
inside a Helm-only runtime solves Helm but leaves every similar integration to
copy it.

This design addresses that demonstrated runtime requirement without adding an
implicit filesystem loader or mutable global configuration.

## Reference Models

The design borrows narrowly from established template APIs:

- Go `text/template` treats associated templates as a namespace, requires
  functions needed by parsing to be registered before parsing, and permits a
  parsed template to execute concurrently. These properties remain the
  compatibility baseline. See the official
  [`text/template` documentation](https://pkg.go.dev/text/template).
- Jinja centralizes configuration in an environment and supplies explicit
  context/environment-aware function decorators. Its documentation also warns
  that changing globals after templates are loaded leads to surprising
  behavior. gotpl adopts explicit contextual calls but not mutable shared
  globals. See the official
  [Jinja API documentation](https://jinja.palletsprojects.com/en/stable/api/).
- MiniJinja passes a read-only execution `State` to functions that request it.
  This supports an explicit VM injection model rather than ambient thread-local
  lookup. See its
  [`Environment`](https://docs.rs/minijinja/latest/minijinja/struct.Environment.html)
  and
  [`Function`](https://docs.rs/minijinja/latest/minijinja/functions/trait.Function.html)
  APIs.

## Current Responsibilities

| Current API | Responsibility | Limitation exposed by Helm |
| --- | --- | --- |
| `Template` | One immutable compiled text association | Registered functions cannot access the active association. |
| `HTMLTemplate` | One immutable contextually analyzed HTML association | Dynamic rendering must not bypass contextual analysis. |
| `TemplateEngine` | Immutable text association plus ordered batch rendering | It does not own a render session or contextual calls. |
| `PythonExtensions` | Immutable opt-in Python function mapping | It cannot describe lifecycle, capabilities, or contextual injection. |
| Function maps | Explicit compatibility function selection | Plain callables cannot request controlled VM services. |
| `SandboxPolicy` | Immutable access and function policy | It sees names, but not extension capabilities. |
| `ExecutionBudget` | Immutable limits with per-render counters | Nested public render calls currently create unrelated counters. |
| `HelmTemplateEngine` | Helm-specific late-bound execution | It duplicates a generally useful lifecycle using `ContextVar`. |

## Design Principles

- Construction configuration is immutable and safe to reuse.
- Every mutable counter, cache, stack, and extension state belongs to one
  top-level render.
- Runtime context is injected explicitly at the VM call boundary. It is not
  discovered through a process-global or object-owned `ContextVar`.
- Ordinary callables remain the common, zero-extra-semantics path.
- The synchronous VM never creates or drives an event loop.
- Text and HTML modes remain explicit types. A runtime extension cannot turn a
  text template into an HTML template or bypass contextual analysis.
- Compatibility libraries remain explicit opt-in registries. An environment is
  not a universal implicit registry.
- `from_sources()` consumes complete named source mappings. File, package,
  chart, glob, network, and repository discovery remain outside the core.
- Extensions may add functions and per-render behavior, but not parser syntax,
  AST rewrites, VM instructions, mutable policy, or unrestricted VM access.

## Proposed Public API

### Environment

```python
from gotpl import Environment
from gotpl.funcs import sprig
from gotpl.exts.helm import HelmExtension

environment = Environment(
    functions=sprig.text_func_map(),
    extensions=(HelmExtension(lint_mode=False),),
    missing_key="zero",
)

template = environment.from_string("Hello {{ .name }}")
engine = environment.from_sources(
    {
        "deployment.yaml": '{{ include "labels" . }}',
        "_helpers.tpl": '{{ define "labels" }}app: {{ .name }}{{ end }}',
    }
)

result = engine.render_template("deployment.yaml", {"name": "demo"})
```

Target shape:

```python
@dataclass(frozen=True, slots=True)
class Environment:
    functions: Mapping[str, TemplateFunction]
    extensions: tuple[Extension, ...]
    delimiters: tuple[str, str]
    missing_key: MissingKeyMode
    format_mode: FormatMode
    sandbox: SandboxPolicy | None
    budget: ExecutionBudget | None

    def from_string(self, source: str, *, name: str = "template") -> Template: ...
    def from_sources(self, sources: Mapping[str, str]) -> TemplateEngine: ...
    def from_html_string(
        self, source: str, *, name: str = "template"
    ) -> HTMLTemplate: ...
    def from_html_sources(self, sources: Mapping[str, str]) -> HTMLTemplate: ...

    def with_functions(
        self,
        functions: Mapping[str, TemplateFunction],
        *,
        replace: bool = False,
    ) -> Self: ...
    def with_extensions(self, *extensions: Extension) -> Self: ...
```

The environment is a frozen factory, not a template cache or template owner.
All `with_*` operations derive a new value. Existing constructors remain valid
and can internally delegate to a default environment, so this is additive.

`from_sources()` returns `TemplateEngine` because a multi-source caller commonly
needs both named rendering and batch rendering. The engine should gain direct
single-name and dynamic-source methods that delegate to its owned `Template`:

```python
engine.render_template(name, data)
engine.render_template_async(name, data)
engine.render_source(source, data, name="template")
engine.render_source_async(source, data, name="template")
```

This removes the current need for callers to reach through `engine.template`
without inventing a second association type.

`from_html_sources()` initially returns `HTMLTemplate`, whose existing named
render methods already cover the important association use case. A separate
HTML batch facade should be added only when an application demonstrates that
batch operation, rather than generalizing `TemplateEngine` over two execution
types prematurely.

### Context Functions

Ordinary functions continue to be registered as plain callables. A function
that needs the active render lifecycle opts into an explicit descriptor:

```python
from gotpl import AsyncRenderContext, ContextFunction, RenderContext


def include(context: RenderContext, name: str, data: object) -> str:
    return context.render_template(name, data)


async def include_async(context: AsyncRenderContext, name: str, data: object) -> str:
    return await context.render_template(name, data)


include_function = ContextFunction(
    sync=include,
    async_=include_async,
    capabilities=frozenset({"render-associated"}),
)
```

Target shape:

```python
@dataclass(frozen=True, slots=True)
class ContextFunction:
    sync: Callable[..., object] | None = None
    async_: Callable[..., Awaitable[object]] | None = None
    capabilities: frozenset[str] = frozenset()


TemplateFunction: TypeAlias = Callable[..., object] | ContextFunction
```

At least one implementation is required. The injected context parameter is
excluded from template-visible arity and annotation checks. Function
preparation validates the remaining signature once during construction and,
when both implementations exist, rejects incompatible visible signatures.

The descriptor has separate sync and async implementations. It must not return
either a string or awaitable depending on a hidden execution flag. The async VM
uses `async_` when present and otherwise calls `sync`, then applies its existing
awaitable handling. The sync VM calls `sync`; if it is absent, or returns an
unexpected awaitable, the VM raises `AsyncRequiredError`.

### Render Context

The sync and async facades intentionally expose different nested-render
operations. This prevents an async extension from accidentally performing a
blocking sync render and prevents a sync extension from receiving an awaitable:

```python
class RenderContext(Protocol):
    @property
    def root(self) -> object: ...

    @property
    def dot(self) -> object: ...

    @property
    def template_name(self) -> str: ...

    @property
    def source_name(self) -> str: ...

    def render_template(
        self,
        name: str,
        data: object = None,
    ) -> str: ...

    def render_source(
        self,
        source: str,
        data: object = None,
        *,
        name: str = "dynamic",
    ) -> str: ...

    def state(self, key: object, factory: Callable[[], T]) -> T: ...


class AsyncRenderContext(Protocol):
    @property
    def root(self) -> object: ...

    @property
    def dot(self) -> object: ...

    @property
    def template_name(self) -> str: ...

    @property
    def source_name(self) -> str: ...

    async def render_template(
        self,
        name: str,
        data: object = None,
    ) -> str: ...

    async def render_source(
        self,
        source: str,
        data: object = None,
        *,
        name: str = "dynamic",
    ) -> str: ...

    def state(self, key: object, factory: Callable[[], T]) -> T: ...
```

The public context deliberately does not expose instruction pointers, mutable
variable scopes, frame stacks, function dictionaries, policy mutation, raw
writers, or parser/compiler objects.

`root` and `dot` are observable values, not writable VM slots. Nested renders
use the explicitly supplied `data`; they do not inherit caller lexical
variables, matching associated-template semantics. The two facades share
metadata and state-key behavior but not rendering method implementations.

### Extensions

An extension is an immutable provider of function descriptors and optional
per-render state:

```python
class Extension(Protocol):
    @property
    def functions(self) -> Mapping[str, TemplateFunction]: ...

    @property
    def template_kinds(self) -> frozenset[Literal["text", "html"]]: ...
```

The initial implementation keeps this protocol intentionally small.
Lifecycle hooks such as `before_render` and `after_render` are not included:
they introduce ordering, partial-output, cancellation, and exception semantics
without a demonstrated requirement. A state factory plus contextual functions
is sufficient for Helm.

`PythonExtensions` can remain source-compatible and gain an adapter to this
protocol. Sprig, Slim-Sprig, and current Sprout registries should remain plain
function maps because they do not need render state. They must not be silently
converted into globally enabled extensions.

## Internal Execution Model

The orchestration layer should first consolidate the duplicated immutable
association data behind a private value:

```text
Environment
    |
    | compile complete sources + fixed registry/policy
    v
CompiledAssociation (immutable)
    |- kind: text | html
    |- root program and complete namespace
    |- prepared function slots and linked sync sidecar
    |- delimiters, missing-key, format, sandbox, budget
    |- dynamic-source derivation callback
    v
Template / HTMLTemplate / TemplateEngine (public facades)
    |
    | one top-level render
    v
RenderSession (private, mutable, never shared)
    |- shared ExecutionBudgetState
    |- associated-template and dynamic-source call stack
    |- bounded dynamic-source cache
    |- extension state keyed by opaque object identity
    |- current immutable association
    v
VM ExecutionContext (private frame-local state)
    |- root, dot, lexical scopes and ranges
    |- location
    `- reference to RenderSession
```

The VM already centralizes registered function invocation in sync and async
helpers. Those call boundaries are the injection point. Linked calls must carry
the same prepared descriptor metadata as generic calls so the optimization
cannot change contextual behavior.

Named template instructions continue using their iterative frame machinery.
Context-driven nested renders enter the same session through the association,
which preserves budgets, recursion accounting, error attribution, and dynamic
cache identity across a call that crosses the public orchestration boundary.

## Session and Cache Semantics

- A fresh session is created for every public top-level `render*` operation.
- A batch `TemplateEngine.render()` creates an independent session for each
  requested source because each source is documented as an independent render.
- Nested `RenderContext` calls share their parent's session.
- The dynamic-source cache is bounded per session. Its key includes the current
  immutable association identity, template kind, source, source name,
  delimiters, registry identity, and contextual-analysis mode.
- A dynamic source is derived from the current association, so definitions
  created by an outer dynamic source are visible while it executes but never
  leak into the reusable parent or a later render.
- Extension state is obtained by an opaque identity key, not a public string,
  preventing unrelated extensions from aliasing each other's mutable state.
- Shared compiled objects contain no session state and remain reusable across
  threads and asyncio tasks without context-local ambient storage.

## Budget and Capture Semantics

Nested context rendering must share function-call, range-item, and active
template-depth counters with the parent. Starting a fresh public render from a
context function would incorrectly reset those limits.

Captured nested text is intermediate data rather than externally emitted
output. It is therefore not charged while captured; the parent writer charges
it once if it is eventually emitted. Function-call, iteration, and depth
counters remain shared while the nested render executes. This avoids provenance
markers that arbitrary string-transforming functions could accidentally erase.

## HTML Safety

Runtime source rendering is not automatically safe for HTML.

- An extension declares whether it supports text, HTML, or both.
- `render_source` in an HTML session parses and contextually analyzes the
  derived complete association before execution.
- Captured nested output returns through the caller's normal contextual output
  instruction. Extensions cannot manufacture a trusted `HTML`, `JS`, `URL`, or
  other safe type through the context API.
- Helm's initial extension is text-only because Helm renders YAML/text and its
  behavior has not been specified against Go `html/template`.

These rules prevent `tpl`-like features from becoming an escaping bypass.

## Function Composition and Policy

Composition follows explicit, deterministic rules:

1. Go built-ins remain owned by the core runtime.
2. The caller's `functions=` mapping and extension function maps are combined
   during immutable environment construction.
3. Duplicate names fail by default, including extension-to-extension
   collisions. `with_functions(..., replace=True)` is the only generic public
   override path.
4. Compatibility registries may retain their documented intentional built-in
   override, such as Sprig's `slice`; the generic extension mechanism does not
   broaden that exception.
5. Sandbox validation sees both the visible function name and the contextual
   capabilities declared by its descriptor. `SandboxPolicy` gains an immutable
   `allow_context_capabilities` set, empty by default. A policy may allow a name
   while denying `render-dynamic-source`, `render-associated`, network,
   environment, DNS, or cluster capabilities.
6. Template source cannot add functions, extensions, or capabilities.

Capability strings are descriptive policy inputs, not authority by themselves.
The context facade exposes only services permitted by the fixed association
policy, and extensions still require explicit caller-provided clients for
network or cluster operations.

## Helm as a Generic Extension

The target Helm layer becomes approximately:

```python
@dataclass(frozen=True, slots=True)
class HelmExtension:
    lint_mode: bool = False
    enable_dns: bool = False
    lookup: LookupFunction | None = None
    custom_functions: Mapping[str, TemplateFunction] = field(...)

    template_kinds = frozenset({"text"})
    functions = {
        "include": ContextFunction(..., capabilities={"render-associated"}),
        "tpl": ContextFunction(..., capabilities={"render-dynamic-source"}),
        # required/fail and the remaining Helm/Sprig functions
    }
```

The Helm example remains responsible for:

- reading an unpacked chart and dependency directories;
- merging values and creating `.Chart`, `.Release`, `.Capabilities`, `.Files`,
  and `.Template` objects;
- selecting templates, processing hooks/CRDs/NOTES, and producing manifests;
- invoking external Helm CLI operations such as dependency download.

The core extension is responsible only for template-runtime behavior. It does
not acquire a chart loader, repository client, Kubernetes client, or implicit
filesystem access.

## Migration and Compatibility

Implementation should be additive and staged:

1. Add private `RenderSession` while preserving all current constructor and
   rendering results.
2. Add public `ContextFunction`, `RenderContext`, and `AsyncRenderContext`;
   cover generic and linked sync paths plus async parity before exposing an
   ecosystem extension.
3. Add immutable `Environment` and make existing constructors delegate to the
   same construction implementation. Existing signatures remain supported.
4. Reimplement Helm late-bound functions as a `HelmExtension`, retaining
   `HelmTemplateEngine` as a thin source-compatible facade.
5. Consider a private `CompiledAssociation` consolidation after profiling; it
   is not required by the public API.
6. Deprecate the facade only after at least one release cycle and only if the
   environment form is demonstrably simpler for Helm users.

No existing `Template`, `HTMLTemplate`, `TemplateEngine`, function-map, or
`PythonExtensions` call needs to change in the first release of this API.

## Required Evidence

Before the proposal becomes public behavior, tests must cover:

- construction-time rejection of collisions and invalid contextual signatures;
- ordinary callable performance and behavior unchanged;
- contextual function arity excludes the injected context;
- sync, async, generic VM, and linked sync parity;
- sync rejection of unexpected awaitables and async cancellation propagation;
- associated and dynamic nested renders with correct source locations;
- shared recursion, iteration, function-call, and output budgets;
- captured output charged exactly once;
- bounded dynamic cache isolation across renders, threads, and asyncio tasks;
- extension-state isolation and cleanup after success, failure, and cancellation;
- sandbox denial by function name and contextual capability;
- HTML dynamic-source contextual reanalysis and injection regressions;
- Helm oracle parity for `include`, `tpl`, `required`, and `fail`;
- representative complex-chart correctness and cold/warm performance.

Performance measurement must report construction, cold render, reusable warm
render, nested associated render, dynamic-source cache hit/miss, and memory
separately. A contextual descriptor check must not add a material regression to
ordinary function calls; any retained hot-path change follows the repository's
paired A/B and 5% alert policy.

## Rejected Alternatives

### Keep the Helm-specific `ContextVar` runtime

It works for Helm but makes every integration recreate sync/async dispatch,
recursion, caching, budget propagation, and error attribution. Ambient lookup
also hides a dependency that the VM already knows explicitly.

### Mutable Jinja-style global environment

It creates registration-timing, cache invalidation, concurrency, and sandbox
ambiguity. Immutable derivation provides the useful construction ergonomics
without changing already compiled templates.

### Put a filesystem loader in `Environment`

Runtime extensions do not require source discovery. A loader would couple the
core to path ordering, package resources, watching, reload, cache invalidation,
and trust policy. Applications can continue to construct an explicit mapping
and call `from_sources()`.

### Expose the private VM execution context

It would freeze scopes, instruction representation, writers, and optimization
details as public API and allow extensions to violate Go semantics. The public
facade exposes only stable values and controlled nested-render operations.

### Infer contextual functions from a parameter name or annotation

Implicit inspection is fragile, makes wrappers and decorators surprising, and
can accidentally grant runtime authority. `ContextFunction` is an explicit,
auditable capability boundary.

### General parser or AST extension hooks

Helm does not require new syntax. Syntax hooks would weaken compatibility and
couple external code to pre-1.0 internals. They remain outside this extension
model.

## Recommendation

The retained first implementation contains
`ContextFunction`, read-only sync/async render contexts, private
`RenderSession`, and immutable `Environment`. Use Helm as the acceptance
workload, but keep every new type and lifecycle name ecosystem-neutral. Do not
add loaders, general hooks, or a generic mutable registry in the same change.

## Implementation Evidence

The implementation passed direct public API, sync/async context,
associated/dynamic rendering, HTML reanalysis, sandbox capability, shared
budget, thread/task reuse, Helm compatibility, architecture, and type tests.

Profiling exposed duplicate preparation of Helm's large registry across
`Environment` and `Template`. Reusing an already prepared immutable registry
reduced the sampled static Helm cold-render median from 0.692 ms to 0.497 ms
and dynamic `tpl` cold-render median from 0.745 ms to 0.559 ms. Median traced
peak memory fell from 86,449 bytes to 72,929 bytes. The before and after runs
used seven timing samples of 500 iterations and ten memory samples on Apple
arm64 with CPython 3.14.7.

The post-change paired linked/reference benchmark verified identical output on
text control flow, contextual HTML, Sprig-heavy functions, and a 33-template
association. Linked medians were 29.32%, 31.91%, and 11.56% faster on the first
three workloads; the named association was within 0.26% of the generic VM.
