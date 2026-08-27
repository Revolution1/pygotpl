# M12: Generated Synchronous Backend

## Outcome

Determine whether lowering validated template IR into compiler-owned Python
code objects can materially narrow the remaining control-flow performance gap
without changing Go-compatible behavior, weakening contextual escaping, or
making generated execution the semantic reference.

M12 is planned work, not an active continuation of the M10 performance
follow-up. It begins only after M11 completes and an explicit milestone
activation. Its source-map and error-translation design must use the public
diagnostic contracts established by M11 rather than inventing a second
debugging model.

## Current Baseline

The August 28, 2026 CPython 3.14.7 comparison against Jinja 3.1.6 measured the
reused `jinja/text-control` fixture at 8.088 us for gotpl and 3.856 us for
Jinja, a 2.10x latency ratio. The fixture ranges over three mappings, evaluates
one field condition per item, and writes two selected name/value pairs.

The retained linked sidecar already reduced the representative Go-shared text
control workload by 25.36%, contextual HTML by 27.55%, and Sprig-heavy
rendering by 14.34% relative to the generic sync VM. Later isolated
fixed-arity and complete-format-cache prototypes failed their retention gates.
This evidence closes the current instruction-level optimization pass and makes
whole-region lowering, rather than more isolated dispatch branches, the next
performance question.

A diagnostic profile of 20,000 reused renders of the Jinja text-control fixture
recorded about 5.28 million Python calls. Each render performs eight field
lookups, eight bound-method checks, four dynamic value formats, eight writer
calls, and four scope push/pop pairs. Profile timing is not a headline
benchmark, but the call structure identifies Python-level interpretation and
small output operations as the feasibility target.

## Architecture Direction

```text
template source
      |
      v
lexer -> parser -> semantic AST -> immutable generic IR
                                      |            |
                                      |            +-> generic async VM
                                      +--------------> reference sync VM
                                      |
                                      v
                             eligibility verifier
                                      |
                                      v
                         compiler-owned Python AST
                                      |
                                      v
                          immutable sync code object
                                      |
                                      v
                           generated sync renderer
```

The generic IR and VMs remain the compatibility references. Generated code is
derived only from validated internal nodes; template source, data, field names,
and function results never become Python syntax. The backend must not use
Python `eval()`, accept arbitrary Python expressions, or bypass the value
adapter, callable registry, execution budget, sandbox, HTML escapers, writer
contract, or error translation.

Unsupported programs or operations use an explicit generic fallback. Backend
selection must be immutable after template construction so one compiled
template remains safe to reuse across threads. Asynchronous rendering remains
on the generic async VM unless a later milestone provides independent evidence
for a generated async design.

## Deliverables

### Feasibility and Cost Model

- [ ] Add stable `range`-only, branch-only, lookup-only, formatting-only, and
  output-only benchmark fixtures that decompose the current text-control case.
- [ ] Record instruction counts, Python call counts, warm latency, construction
  latency, retained memory, and output operations without treating profiler
  timing as benchmark evidence.
- [ ] Define a conservative eligibility model and an amortization policy for
  construction cost, named-template associations, and generic fallback.
- [ ] Re-run the version-pinned Jinja, Mako, Chameleon, and Go comparisons on
  the retained implementation and disclose semantic capability differences.

### Generated Backend Prototype

- [ ] Lower a bounded initial subset covering literal writes, dot and field
  writes, lookup-only conditions, list and tuple ranges, lexical scopes, and
  ordinary return-string rendering.
- [ ] Preserve mapping, attribute, method, missing-key, pointer, truthiness,
  formatting, and partial-output semantics through shared audited boundaries or
  proven-equivalent specialized paths with generic fallback.
- [ ] Coalesce return-string output where profitable while retaining streaming,
  short-write, application-exception, and budget behavior for writer APIs.
- [ ] Translate generated failures to the same project exception hierarchy,
  source span, template frame, and original `__cause__` as the reference VM.
- [ ] Support associated templates, recursion limits, `break`, `continue`,
  variable binding and assignment, function calls, and contextual HTML only
  after the initial subset meets the retention gate.

### Backend Integration

- [ ] Keep backend selection private until behavior, construction-cost, and
  observability contracts are stable; do not expose compiler internals as a
  pre-1.0-style public surface.
- [ ] Preserve immutable compiled templates and independent per-render state
  under threads, recursive template calls, and concurrent writer use.
- [ ] Report the selected backend in benchmark and future debugging metadata.
- [ ] Document fallback reasons and prevent mixed generated/generic frames from
  losing source or template identity.

## Testing and Evidence

- [ ] Differentially compare generated execution with the generic sync VM for
  output, partial output, error class, stable error meaning, source position,
  template frame, cause, and execution-budget accounting.
- [ ] Run the existing Go conformance fixtures through every eligible generated
  path and keep the pinned Go oracle as the external semantic authority.
- [ ] Add property tests over nested `if`, `with`, and `range`, Unicode,
  whitespace, missing keys, value shapes, function outcomes, and writers.
- [ ] Compare generated sync output with generic async output for templates
  containing no asynchronous work.
- [ ] Cover sandboxed and unsandboxed lookup, contextual HTML/JS/CSS/URL
  escaping, hostile values, callable methods, recursion, cancellation of
  adjacent async work, and concurrent template reuse.
- [ ] Run the complete supported CPython and PyPy matrix; no generated code may
  depend on one CPython bytecode version or private interpreter ABI.

## Performance Gates

- [ ] The prototype improves median warm latency by at least 30% on
  `jinja/text-control` and one additional representative non-trivial workload
  in paired alternating samples with matching output.
- [ ] The retained implementation brings the Jinja text-control latency ratio
  to 1.35x or lower on the stable benchmark host, or records an explicit stop
  decision explaining why further backend complexity is not justified.
- [ ] Generic and ineligible workloads have no unexplained median regression
  above 2%; representative public cold construction has no unexplained
  regression above 10%.
- [ ] If generated construction exceeds the cold gate, it remains opt-in or
  behind a documented immutable selection policy until measured reuse amortizes
  the cost. Mutable first-render compilation is not an acceptable shortcut.
- [ ] Report code-object size, retained template memory, peak render memory,
  writer operation counts, and warm/cold variance alongside latency.
- [ ] No optimization is retained from a single microbenchmark or by weakening
  lookup, formatting, escaping, error, budget, or sandbox semantics.

## Non-Goals

- Replacing the generic IR or reference VMs.
- Compiling template-provided Python expressions.
- Adding Jinja syntax or changing Go template behavior to match another engine.
- Generating an async backend without separate evidence and acceptance gates.
- Requiring a native extension, compiler toolchain, platform-specific wheel, or
  private CPython bytecode API.
- Growing an open-ended catalog of benchmark-specific superinstructions.
- Continuing the closed M10 linked-IR pass before M12 is explicitly activated.

## Acceptance Gates

- [ ] The feasibility prototype meets every performance retention gate on at
  least two non-trivial workloads.
- [ ] Generated and reference backends pass output, error, source-map, partial
  writer, budget, sandbox, HTML-security, sync/async parity, property, and
  concurrency tests.
- [ ] Compiled templates remain immutable and reusable, and unsupported shapes
  fall back without observable semantic differences.
- [ ] Construction cost and retained memory are measured and covered by an
  explicit backend-selection policy.
- [ ] The full supported interpreter matrix passes without native or private-ABI
  dependencies.
- [ ] Architecture, testing, performance, debugging, and user documentation
  match the retained implementation or the recorded stop decision.
