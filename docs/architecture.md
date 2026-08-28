# Architecture

## Status

This document defines the current 1.0 architecture. It should change through
explicit, reviewed decisions rather than incidental implementation pressure.

## Runtime Pipeline

```text
template source
    -> lexer
    -> parser
    -> semantic analysis
    -> immutable AST
    -> compiler
    -> immutable instruction stream
    -> link immutable sync sidecar from fixed registry and policy
    -> linked sync VM or generic async/reference VM
    -> output buffer or writer
```

The AST preserves source positions and language meaning. The generic instruction
stream is the compact compatibility representation shared by both executors.
After the callable registry and HTML context are fixed, templates also derive an
immutable PC-aligned linked sidecar for synchronous writes and lookup-based
control pipelines. It fuses proven-safe field or variable lookup plus unary-call
shapes, decodes static function operands once, and links common dot, field, and
variable arguments, while retaining the generic instruction at the same program
counter for diagnostics and fallback. Execution must not repeatedly parse field
paths, decode literal operands, resolve function names, or reinterpret
control-flow structure.

## Package Boundaries

The intended package layout is:

```text
gotpl/
    environment.py  immutable construction and extension composition
    parse/          tokens, lexer, parser, AST nodes, and semantic validation
    compile/        immutable instructions and instruction generation
    runtime/        value adaptation, sync/async VMs, and multi-source engine
    html/           contextual analysis, safe types, and escapers
    funcs/
        sprig/      versioned Sprig-compatible functions
        slim_sprig/ reduced fork profile
        sprout/     opt-in Sprout registries and groups
        helm/       reusable opt-in Helm-compatible functions
    pythonic/       opt-in Python-native categories and immutable registry
    _compat/        private formatting and RE2-compatible support
```

Dependencies flow downward from public APIs to these components. `parse` and
the text runtime must not depend on `html`, compatibility function libraries,
or `pythonic`.

### Ownership and enforced imports

The module owner, not a convenient re-export, determines the permitted
dependency direction:

| Owner | Responsibility | May import from gotpl |
| --- | --- | --- |
| `errors` | Public exception taxonomy | nothing |
| `_compat` | Private formatting and RE2-compatible engines | `_compat` |
| `pythonic` | Explicit Python-native extension registries | `pythonic` |
| `parse` | Tokens, lexing, syntax trees, parsing, semantic validation | `errors`, `parse` |
| `compile` | Immutable IR and AST-to-IR compilation | `parse`, `compile` |
| `runtime` | Value adaptation, prepared calls, results, sync VM, async VM | `_compat`, `compile`, `errors`, `runtime` |
| `runtime.engine` | Public multi-source and per-file-context execution | `pythonic`, `runtime`, `template` |
| `environment` | Immutable construction policy and extension composition | `html`, `pythonic`, `runtime`, `template` |
| `template` | Public text-template orchestration | `parse`, `compile`, `runtime`, `errors`, `pythonic` |
| `html` | Safe content, contextual analysis/rewriting, escapers, HTML API | `compile`, `runtime`, `template`, `errors`, `html`, `pythonic` |
| `funcs.sprig` | Sprig coercion, names, error adapters, registry | `_compat`, `runtime`, `funcs.sprig` |
| `funcs.slim_sprig` | Slim-Sprig profile and fork-specific differences | `funcs.sprig`, `funcs.slim_sprig` |
| `funcs.sprout` | Opt-in Sprout registries, groups, and adapters | `_compat`, `runtime`, `funcs.sprig`, `funcs.sprout` |
| `funcs.helm` | Reusable Helm-compatible function-map and late-bound runtime | `environment`, `errors`, `runtime`, `runtime.engine`, `funcs.sprig`, `funcs.helm` |
| package root | Stable public re-exports | `environment`, `template`, `html`, `runtime`, `errors`, `pythonic` |

Formatting and regular-expression compatibility live under private `_compat`
because neither incomplete surface is an independent product. Only `runtime`,
`funcs.sprig`, and `funcs.sprout` may import those internals. Sprig and Sprout
may import the public `goduration` and `gotime` leaf packages. This keeps
parsing, compilation, public orchestration, and HTML analysis independent of
function-library and compatibility details they do not own.

`tests/architecture/test_import_layers.py` parses imports with the standard
library AST, checks these rules, verifies each workspace member's declared
dependencies, and rejects workspace dependency cycles. New import directions
must update this document and the executable policy in the same change.

## Template Model

A compiled template owns an immutable template namespace, function slots,
options, source metadata, generic instructions, and a linked sync sidecar.
Rendering creates an execution context containing dot, root, variables, call
frames, and output state. The sidecar namespace contains definitions without a
self-reference; the executor carries the association root separately for root
recursion.

`Template.from_sources()` is the core boundary for assembling named files into
one namespace. The package-root `gotpl.TemplateEngine` adds ordered batch
execution with an independent context for each source. `with_source()` derives a new
immutable namespace, while
`render_source()` and `render_source_async()` compile and execute dynamic source
against inherited definitions. Per-file data remains an execution input to
`render_template()` rather than state stored in a compiled template. Helm,
gomplate-like integrations, and other multi-file runtimes must build on these
core primitives instead of maintaining another parser or template namespace.

`Environment` is an immutable construction factory over these same APIs. It
composes explicit functions and runtime extensions, but owns neither sources nor
a loader or mutable cache. `from_string()` constructs one reusable template;
`from_sources()` constructs a `TemplateEngine`. HTML construction remains
explicit through `from_html_string()` and `from_html_sources()`.

Construction and parsing may be mutable. Once exposed for execution, a compiled
template must be safe to share between threads and asyncio tasks.

## Sync and Async Execution

The sync and async VMs retain the same generic instructions and semantic helpers
where those helpers do not add coroutine overhead. The sync VM may consume a
PC-aligned linked write or lookup-control shape when linking proved its static
arity and runtime type-check requirements equivalent. Linked `ITERATE` preserves
the generic range binder by evaluating with `bind=False`; linked conditional and
`with` pipelines retain declaration binding. Logical short circuiting, dynamic
methods, unsupported shapes, and sparse named-template associations fall back
to the generic evaluator. Programs without a linkable control shape store no
control sidecar tuple. The async VM remains generic so awaiting semantics stay
at explicit async boundaries.

The sync VM never starts or manages an event loop. If a registered function
returns an awaitable, rendering fails with `AsyncRequiredError`.

The async VM accepts both ordinary and awaitable results. It checks at function
call boundaries and awaits results before the pipeline continues. Cancellation
must propagate and must not be converted into a template execution error.

Named-template calls use a lazily allocated caller stack in both VMs. Ordinary
templates pay no frame-stack allocation, while nested calls avoid Python
recursion and enforce Go's non-wasm 100,000-template depth limit. Each callee
receives a fresh execution context and root variable; caller variables are not
dynamically inherited.

Async iterables are outside the initial async-function milestone unless added by
an explicit compatibility decision.

## Value Adaptation

Go reflection behavior cannot be mapped mechanically onto Python. All access
must go through a centralized adapter with documented lookup, invocation,
truthiness, comparison, and missing-value rules. The adapter is both a
compatibility boundary and a performance specialization point.

Private and magic Python attributes must not become reachable accidentally.

## HTML Templates

HTML rendering reuses the text parser and instruction model. Before execution,
a contextual analyzer propagates HTML, attribute, URL, CSS, JavaScript, and
related states through the template graph. It rewrites output operations to use
the required contextual escaper.

Escaping the final rendered string is not a valid implementation.

## Function Registries

Every template starts with Go template built-ins. The caller supplies one
explicit `functions=` mapping, which may come from a Sprig, Slim-Sprig, Sprout,
or Helm constructor and may be composed with application functions before
template construction. `PythonExtensions` supplies a separate opt-in mapping;
construction rejects collisions between it and `functions=`.

Collision and registration timing must follow the compatibility contract.
Compatibility and Python-native functions must remain distinguishable for
versioning and auditing.

Sandbox policy and Python extensions are immutable construction inputs.
`Template`, `HTMLTemplate`, and `TemplateEngine` carry them into
the sync or async VM; template source cannot modify them. Budget state is
created per render and shared by frames in one associated-template execution.
Workspace compatibility packages remain below this layer and never import the
policy, VM, or extension registry.

Functions that execute against the current association use an explicit
`ContextFunction`. The VM injects a read-only `RenderContext` or
`AsyncRenderContext` backed by a private per-render session. Sessions own nested
render depth, shared budget counters, bounded dynamic-source caching, and
extension-local state. Ordinary callables retain the non-session path.

Helm's `include` and `tpl` use this generic mechanism through `HelmExtension`.
`HelmTemplateEngine` remains a convenience facade rather than owning a second
context-local runtime. Compiled associations remain reusable across threads and
asyncio tasks; no mutable render state is stored on them.

Slim-Sprig is exposed as a named subset of the Sprig registry rather than a
second implementation. Sprout has its own registry namespace because its names,
aliases, notices, and grouped loading behavior have diverged from Sprig.
`gotpl.funcs.helm` provides only the reusable function-map compatibility layer.
Context-aware integration lives in `gotpl.exts.helm`, which provides
`HelmExtension` and the `HelmTemplateEngine` facade. Neither package owns a
chart model, loader, repository client, or cluster client. The miniature runtime
under `examples/helm_runtime` supplies chart globals and collection on top of
that engine. Helm names never enter the Go built-in or Sprig maps.

Optional integrations must be importable without their third-party extras.
Functions that require an unavailable extra fail when that capability is
explicitly selected or called, with an actionable installation message.
Optional packages are loaded lazily so importing the core parser and renderer
does not require extras.

## Performance Evolution

The generic instruction VM is the compatibility reference inside Python. The
sync linked sidecar is a derived optimization, not another semantic backend: it
preserves each generic `Program`, source position, value adapter, error
translation, budget accounting, and generic fallback. An association-level cost
model disables sidecar frame tracking when linked writes do not outnumber named
template calls.

M6 did not retain a Python-AST or native backend under the measured opportunity
and end-to-end gates. The later linked-IR pass is closed after retaining only
the measured sidecar and contextual URL table changes. M12 may reconsider a
generated synchronous backend as a separately acceptance-gated milestone; it
must derive code from validated internal nodes, retain template source mapping,
and pass full backend parity tests. No M12 implementation is active in the M10
release scope.

## Potential Library Extraction

Independently useful Go-compatibility primitives first move into buildable
workspace distributions under `packages/` after their contracts stabilize.
Candidates, dependency direction, and extraction gates are tracked in
`docs/extraction-candidates.md`. The `gotpl` package remains the integration and
differential-test host. Moving a distribution to another repository is a later
decision and must not weaken compatibility or coordinated testing.

`goduration` and `gotime` are extracted workspace distributions. The narrow
formatting and RE2-compatible engines were returned to private `gotpl._compat`
modules before the 1.0 freeze because they have no independent product or
comprehensive API roadmap. `gotime` may depend on `goduration`; neither may
depend on gotpl's AST, compiler, VM, sentinels, or function registries.

## M7 Workspace Framework

M7 established the repository as a coordinated uv workspace before Sprout and
Helm integration. Each retained extracted distribution owns independent PEP 621
metadata, a `src` layout, a `py.typed` marker, public API documentation, direct
tests, performance fixtures, and wheel-install verification. The root lock file
coordinates development without turning the packages into one distribution.

The current dependency direction is:

```text
goduration <- gotime

goduration ----\
gotime -----------> gotpl
```

The workspace packages expose the independently useful time and duration
values. Private formatting and regex code expands only for concrete,
oracle-backed template ecosystem requirements; completeness against the entire
Go `fmt` or `regexp` package is not an architecture goal. gotpl retains
template-specific coercion, sentinels, error translation, registry names, HTML
contexts, execution policy, Sprout registries, and Helm function additions.
The concrete Helm runtime remains an example. External ecosystem extensions
consume public APIs and must not import `_compat`.

## Dual Semantic Surfaces

Every retained extracted compatibility distribution exposes explicit `go` and
`python` surfaces. The Go surface reproduces Go time and duration behavior. The
Python surface borrows useful API concepts while following Python-native
integers, floats, Decimal values, standard-library objects, protocols, and
exceptions. Private `_compat` modules are not subject to this public dual-surface
product rule.

Top-level convenience exports default to the Go surface. gotpl's default
registries import the Go surface explicitly; opt-in Python rendering and helper
profiles import the Python surface explicitly. A global mutable mode is not
allowed. Surface selection is part of imports or immutable template
construction and therefore remains safe for concurrent threads and asyncio
tasks.

Implementation code may share parsing tokens, immutable data, or algorithms
only when the observable policies remain separate. Cross-surface conversion is
explicit and tested for overflow and precision loss.

Inside gotpl, module cleanup follows ownership rather than file size. Go
built-in registration, compile-time metadata, per-render state, value
adaptation, contextual analysis, escapers, and sync/async dispatch must remain
separately auditable. Refactoring must not introduce an extra function boundary
on a measured hot path merely to shorten a module.

The instruction representation will reserve explicit specialization points for
common operands, exact mappings, prepared callable slots, formatting shapes,
and HTML contexts. A specialization becomes production behavior only after VM
parity, source-attribution, security, and representative end-to-end benchmark
gates pass.
