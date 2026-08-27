# M8: Ecosystem Integrations

> Historical milestone: M10 later reintegrated the `gofmt` and `goregexp`
> workspace packages under private `gotpl._compat`. References below to those
> M7 packages describe the boundary validated during M8, not a current public
> import surface.

## Outcome

Provide isolated, opt-in `gotpl.funcs.sprout` registries and reusable
`gotpl.funcs.helm` functions on the stable M7 boundaries. Demonstrate them with a
miniature Helm runtime under `examples/`, without creating separate
distributions or expanding the core Go-template or Sprig namespaces.

Cross-file named-template namespaces, per-source render contexts, batch
execution, and dynamic source inheritance are core runtime capabilities.
`gotpl.funcs.helm` supplies reusable functions only. The example owns chart
collection, Helm globals, and orchestration. This boundary is also intended for
later gomplate-like runtimes.

## Deliverables

- [x] Versioned Sprout v1.1.1 function, alias, notice, and group inventories,
  generated and verified by `scripts/check_sprout_inventory.sh`; see
  `docs/reports/m8-sprout-inventory.md`.
- [x] Sprout registry-level and `all`/`hermetic` group APIs.
- [x] Helm function map including `include`, `required`, and `tpl` semantics;
  see `docs/reports/m8-helm-functions.md`.
- [x] Core immutable multi-source namespaces, per-source
  package-root `gotpl.TemplateEngine` execution, and synchronous/asynchronous
  dynamic-source inheritance.
- [x] Explicit Helm chart globals and release-capability model in the example
  runtime, without adding them to the pygotpl public package API.
- [x] Pure Python miniature Helm CLI under `examples/`.
- [x] Initial end-to-end rendering fixture from a representative Helm chart;
  expansion of the compatibility matrix remains an acceptance gate.
- [x] Versioned representative Helm workloads with integration-level latency,
  memory, and hotspot profiles suitable for the ongoing performance suite.
- [x] Optional dependency groups with actionable missing-extra diagnostics.

## Acceptance Gates

- [x] Every exposed Sprout function is oracle-backed or a documented difference.
- [x] Helm integration fixtures agree with the pinned Helm behavior baseline.
- [x] The core wheel installs and renders without optional dependencies.
- [x] Sprout, Helm, and project-extra names never enter Go or Sprig registries.
- [x] Network, filesystem, environment, and cryptographic capabilities are
  explicit and covered by security tests.
- [x] Helm fixtures identify the functions, globals, and object capabilities
  that the later strict sandbox must allow or deny explicitly.
- [x] Helm profiling follows the M6 methodology and distinguishes integration
  overhead from the core parser, workspace packages, and runtime.
- [x] Sprout and Helm follow the documented owned-module import graph and use
  only public workspace-package boundaries.
- [x] Sprout or Helm regexp gaps extend `goregexp` only for concrete pinned
  compatibility cases, with oracle-backed tests; M8 does not broaden it into a
  complete Go `regexp` clone.

## Non-Goals

- Reimplementing the complete Helm command-line application.
- Installing Go, invoking Helm, or spawning subprocesses at runtime.
- Treating Sprout differences as silent changes to Sprig behavior.
- Expanding `gofmt` or `goregexp` for standalone completeness without a
  template-ecosystem consumer.

Complexity, performance, security, simplification, and deferral decisions are
recorded in `docs/implementation-decisions.md`; an inventory entry alone never
counts as an implementation.

The completed gate-by-gate evidence is summarized in the
[M8 acceptance audit](../reports/m8-acceptance-audit.md).
