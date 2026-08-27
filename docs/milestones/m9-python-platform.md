# M9: Python Platform

## Outcome

Add an explicit untrusted-template policy and bounded Python-native extensions
on the stable workspace and ecosystem architecture before the version 1.0 API
freeze.

## Deliverables

- [x] Immutable sandbox policy API shared by text and HTML templates.
- [x] Strict sandbox preset that defaults to data-only lookup and explicitly
  allowlisted attributes, methods, and functions.
- [x] Execution-budget model covering output size, iteration work, and template
  call depth, with documented process-level limits for CPU and memory.
- [x] Adversarial sandbox suite for properties, bound methods, data-supplied
  callables, mutable Sprig functions, ecosystem registries, and
  resource-exhaustion inputs.
- [x] Immutable Python-extension configuration that cannot be changed from
  template source.
- [x] Python `re`-backed `reMatch(pattern, value)` extension with search
  semantics, bounded compilation caching, and explicit backtracking-risk
  documentation.
- [x] Decisions and tests for any Python-native numeric or helper extensions;
  no extension may replace a Go, Sprig, Slim-Sprig, Sprout, or Helm name in a
  compatibility profile.
- [x] Sandbox and extension adapters use public M7 workspace-package APIs and
  do not introduce reverse dependencies into those packages.

## Acceptance Gates

- [x] Default construction remains Go-compatible and does not enable sandbox
  or Python-native behavior implicitly.
- [x] Strict sandbox tests demonstrate that arbitrary Python properties,
  methods, data callables, and non-hermetic registries are inaccessible.
- [x] Documentation distinguishes contextual HTML safety, execution sandboxing,
  and operating-system resource isolation.
- [x] `reMatch` is absent from Go, Sprig, Slim-Sprig, Sprout, Helm, and
  strict-sandbox profiles unless a caller explicitly allows it.
- [x] Python-native configuration is part of construction and cache identity;
  template code cannot mutate parsing, execution, or security policy.
- [ ] The pure Python implementation remains complete, tested, and installable
  on every supported interpreter and platform without a compiler.
- [x] The complete pygotpl and workspace-package suites pass with no observable
  compatibility, security, or dependency-direction regression.

## API Direction

Sandboxing is an opt-in execution policy, not a change to the default Go
adapter. Python extensions are selected by immutable construction options or an
explicit registry. In-template feature switches such as `setFeatureFlag` are
prohibited because parsing precedes execution and mutable policy would make
caching, concurrency, and security order-dependent.

`reMatch` uses Python standard-library regular-expression syntax and search
semantics. It does not alias, override, or alter Sprig's `regexMatch`, and it is
not a claim of Go regexp compatibility. Backtracking patterns are inappropriate
for untrusted templates or patterns and are disabled by the strict sandbox.

## Non-Goals

- Making untrusted in-process rendering equivalent to an operating-system
  security boundary.
- Enabling sandboxing or Python syntax by default.
- Adding a template-controlled feature-flag function.
- Replacing Sprig regex functions with Python `re` behavior.
- Redesigning or moving the workspace packages established in M7.

Implementation and security evidence is in the
[M9 sandbox report](../reports/m9-sandbox.md). The platform-install checkbox
remains open with the shared hosted-matrix gate tracked by M10.
