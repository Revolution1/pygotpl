# M7 Specialized Instruction Design and Prototype

## Decision

M7 does not retain a production specialized instruction. A complete
`WRITE_FIELD` prototype preserved output and improved one representative
workload, but it did not improve two. The production compiler and both VMs were
returned to the reference instruction set after measurement.

This is a useful framework result rather than a failed implementation task:
isolating only the final field write adds another opcode check to every VM
iteration, while most real cost remains in control pipelines, lookup policy,
formatting, calls, and HTML escaping. A future specialization should fuse a
coherent family of shapes and use a dispatch organization that does not tax
unrelated instructions.

## Candidate Instruction Families

Specialization remains an immutable compile/link-time transformation. The AST
continues to represent source meaning, the existing generic IR remains the
reference backend, and specialized payloads retain `source_start` for error
attribution.

| Family | Immutable payload | Work removed at render time | Required fallback |
| --- | --- | --- | --- |
| Operand | literal value or pre-split field/variable path | operand-kind dispatch and repeated shape checks | generic `Operand` evaluation |
| Lookup/control | field path plus branch/range targets | generic single-command pipeline, argument list, truth/range setup | `ValueAdapter` for mappings, descriptors, methods, and missing policy |
| Callable | prepared registry slot plus fixed operand tuple | function-name lookup and call-spec lookup | generic registry lookup when callers may replace a name |
| Formatting | known value source plus immutable Go/Python format plan | pipeline boundary and repeated directive/format selection | generic `format_value`/`sprintf` for dynamic values and modes |
| HTML context | value source plus ordered immutable escape plan | reconstruction and repeated context-to-escaper selection | current contextual rewritten pipeline |

The appropriate boundary is likely a linked program owned by a `Template`, not
more parser knowledge. Parsing and semantic validation do not know the final
callable registry, formatting mode, missing-key policy, or HTML context. A link
step may derive specialized instructions from the generic immutable `Program`
after those policies are fixed, while keeping the generic program for parity
tests and diagnostics.

No specialized instruction may bypass:

- exported-field and method invocation rules;
- missing-key `default`, `zero`, and `error` behavior;
- `FunctionResult`, arity, exception, and awaitable handling;
- sync `AsyncRequiredError` and async awaiting;
- Go versus Python formatting selection;
- HTML trusted-content classification and contextual escaping; or
- instruction source positions and named-template attribution.

## Measured Prototype

The prototype added an immutable `WRITE_FIELD(fields)` instruction for an
output action containing exactly one field operand and no bindings or pipeline.
The compiler emitted it, the sync VM performed direct `ValueAdapter` lookup and
final bound-method invocation, and the async VM used its await-aware lookup and
call path. HTML contextual analysis converted it back to an escaped generic
pipeline because escaping semantics take precedence over this isolated
specialization.

The test was developed from a failing compiler-IR assertion. Compiler, sync,
async, HTML, invalid-instruction, and public rendering tests passed before
benchmarking. Both benchmark output hashes were identical before and after.

Eleven samples on CPython 3.14.7, Go 1.27.0, macOS arm64:

| Workload | Generic median ns/render | Prototype median ns/render | Change | Generic RSD | Prototype RSD |
| --- | ---: | ---: | ---: | ---: | ---: |
| Text control | 15,811 | 15,821 | +0.07% | 2.05% | 1.17% |
| Large named templates | 25,867 | 25,471 | -1.53% | 2.46% | 1.31% |

The named-template change is small but directionally plausible because its
last template writes a plain field. Text/control contains two plain field
writes, yet the extra dispatch branch cancels their local saving. Neither
result is large enough to establish a broadly useful optimization, and only
one moves in the favorable direction. The M7 retention gate therefore rejects
the instruction.

## Next Experiment Gate

A future experiment should prototype the operand, lookup/control, and prepared
call families together, preferably through a separate linked-instruction
dispatcher so generic instructions do not each pay additional sequential
branches. It should target at least text/control and contextual HTML, with
Sprig and named-template workloads as regression controls.

Production adoption requires all of the following:

1. generic-VM output, errors, positions, sync, and async parity;
2. contextual HTML and security suites remain green;
3. a checked-in benchmark that exercises the specialized shapes;
4. statistically credible median improvement on at least two representative
   non-trivial workloads;
5. no unexplained regression above 5% elsewhere; and
6. memory and compile/link overhead reported separately from warm rendering.

The original reference commands were:

```console
uv run --frozen python -m benchmarks.compare \
  benchmarks/fixtures/text_render.json --samples 11
uv run --frozen python -m benchmarks.compare \
  benchmarks/fixtures/named_large_render.json --samples 11
```

The measured prototype is intentionally not left behind as dormant production
code or an unsupported execution mode.
