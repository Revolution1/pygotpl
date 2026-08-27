# M2: Synchronous Text Templates

## Outcome

Provide a reusable, thread-safe synchronous implementation of the targeted
`text/template` behavior.

## Deliverables

- [x] Dot, root, variables, scopes, and call frames.
- [x] Central Python value adapter with documented rules.
- [x] Truthiness, comparison, indexing, slicing, and iteration.
- [x] Pipelines and Go built-in functions.
- [x] Named-template namespaces and invocation.
- [x] Missing-key modes and project exception hierarchy.
- [x] Buffered, string, and writer output APIs.
- [x] Public `render` and `Template` APIs.
- [x] Thread-safety tests and warm-render benchmarks.

## Acceptance Gates

- [x] Required sync conformance fixtures match Go 1.27.x.
- [x] Python adaptation questions in `docs/compatibility.md` are resolved.
- [x] VM code reaches 100% statement coverage.
- [x] Public APIs and error paths have direct tests.
- [x] A Go/Python text-render performance report is recorded.
- [x] Remaining semantic gaps are enumerated and assigned.

## Non-Goals

- Awaiting asynchronous functions.
- Sprig compatibility.
- Contextual HTML escaping.
