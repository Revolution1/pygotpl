# M2 Acceptance Audit

## Status

Complete for the scoped M2 synchronous runtime. The systematic behavior-group
mapping is recorded in `m2-behavior-inventory.md`; later milestone boundaries
remain explicit rather than being counted as M2 compatibility evidence.

## Evidence Reviewed

- M2 deliverables and acceptance gates.
- Go 1.27.0 `text/template` execution, built-in, option, and multi-template
  source and tests.
- The project upstream test map and all synchronous conformance fixtures.
- Public API, Python adaptation, writer, thread-safety, property, iterator, and
  malformed-IR tests.
- Branch-aware coverage, strict typing, lint, format, Go oracle, and benchmark
  reports.

## Defects Found and Closed

- `len`, `index`, and `slice` incorrectly treated strings as Unicode code-point
  sequences instead of UTF-8 byte sequences.
- Negative and Boolean sequence indexes incorrectly inherited Python indexing
  behavior.
- HTML escaping used Python entity spellings and preserved NUL instead of
  matching Go's text-template escaper.
- JavaScript escaping incorrectly escaped DEL and relied on Python
  printability rather than Go's explicit control and line-separator rules.
- Invalid and nil values raised during `range` instead of selecting its empty
  branch.
- A typed nil `GoPointer` was truthy.
- Property getter and Python iterator failures escaped the project exception
  hierarchy instead of retaining their cause in `TemplateExecutionError`.
- Callable parameter annotations were not enforced consistently across
  registered functions, bound methods, and the `call` built-in.
- Writer return counts were ignored, allowing a short write to appear
  successful and silently truncate output.
- The public API could invoke named templates only through template syntax; it
  lacked an `ExecuteTemplate` equivalent and omitted the named root from the
  runtime association namespace.

Each defect has a direct Python regression test or independently authored Go
oracle fixture.

## Completed Proof Work

The conformance inventory maps each applicable M2 behavior group from Go
`exec_test.go`, `multi_test.go`, and the public built-in tests to one of:

1. a differential fixture;
2. a Python adaptation test with a documented type-model reason; or
3. a later-milestone assignment with a tested boundary.

Callable values and methods, nested and associated templates, typed argument
failures, and writer/error semantics all gained direct evidence during the
audit. Deferred work is assigned to M3 through M10 in the inventory.
