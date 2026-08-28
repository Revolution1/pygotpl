# Implementation Complexity Decisions

## Purpose

This register records cases where full upstream reproduction has unusually high
implementation complexity, runtime cost, security exposure, or maintenance
cost. It prevents silent simplification and distinguishes an internal design
shortcut from an observable compatibility difference.

Milestone documents remain authoritative for required outcomes. A decision in
this register cannot mark a milestone gate complete, weaken the default Go or
Sprig contract, or turn an unimplemented function into an advertised feature.

## Decision Process

Before simplifying or deferring behavior:

1. Identify the pinned upstream implementation and tests.
2. Describe the observable behavior and affected compatibility profile.
3. Measure implementation or runtime cost when performance is part of the
   concern.
4. Consider a compatible implementation with a simpler internal design.
5. Record whether the result is implemented, simplified without an observable
   difference, explicitly unsupported, or deferred to a named milestone.
6. Add tests that make the chosen boundary visible and update the compatibility
   documentation when users can observe a difference.

Security-sensitive behavior is not enabled merely to satisfy a name inventory.
Performance-sensitive behavior is not replaced by an incompatible shortcut.
During an active milestone, incomplete work is tracked as incomplete rather
than prematurely recorded as a permanent simplification.

## Decision Register

### D001: Narrow gofmt and goregexp boundaries

- Status: superseded by D012
- Milestone: M7, reaffirmed for M8
- Profiles: internal pygotpl support
- Decision: keep both as independently buildable internal-support
  distributions, but implement only the APIs required by concrete pygotpl
  ecosystem compatibility cases. Their Python surfaces remain narrow adapters
  for pygotpl's explicit dual-mode contract, not competing general-purpose
  libraries.
- Reason: Python already has richer general-purpose formatting and regular
  expression facilities; in particular, Python `re` is more expressive than
  Go's RE2-based `regexp`. Completing the unrelated Go `fmt` and `regexp`
  packages, or growing a second Python regex facade, would add substantial
  surface and maintenance cost without a likely standalone user.
- Compatibility effect: none inside the documented pygotpl, Sprig, Sprout, and
  Helm matrices. New required behavior still needs pinned oracle evidence.
- Revisit condition: demonstrated standalone users and a separate product and
  release decision.

### D002: Sprout inventory is not an implementation claim

- Status: accepted
- Milestone: M8
- Profiles: `gotpl.funcs.sprout`
- Decision: publish immutable versioned metadata for every Sprout v1.1.1
  registry, function, alias, notice, and group, but expose a registry function
  map only after its functions have behavioral evidence.
- Reason: the upstream release contains 234 raw registrations, 45 aliases, 251
  names in the `all` group, and 227 names in `hermetic`. Name-only placeholders
  would make parsing succeed and execution fail, producing a misleading
  compatibility claim.
- Compatibility effect: during M8, incomplete registries raised an explicit
  `NotImplementedError`. The completed public registry set now has behavioral
  evidence for every exposed entry; future inventory additions remain hidden
  until equivalent evidence exists.
- Evidence: `docs/reports/sprout-v1.1.1-inventory.json` and
  `scripts/check_sprout_inventory.sh`.

### D003: Reuse requires oracle proof

- Status: accepted
- Milestone: M8
- Profiles: `gotpl.funcs.sprout`
- Decision: Sprout implementations may delegate to public pygotpl Sprig or M7
  workspace APIs only when tests prove the Sprout signature, success result,
  error behavior, and mutation policy. Changed signatures or fixed Sprig bugs
  receive Sprout-specific adapters.
- Reason: many names overlap Sprig while their argument order, error handling,
  or bug-compatible behavior differs.
- Compatibility effect: none; this is an implementation constraint.
- Evidence: dynamic `sprout-registry:*` Go oracle profiles and
  `tests/conformance/test_sprout.py`.

### D004: Specialized Sprout dependencies remain optional

- Status: accepted
- Milestone: M8
- Profiles: `gotpl[crypto]`, `gotpl[yaml]`
- Decision: cryptography, password hashing, and YAML libraries are optional and
  lazily required by the relevant registry functions. The inventory and all
  dependency-free registries remain importable without those extras.
- Reason: these dependencies are specialized and materially heavier than the
  core template runtime.
- Compatibility effect: calling a capability without its extra must produce an
  actionable missing-extra diagnostic. With the extra installed, behavior must
  pass the pinned oracle matrix.
- Revisit condition: dependency weight or Python standard-library capability
  changes materially.

### D005: Preserve eager cidrRangeList only on compatibility profiles

- Status: accepted
- Milestone: M8, with enforcement in M9
- Profiles: Sprout `network`, `all`, and `hermetic`
- Decision: the ordinary Sprout compatibility profiles preserve v1.1.1's eager
  `cidrRangeList` result without an undocumented address-count cap. The function
  is classified as a resource-amplifying capability. M9's opt-in strict sandbox
  must deny it by default or require an explicit address-work budget before it
  can run.
- Reason: the upstream function allocates one result for every address, making
  both time and memory `O(2^(address_bits-prefix_bits))`; even an IPv4 `/0` is
  not practically renderable. Adding a silent default cap would make the main
  compatibility profile disagree with Sprout, while unconditional availability
  in an untrusted profile would permit trivial denial of service.
- Performance effect: no hot-path cost unless the function is invoked. Small
  ranges retain direct eager-list behavior; large ranges intentionally inherit
  the upstream resource cost outside the strict sandbox.
- Compatibility effect: none in ordinary profiles. The strict sandbox is an
  explicit Python policy and will report its denial or budget failure.
- Evidence: pinned Sprout `registry/network/functions.go`, the M8 network oracle
  matrix, and M9 strict-sandbox denial tests.

### D006: Multi-source execution belongs to the core runtime

- Status: accepted
- Milestone: M8
- Profiles: core text-template API, Helm example, future gomplate-like runtimes
- Decision: immutable named-source associations, per-source render contexts,
  per-source batch execution, and synchronous/asynchronous dynamic-source
  inheritance are core APIs. Package-root `gotpl.TemplateEngine` owns generic
  cross-file execution. The Helm
  example retains chart traversal, chart globals, and the
  Helm-specific `include` and `tpl` contracts, but builds on the same compiled
  namespace and VM as ordinary templates.
- Reason: cross-file definitions and references are Go template capabilities,
  and multiple ecosystem runtimes need them. Reimplementing namespace merge,
  parsing, source attribution, async dispatch, and recursion handling in every
  integration would create divergent semantics and duplicate hot paths.
- Performance effect: `with_source` parses and compiles only the added source;
  rendering an already associated source does not recompile it. The convenience
  `render_source` APIs intentionally compile on each call. Helm `tpl` must do
  the same for observable compatibility; any future cache must be bounded,
  preserve function and option identity, and be justified by M8 profiling.
- Compatibility effect: none. `gotpl.funcs.helm` contributes the `include` and
  `tpl` function names but requires application-owned implementations. Their
  execution, error, and empty-value behavior remain in the embedding runtime;
  the example demonstrates Helm's contract. Neither name enters Go's built-in
  function registry.
- Evidence: core multi-source and dynamic-source unit tests, sync/async parity
  tests, and the pinned Helm integration oracle.

### D007: Pin Helm's generated default capabilities without Kubernetes SDKs

- Status: accepted
- Milestone: M8
- Profiles: `examples.helm_runtime.Capabilities.default()`
- Decision: check in the ordered API-version baseline generated by Helm v4.2.3
  and its pinned client-go v0.36 module graph. Expose it through an immutable
  sequence with Helm's `Has` method. Do not import a Kubernetes Python client or
  construct a runtime API scheme merely to reproduce this constant default.
- Reason: Helm computes the default from its compiled Go Kubernetes scheme.
  Reconstructing that scheme in Python would add a large runtime dependency,
  substantial import time, and a second version-resolution problem. The result
  is fixed for a pinned Helm build and has only 55 ordered strings.
- Performance effect: constant tuple construction replaces Kubernetes scheme
  registration and discovery. Import and default-capability creation remain
  deterministic and network-free.
- Compatibility effect: none for the pinned default. Callers may still provide
  an explicit `APIVersions` value to model a live cluster. A Helm reference
  upgrade must regenerate and differentially verify the tuple.
- Evidence: a pinned Helm oracle fixture compares the complete ordered range,
  membership, length, Kubernetes version fields, and Helm build information.

### D008: Use Python serializers with explicit Helm diagnostic boundaries

- Status: accepted documented difference
- Milestone: M8
- Profiles: reusable Helm YAML, TOML, and JSON functions
- Decision: use PyYAML, tomli-w, `tomllib`, and `json` behind the `helm` extra.
  Match Helm's successful map, nested-map, list-indentation, and ordinary TOML
  table output where the formats overlap. Preserve Helm's failure result shape:
  tolerant decoders return an `Error` entry or one-element list, tolerant
  encoders return an empty string or error text, and `must` variants fail.
  Exact parser diagnostic wording is Python-library-specific. tomli-w may also
  choose an inline table for a short array of tables where BurntSushi TOML emits
  repeated `[[table]]` sections.
- Reason: reproducing the complete error vocabulary and all encoder layout
  heuristics of three pinned Go serializer implementations would require
  maintaining independent YAML, TOML, and JSON parsers. Those strings are not
  template-language semantics, while result shape and successful serialized
  content are operationally important.
- Performance effect: dependencies remain lazy and optional. Core imports pay
  no serializer import cost; serializer calls use maintained native Python
  implementations rather than a template-specific parser.
- Compatibility effect: invalid-input diagnostic text and the noted TOML
  array-of-tables layout are documented differences. Ordinary upstream Helm
  function cases are pinned-oracle tested.
- Revisit condition: a chart demonstrates reliance on exact diagnostic text or
  TOML array-table layout, or a maintained serializer exposes compatible modes.
- Evidence: `tests/conformance/test_helm.py`, optional-dependency tests, and
  `docs/reports/m8-helm-functions.md`.

### D009: Keep prepared-chart caching out of the Helm example

- Status: amended; prepared-chart deferral retained
- Milestone: M8, amended in M10
- Profiles: `examples.helm_runtime.Engine`, Helm `tpl`
- Decision: the miniature Helm runtime continues to compile a chart on each
  `Engine.render()` call. It does not add a transparent chart cache or promote
  a prepared-chart abstraction to `gotpl.exts.helm`. Within one render only,
  identical `tpl` sources reuse a bounded compiled dynamic engine keyed by the
  immutable parent namespace. Applications that need reusable cross-file
  execution still build and retain `gotpl.TemplateEngine` instances in their
  own runtime layer.
- Reason: the Helm engine is an example, while reusable immutable compilation
  already belongs to the core runtime. A transparent cache would need bounded
  lifetime, function-registry identity, option identity, dynamic-source and
  redefinition semantics, concurrency behavior, and strict-sandbox accounting.
  Defining those policies in an example would create a second public runtime
  contract before representative applications establish the required API.
- Performance effect: on the M8 fixture, Python Helm static cold render was
  0.415 ms and dynamic `tpl` cold render is 0.441 ms; `tpl` adds 6.3%. Profiling
  attributes most cumulative time to compilation, parser work, and validation
  of the 222-function registry. Complex-chart profiling later found 96 `tpl`
  calls but only 19 distinct sources in kube-prometheus-stack. The bounded
  render-local cache reduced representative Loki and kube-prometheus-stack
  render medians by 63.2% and 66.5%, respectively.
- Compatibility effect: the cache is discarded after every render and includes
  parent namespace identity, so dynamic definitions remain isolated and values
  are rendered afresh. Chart construction, function changes, separate render
  calls, and concurrency do not share cached state.
- Revisit condition: a real embedding application misses an adopted latency
  budget, or the example runtime is proposed for promotion into a supported
  prepared-chart API. Any cache must remain bounded and pass redefinition,
  concurrency, async, and strict-budget tests.
- Evidence: `benchmarks/helm/fixtures/runtime-v1.json`,
  `benchmarks/helm_runtime.py`, `benchmarks/helm_chart.py`,
  `tools/helm_oracle/benchmark_test.go`, `docs/reports/m8-helm-performance.md`,
  and `docs/reports/m10-helm-complex-charts.md`.

### D010: Do not approximate Sprout safe-function generation

- Status: accepted deferral and documented difference
- Milestone: M8
- Profiles: Sprout handler and registry groups
- Decision: M8 exposes Sprout's pinned raw functions, aliases, notices, and
  `all`/`hermetic` groups, but does not expose a `safe_functions` switch or
  synthesize `safeX` names. The absence is explicit; safe names are not added
  with a generic `None` or empty-string fallback.
- Reason: upstream safe wrappers swallow a function error while returning the
  precise zero value of that function's first Go return type. pygotpl adapters
  intentionally use `FunctionResult` and many have an `object` return surface,
  so Python annotations cannot recover whether the compatible fallback is
  `false`, `0`, `""`, an empty collection, a zero struct, or `nil`. Correct
  support needs pinned return-shape metadata and oracle cases across every raw
  function and alias. A generic fallback would appear resilient while changing
  pipelines and conditionals silently.
- Performance effect: enabling the feature upstream approximately doubles the
  `all` group from 251 names to 502 and adds a wrapper call to each safe
  invocation. Default registries pay no cost. Performance is secondary to the
  missing zero-value contract, but any future implementation must benchmark
  construction, lookup, and call overhead.
- Compatibility effect: templates using `safeX` names are unsupported and fail
  at parse time. Ordinary Sprout names and groups are unaffected. pygotpl does
  not claim compatibility for Sprout's optional safe-function feature.
- Revisit condition: a consumer requires safe functions and the project adds a
  generated, pinned return-shape ledger with success, error, panic-equivalent,
  alias, and template-pipeline oracle coverage.
- Evidence: pinned `handler.go`, `internal/runtime/safecall.go`, upstream safe
  function tests and documentation, plus the 234-function M8 evidence audit.

### D011: Keep hard resource isolation outside the Python process

- Status: accepted boundary
- Milestone: M9
- Profiles: opt-in strict sandbox and Python `reMatch`
- Decision: provide deterministic VM-visible limits for template-source
  characters, output characters, range items, active associated-template depth,
  and function or method calls. Deny every caller registry function by default.
  Do not claim an in-process CPU deadline, heap quota, callback preemption, or
  Python-regex step budget. Hostile workloads require a replaceable worker with
  operating-system resource and wall-time limits.
- Reason: Python cannot safely interrupt arbitrary user callbacks or native
  dependencies, account all allocations to one render, or impose a step budget
  on the standard-library backtracking matcher. Thread or asyncio cancellation
  does not stop CPU-bound Python or blocking native work. Presenting those
  mechanisms as a sandbox would create a false security guarantee.
- Performance effect: default Go-compatible rendering pays no counter or writer
  wrapper cost. Opt-in budgets use one counter check per visible unit. The
  256-entry Python regex compilation cache bounds retained compiled patterns,
  but matching time remains pattern-dependent.
- Compatibility effect: none; the sandbox and `reMatch` are explicit Python
  extensions. Strict policy rejects `reMatch`, mutation, cryptography, network,
  environment, serializers, and eager resource-amplifying helpers unless the
  caller deliberately grants their names.
- Revisit condition: a maintained Python runtime API provides enforceable
  per-operation CPU, allocation, or regex-step accounting without unsafe
  process-global side effects.
- Evidence: `tests/security/test_sandbox_policy.py`,
  `tests/async/test_sandbox_budget.py`, `tests/unit/test_python_extensions.py`,
  and `docs/sandbox.md`.

### D012: Publish gotpl and reintegrate non-product compatibility leaves

- Status: accepted
- Milestone: M10 pre-freeze architecture
- Profiles: distribution/import naming, formatting, regex, and function maps
- Decision: publish and import the main library as `gotpl` while retaining the
  repository name `pygotpl`. Move Sprig, Slim-Sprig, Sprout, and Helm functions
  under `gotpl.funcs`; move Python-native functions under `gotpl.pythonic`.
  Reintegrate the incomplete `gofmt` and `goregexp` workspace distributions as
  private `gotpl._compat` modules. Retain `goduration` and `gotime` as the only
  independent compatibility distributions. Do not ship a duplicate `pygotpl`
  import alias before 1.0.
- Reason: `gotpl` is the shorter user-facing name and both relevant PyPI JSON
  endpoints returned no published project at review time. Function libraries
  share one auditable category without entering the default registry.
  `goduration` and `gotime` have coherent human-friendly object APIs and
  plausible standalone users; the formatting and RE2 layers deliberately
  implement only template-ecosystem subsets. Four required compatibility wheels
  increased installation, coordinated release, dependency resolution, CI, and
  support work without adding a real product boundary. A second import alias
  would preserve two names throughout documentation, typing, module identity,
  tracebacks, and support before any stable user contract exists.
- Simplification: remove the unused Python facade of the private RE2 engine;
  `gotpl.pythonic.reMatch` uses Python `re` directly. Keep the private gofmt
  Python mode because `format_mode="python"` is a supported template feature.
  The root `gotpl/py.typed` marker covers the private compatibility modules, so
  their former distribution-local markers are removed as redundant packaging
  artifacts. Do not merge similarly named Helm, Sprout, or Sprig conversion,
  serializer-loading, numeric, or optional-dependency helpers unless pinned
  oracle evidence proves identical value, error, and type behavior. Their
  current overlap reflects distinct upstream contracts rather than accidental
  implementation duplication.
- Performance effect: core formatting and regex call paths retain the same
  implementations and algorithms. Installation drops two wheel resolutions;
  imports avoid no meaningful hot-path work because the previous packages were
  pure Python workspace dependencies. Representative benchmarks and full
  parity suites must confirm no regression after the move.
- Compatibility effect: no template behavior changes. Pre-1.0 Python imports
  change from `pygotpl` to `gotpl`, and ecosystem imports move to
  `gotpl.funcs.*`. Direct `gofmt` and `goregexp` imports are intentionally no
  longer supported; neither distribution had been published as stable.
- Revisit condition: only demonstrated external users justify a separately
  versioned formatting or regex product. A legacy `pygotpl` alias requires a
  published release with users who cannot migrate directly.
- Evidence: architecture import tests, the combined formatting/regex oracle
  suites, isolated three-wheel installation, and the M10 package-architecture
  report.

### D013: Preserve multi-source HTML behavior through immutable construction

- Status: accepted documented difference
- Milestone: M10 public API freeze
- Profiles: `HTMLTemplate` construction and cross-source contextual analysis
- Decision: provide `HTMLTemplate.from_sources`, `with_source`,
  `render_source`, and `render_source_async`. Analyze the complete association
  before it can execute, and return a new object whenever a source is added or
  replaced. Do not reproduce Go's mutable `Clone`, `AddParseTree`, post-parse
  redefinition, `ParseFiles`, `ParseGlob`, or `ParseFS` methods. File and glob
  discovery remain application-owned and feed source mappings into gotpl.
- Reason: source association, cross-template calls, contextual specialization,
  and fail-closed analysis are observable template behaviors and therefore
  belong in the compatibility path. Go's mutable builder methods are an API
  shape rather than template language behavior. Adding them would conflict
  with the project's immutable, task-safe compiled-template contract and would
  create partial-analysis states that callers could execute accidentally.
- Performance effect: warm rendering is unchanged. Initial `from_sources` and
  each `with_source` call analyze the complete HTML namespace. This deliberate
  construction-time cost avoids runtime context checks and stale variants. A
  future persistent analysis cache requires measured construction workloads,
  bounded memory, and equivalence tests before adoption.
- Compatibility effect: associated source content and execution are supported;
  Go method names, in-place mutation, and filesystem discovery are not. Text
  templates retain the same immutable source APIs, while `TemplateEngine`
  remains the generic text-oriented batch runtime.
- Revisit condition: a real integration cannot efficiently provide source
  mappings, or profiling shows complete namespace reanalysis dominates a
  supported long-lived dynamic-source workload.
- Evidence: multi-source URL-context specialization, immutable derivation,
  sync/async dynamic source, named-root execution, fail-closed HTML, and
  concurrency tests.

### D014: Accept M10 alert-level regressions and defer hot-path specialization

- Status: accepted deferral
- Milestone: M10 release performance review
- Profiles: representative Go-shared text, HTML, Sprig, and Python-engine
  workloads
- Decision: accept the complete release-suite alert-level changes relative to
  the historical M6 and M7 developer-machine medians. The largest complete-run
  changes are +8.78% for the large named-template set and +8.50% for cold text;
  neither crosses the 10% blocker. Do not add a native extension, isolated
  opcode, or speculative context fast path before release. Continue tracking
  every fixture and apply the normal policy to future credible regressions.
- Reason: all changes remain below the explicit 10% release-blocking line,
  output hashes agree, and the comparison spans accumulated M7-M10 capabilities
  without a commit-isolated attribution point. An independent eleven-sample
  large named-template rerun measured only +5.37%, demonstrating why the
  earlier noisy +14.28% observation cannot justify a VM change. More importantly,
  measured implementation alternatives have poor leverage: compiling the actual VM with
  Cython failed the 25% two-workload gate, and a direct field opcode improved
  only one workload by 1.53% while slightly slowing another. A credible next
  design must fuse several instruction families and prove sync, async, HTML,
  security, error-location, and reference-VM parity; that is not a safe release
  micro-optimization.
- Performance effect: this decision makes no code-path change. It records all
  release-suite medians, RSD, and alert-level changes rather than hiding them.
  Text and HTML remain 3.38x and 2.34x Jinja on stable measured warm fixtures;
  callback and async paths remain in the same comparison band.
- Compatibility effect: none. No semantic shortcut, final-string HTML escape,
  benchmark-only branch, or native runtime dependency is introduced.
- Revisit condition: a representative path crosses the 10% blocker, hosted
  history confirms continuing deterioration, a user workload establishes a
  missed latency budget, or a fused linked-instruction prototype improves at
  least two non-trivial paths without a >5% unexplained regression elsewhere.
- Evidence: the M10 release performance report, M6 native-accelerator report,
  and M7 specialized-instruction prototype.

### D015: Put Helm late-bound execution in the reusable library

- Status: accepted, then generalized by D016
- Milestone: M10 Helm integration follow-up
- Profiles: `gotpl.exts.helm`, `examples.helm_runtime.Engine`
- Decision: expose `HelmTemplateEngine` from `gotpl.exts.helm`. It originally
  owned the associated namespace lifecycle for `include` and `tpl`, the Helm
  behavior of `required` and `fail`, and per-render recursion and dynamic-source
  state. D016 retained this surface as a facade over the generic session. The
  example runtime supplies Chart-specific contexts but no longer implements
  those functions. Keep `function_map()` as the lower-level escape hatch for
  applications with a different execution lifecycle.
- Reason: four required application callbacks made the nominally reusable Helm
  registry incomplete and forced consumers to copy subtle sync, async,
  recursion, error, namespace, and caching behavior from an uninstalled
  example. These behaviors are Helm execution infrastructure, not Chart model
  policy.
- Performance effect: the compiled base association can now be retained across
  calls by direct library users. Dynamic `tpl` caching remains bounded and
  scoped to one render. The example retains its existing cold-render lifecycle
  and measured behavior.
- Compatibility effect: `include`, `tpl`, `required`, and `fail` retain their
  pinned-oracle behavior. Context-local execution state keeps a shared engine
  safe across threads and asyncio tasks and prevents dynamic definitions from
  leaking between renders.
- Revisit condition: a future public Chart API requires a higher-level package,
  or runtime policy inputs must be added without weakening the immutable core
  engine boundary.
- Evidence: direct public runtime tests, example-engine regression tests,
  thread reuse, async include/tpl, and dynamic-source cache isolation.

### D016: Generalize late-bound execution through immutable environments

- Status: accepted
- Milestone: M10 runtime-extension follow-up
- Profiles: core text/HTML runtime and opt-in ecosystem extensions
- Decision: introduce an immutable construction `Environment`, explicit
  context-aware function descriptors, a read-only public render context, and a
  private per-render session. Keep `from_sources()` as the complete association
  boundary and keep loaders application-owned. Reimplement Helm late-bound
  functions over the generic session. Keep Helm explicitly text-only and retain
  `HelmTemplateEngine` as the convenient source-compatible facade.
- Reason: Helm's `include` and `tpl` demonstrate a reusable need for controlled
  access to the active association. Keeping that lifecycle Helm-specific would
  require every integration to copy recursion, caching, error, budget, and
  sync/async behavior. A mutable global environment would solve a different
  problem and weaken construction-time and concurrency guarantees.
- Performance effect: ordinary templates allocate no render session, and linked
  direct callables retain their direct path. Reusing a prepared registry removed
  duplicate Helm cold-construction validation: sampled static and `tpl` medians
  fell from 0.692/0.745 ms to 0.497/0.559 ms, with median traced peak bytes down
  from 86,449 to 72,929. The paired linked/reference benchmark retained output
  parity across text, HTML, Sprig, and a 33-template association.
- Compatibility effect: the proposal is additive. Existing constructors,
  function maps, and Helm facade remain supported during migration. Runtime
  extensions cannot add syntax or alter the default Go compatibility path.
- Revisit condition: hosted history finds a material ordinary-render
  regression, another real integration requires lifecycle hooks excluded from
  the protocol, or a private compiled-association consolidation proves useful
  without widening the public API.
- Evidence: the
  [unified environment and runtime extension design](reports/m10-unified-environment-design.md).

### D017: Separate function registries from context-aware extensions

- Status: accepted
- Milestone: M10 runtime-extension follow-up
- Profiles: `gotpl.funcs`, `gotpl.exts`
- Decision: retain pure compatibility registries under `gotpl.funcs` and expose
  context-aware integrations under the abbreviated `gotpl.exts` namespace.
  Rename the public protocol from `RuntimeExtension` to `Extension`, move
  `HelmExtension` and `HelmTemplateEngine` to `gotpl.exts.helm`, and leave the
  lower-level Helm `function_map()` under `gotpl.funcs.helm`.
- Reason: a function registry only contributes template callables, while an
  extension may require injected render context, per-render state, nested
  rendering, template-kind restrictions, and sandbox capabilities. Keeping
  those concepts in separate namespaces makes the common user path discoverable
  without misclassifying Sprig, Slim-Sprig, or Sprout as runtime extensions.
- Compatibility effect: pre-1.0 import cleanup only; no legacy alias is shipped.
  Template behavior and function names are unchanged.
- Evidence: public API contract, import-layer checks, Helm runtime tests, and
  strict documentation build.

### D018: Group Python-native functions without changing template syntax

- Status: accepted
- Milestone: M10 API follow-up
- Profiles: `gotpl.pythonic`, `Environment.pythonic()`
- Decision: keep Python-native helpers in a separate immutable registry with
  `text`, `encoding`, `hashing`, `compression`, and `regex` categories. Offer
  `common` and `all` profiles, explicit category selection, and
  `Environment.pythonic(...)` as the high-level constructor. It fixes
  `format_mode="python"` while retaining Go template syntax, pipelines, and
  control flow.
- Reason: a growing list of boolean options makes opt-in selection hard to
  discover, while a universal global Python namespace would obscure collisions
  and grant expensive or backtracking functions accidentally. Python's built-in
  `hash()` is intentionally not exposed because its process-randomized result
  is unsuitable for rendered output; named cryptographic digests are explicit.
- Compatibility effect: additive only. The default Go-compatible construction
  path and existing `PythonExtensions(re_match=True)` usage remain unchanged.
  Pythonic formatting changes values such as Boolean output by explicit caller
  selection.
- Security effect: `common` excludes backtracking `reMatch`; every selected
  function remains subject to strict sandbox allowlists and callback work is
  still outside VM budget accounting.
- Evidence: direct category, profile, composition, sandbox, and environment
  API tests; strict documentation build.

## Open Reviews

No complexity review is currently open. New simplifications or deferrals must
be added here before their milestone can close.
