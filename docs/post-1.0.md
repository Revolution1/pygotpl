# Post-1.0 Conformance Backlog

This backlog records proof and compatibility work that is outside the current
M10 release gates. It does not weaken the required suites or turn discovered
mismatches into accepted differences.

The current measured claim boundary remains authoritative in the
[compatibility contract](compatibility.md); completing a backlog item changes
no public status until its evidence is reviewed there.

## Standard-Library Proof Expansion

- Map every remaining applicable Go `text/template` test case to an
  independently authored differential case or a documented Python host-value
  adaptation. Promote the compatibility row only when no applicable case is
  represented solely by a broad behavior-group assertion.
- Do the same for `html/template`, including construction and association
  cases after D013. Contextual engine families are covered, but the final claim
  requires case-level traceability across the full pinned upstream suite.
- Keep exact error wording scoped to upstream messages classified as stable;
  otherwise compare phase, source position, partial output, and semantic
  meaning.

## Optional Ecosystem Work

- Revisit Sprout safe-function generation only if the registry gains typed
  fallback metadata and a pinned oracle matrix for generated wrappers.
- Add asynchronous iterable consumption only as an explicit Python extension
  with cancellation, closure, backpressure, and sync-boundary rules.
- Revisit exact Helm serializer diagnostics or TOML layout only when a real
  chart depends on them or a maintained serializer exposes the required mode.

## Performance Revisit Triggers

Do not pursue a native VM or persistent HTML-analysis cache solely to reduce a
headline ratio. Reopen those designs when a representative supported workload
shows a material regression, construction dominates a long-lived dynamic-source
runtime, or gotpl becomes materially slower than the Python template-engine
comparison band. Every optimization retains the reference VM and oracle suites
as correctness baselines.
