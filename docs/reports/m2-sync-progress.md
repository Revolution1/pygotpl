# M2 Synchronous Runtime Completion Report

## Status

M2 is complete for its scoped synchronous runtime. M6 subsequently replaced
recursive named-template execution with explicit caller frames; remaining
optimization and release-wide compatibility work stays assigned to M6 and M10.

## Environment

- Date: 2026-08-25
- Platform: Darwin 25.5.0, arm64
- Python: CPython 3.13.7
- Go: 1.26.5, darwin/arm64

## Correctness Evidence

- Sixty-eight independently authored `text/template` fixtures match the pinned
  Go oracle.
- Missing-key modes, streaming writer behavior, Python object adaptation,
  caller exception translation, and concurrent warm rendering have direct
  Python tests.
- One reusable compiled template completed 100 concurrent renders without
  shared execution-state contamination.
- The synchronous VM reaches 100% statement coverage, including malformed-IR
  defenses and built-in error translation.
- Go-style formatting now covers the conformance-tested value, syntax, type,
  indexed-operand, dynamic width and precision, string hexadecimal, quote,
  integer, binary float, hexadecimal float, padding, and diagnostic behavior
  without delegating to Python percent formatting.
- Public render APIs default to Go formatting and provide an explicit
  `format_mode="python"` extension for native Python value representations.
- Intermediate no-argument bound methods are invoked inside field chains, and
  `FunctionResult` provides explicit Go value/error semantics for Python
  callables without reserving ordinary tuples.
- Registered callables have pre-invocation positional arity checks with stable
  diagnostics. Python defaults are supported, while required keyword-only
  parameters are rejected at registration.
- Complex map keys use the Go ordering of real component followed by imaginary
  component, and complex values use Go's `i` representation.
- Execution errors expose source-mapped byte position, character line and
  column, source name, and executing template name. Nested calls preserve the
  innermost failure location.
- `TypedMap` preserves an explicit element zero value for missing `index`
  operands and `missingkey=zero` field lookups without guessing the element
  type of ordinary Python mappings.
- `GoSeq` and `GoSeq2` preserve Go's different range binding rules. Integer
  ranges reject two declarations, while ordinary Python iterables retain
  indexed array/channel-style behavior.
- Byte slices, Unicode quoting and precision, explicit pointer adapters, and a
  custom `GoFormatter` protocol cover the remaining planned M2 formatter
  adaptation surface.
- The acceptance audit added UTF-8 byte semantics for string built-ins, exact
  HTML and JavaScript escaping edges, invalid and nil range behavior, typed nil
  pointer truthiness, and translated property and iterator failures.
- Registered functions, bound methods, and `call` targets share pre-invocation
  annotation validation. Writer short writes are detected instead of silently
  discarding output.
- Public `ExecuteTemplate` equivalents execute associated definitions, preserve
  sibling calls, and keep the named root in the immutable namespace.

## Warm-Render Baseline

Run with:

```console
python -m benchmarks.compare benchmarks/fixtures/literal.json
python -m benchmarks.compare benchmarks/fixtures/text_render.json
```

| Case | Python ns/op | Go ns/op | Python/Go |
| --- | ---: | ---: | ---: |
| Literal output | 1,342.75 | 35 | 38.36x |
| Range, branch, fields, and `printf` | 13,431.32 | 1,379 | 9.74x |

Go reported 2 allocations and 128 bytes per literal render, and 35 allocations
and 848 bytes per control-flow render. Python allocation counts are not yet
recorded. Results are directional measurements from one local run and are not
release thresholds.

## Remaining M2 Gates

- Complete the Go built-in function behavior and error matrix.
- Expand the required synchronous conformance matrix.
- Produce the final optimized performance report.
