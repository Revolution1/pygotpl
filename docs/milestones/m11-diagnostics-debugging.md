# M11: Diagnostics and Debugging

## Outcome

Make failures in large, associated template sets explainable without changing
Go-compatible rendering behavior or imposing measurable debugging machinery on
the default execution path. Deliver rich source diagnostics first, then an
opt-in structured execution trace, and finally a source-level debugging session
that supports breakpoints and stepping in synchronous and asynchronous renders.

M11 begins after the M10 release gates. Its APIs are not part of the 1.0 API
freeze until their contracts and security boundaries pass this milestone.

## Current Baseline

`TemplateSyntaxError` exposes a byte position plus character line and column.
`TemplateExecutionError` additionally exposes the root source name, innermost
executing template name, and the original application exception as `__cause__`
where applicable. Runtime errors preserve the first attached execution
location, so a nested failure identifies its callee but not the template call
chain that reached it.

The current public API does not provide source excerpts, caret ranges, template
stack frames, execution events, value inspection, breakpoints, or step
operations.

## Architecture

```text
                             default path
template + data ---------------------------------> linked sync VM
       |                                            no trace hooks
       |
       | diagnostics / trace / debugging enabled
       v
instrumented generic VM -> event sink -> debugger controller
       |                     |               |
       |                     |               +-> break / continue / step
       |                     +-> structured trace
       +-> source map + frames + bounded value snapshots

async template + data -> instrumented async VM -> the same event vocabulary
```

The generic instruction stream remains the semantic reference and retains the
source positions needed for diagnostics. Debug execution may use a separate
instrumented dispatch loop. The linked synchronous sidecar must not gain an
unconditional per-instruction callback, event allocation, or debugger branch.
If debug mode cannot preserve a linked specialization transparently, it falls
back to the generic VM and reports that backend in session metadata.

Trace and debug state belongs to one render. Compiled templates remain immutable
and reusable across threads and asyncio tasks. Synchronous debugging must not
start an event loop; asynchronous debugging must preserve awaiting,
cancellation, and exception semantics.

## Deliverables

### Rich Diagnostics

- [ ] Define immutable public diagnostic, source-span, note, and template-frame
  value objects without exposing compiler or VM internals.
- [ ] Render configurable source context with Unicode-correct line and column
  handling, an action range or caret, nested causes, and stable plain-text
  formatting.
- [ ] Record the associated-template call chain while preserving the existing
  innermost `TemplateExecutionError` attributes and exception hierarchy.
- [ ] Identify the failing action or pipeline when the compiler has a valid
  source span; do not reconstruct expressions from runtime values.
- [ ] Provide a structured diagnostic API suitable for logs, web error pages,
  and editor integrations, plus an explicit human-readable formatter.
- [ ] Apply the same diagnostic model to text and HTML templates, including
  contextual-analysis failures where a source span is available.

### Structured Execution Trace

- [ ] Define a versioned event vocabulary covering template enter/exit,
  instruction or source-step boundaries, pipeline evaluation, function
  call/return/error, branch selection, range iteration, variable binding, and
  output writes.
- [ ] Provide callback/sink-based streaming so tracing does not require retaining
  the complete event history.
- [ ] Include source span, template frame, logical operation, and monotonically
  increasing event sequence; exclude raw internal instruction objects from the
  public contract.
- [ ] Support filters and bounded collection by event kind, template, source
  span, event count, and elapsed time.
- [ ] Keep sync and async event ordering equivalent for executions containing no
  asynchronous work.
- [ ] Define writer-event semantics without copying the complete rendered output
  for every write.

### Source-Level Debugging

- [ ] Resolve breakpoints expressed as source name plus line and optional column
  to executable source steps, with explicit reporting for unresolved locations.
- [ ] Support continue, pause, step into, step over, and step out at template
  source boundaries rather than raw VM program counters.
- [ ] Expose immutable frame snapshots containing template/source identity,
  source span, dot and root previews, scoped variables, and the current logical
  operation.
- [ ] Make named-template calls visible as frames and define range-iteration
  behavior for step operations.
- [ ] Provide separate synchronous and asynchronous session APIs. Async pause
  must not swallow cancellation or leave awaited application functions running
  after session closure.
- [ ] Define deterministic terminal states for completion, template failure,
  cancellation, execution-budget exhaustion, and debugger-limit exhaustion.

### Security and Resource Bounds

- [ ] Make value capture opt-in and apply configurable redaction by variable or
  field name, value type, and caller-supplied policy.
- [ ] Bound string length, collection items, object depth, event count, retained
  bytes, and debugger pause duration.
- [ ] Never call arbitrary `repr`, properties, methods, iterators, or user
  functions solely to produce a diagnostic or value preview.
- [ ] Ensure tracing cannot bypass sandbox policy, reveal denied members, mutate
  execution state, or enable capabilities unavailable to the template.
- [ ] Document that function arguments, return values, template data, and output
  may contain secrets and are excluded unless explicitly captured.

### Documentation and Integration

- [ ] Document exception diagnostics, trace consumption, breakpoint resolution,
  stepping semantics, redaction, limits, async behavior, and performance cost.
- [ ] Provide complex associated-template examples for text and HTML rendering.
- [ ] Add a minimal CLI debugger or machine-readable adapter only after the
  Python session contract is stable.
- [ ] Evaluate Debug Adapter Protocol integration separately; an IDE extension
  is not required for M11 completion.

## Testing and Evidence

- [ ] Add direct public-API tests for every diagnostic, trace, breakpoint,
  stepping, inspection, limit, and terminal-state operation.
- [ ] Verify byte positions and character columns with ASCII, multibyte Unicode,
  combining characters, multiline actions, and multiple source files.
- [ ] Cover nested definitions, recursion, `if`, `with`, `range`, `break`,
  `continue`, missing values, function errors, partial writes, and writer
  failures.
- [ ] Compare ordinary render output, error type, source position, partial
  output, and cause with debugging disabled and enabled.
- [ ] Compare sync and async trace sequences after removing explicitly
  async-only events for templates containing no asynchronous work.
- [ ] Test concurrent reuse of one compiled template by independent trace and
  debug sessions.
- [ ] Add adversarial tests for secret redaction, hostile objects, recursive
  values, huge containers, event floods, sandbox denial, budget exhaustion, and
  cancellation.
- [ ] Retain the Go oracle and generic VM as compatibility references; debugging
  events themselves are a Python API and must not be presented as Go behavior.

## Performance Gates

- [ ] Add checked-in representative benchmarks for diagnostics construction,
  filtered and unfiltered tracing, breakpoint lookup, stepping, and bounded
  value capture.
- [ ] On the existing warm-render benchmark set, debugging-disabled median
  latency must not regress by more than 2% and the default path must allocate no
  trace events or frame snapshots.
- [ ] Compare linked and generic output before measuring debug overhead, and
  report fallback backend selection explicitly.
- [ ] Record trace events per second, incremental bytes per retained event, and
  pause/resume latency without mixing those opt-in costs into normal-render
  claims.
- [ ] Run the full compatibility, HTML security, sandbox, sync/async parity, and
  benchmark regression suites before accepting the implementation.

## Non-Goals

- Editing template source or runtime data from a paused session.
- Rewinding execution or replaying side-effecting application functions.
- Hiding Python application tracebacks when the caller requests the original
  cause.
- Guaranteeing that debugging uses the same optimized backend as normal
  rendering.
- Making trace event wording or internal instruction names Go-compatible.
- Shipping an editor-specific extension before the core Python API stabilizes.

## Acceptance Gates

- [ ] Rich diagnostics identify the failing source range and complete associated
  template call chain without breaking existing exception consumers.
- [ ] Structured traces are bounded, filterable, redaction-aware, and equivalent
  across sync and async execution where their semantics overlap.
- [ ] Breakpoints and all four execution controls behave deterministically for
  nested templates and control flow.
- [ ] Debug sessions are isolated under concurrent template reuse and preserve
  async cancellation.
- [ ] Security tests demonstrate that inspection adds no property access,
  invocation, mutation, sandbox bypass, or default secret capture.
- [ ] The debugging-disabled performance and allocation gates pass on paired
  samples.
- [ ] Public documentation, compatibility boundaries, and recorded benchmark
  evidence match the shipped implementation.
