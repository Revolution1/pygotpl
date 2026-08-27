# M2 Synchronous Semantic Gap Register

This historical register tracks work identified during M2. M2 has no open
owned row: later performance and recursion work closed in M6. A newly found
gap is not an accepted permanent difference unless the
[compatibility contract](../compatibility.md) explicitly classifies it that
way.

## Open Gaps

None in the approved M2 scope.

## Resolved During M2

- Go formatting covers core flags and verbs, indexed and dynamic operands,
  diagnostics, byte slices, rune-aware quoting, byte-aware hexadecimal
  precision, binary and hexadecimal floats, and explicit `GoPointer` values.
  `GoFormatter` supplies Python's explicit adaptation of `fmt.Formatter`.

- Registered function arity is validated before invocation. Fixed, bounded by
  Python defaults, and variadic signatures have stable diagnostics; optional
  keyword-only defaults are retained, and required keyword-only parameters are
  rejected because template commands are positional.
- Homogeneous complex mapping keys are ordered by real and then imaginary
  component. Mixed and custom Python key types retain the documented stable
  fallback because they have no single Go map-key type equivalent.
- `TemplateExecutionError` retains the innermost instruction or pipeline
  location with UTF-8 byte position, character line and column, root source
  name, and executing template name. Nested template calls do not overwrite a
  callee failure location.
- `TypedMap` carries an explicit element zero value used by missing `index`
  operations and `missingkey=zero` field lookup. Ordinary Python mappings keep
  the documented dynamic `None` fallback rather than relying on unsafe type
  inference.
- `GoSeq` and `GoSeq2` explicitly model their different declaration and dot
  binding rules. Synchronous Python iterables provide deterministic
  array/channel-style indexed entries; asynchronous iterable cancellation and
  closure remain assigned to M3.

- Intermediate no-argument bound methods are invoked during field-chain
  traversal, with exceptions translated and chained.
- `FunctionResult` explicitly represents Go-style value/error returns. Raised
  Python exceptions use the same error path, and ordinary tuples are never
  implicitly unpacked.

## Resolved During M6

- The complete performance suite added profiling, multi-sample variance,
  Python memory evidence, optimization decisions, and cross-engine reports.
- Sync and async named-template calls use an explicit, lazily allocated caller
  stack rather than Python recursion. A 1,500-template finite chain executes in
  both runtimes, callees retain isolated root-variable scopes and innermost
  error locations, and the non-wasm Go depth limit and diagnostic are
  matched at 100,000 calls.
