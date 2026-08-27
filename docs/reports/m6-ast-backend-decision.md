# M6 Python-AST Backend Decision

## Decision

M6 retains the instruction VM as the only production backend. A Python-AST
code-generation backend is not justified by the measured opportunity after the
retained VM optimizations. This is a reviewable decision, not a permanent ban.

## Evidence

`python -m benchmarks.backend_feasibility` profiles the same prepared public
operation as the shared timing and memory runners. It then makes the deliberately
unrealistic assumption that all self time in the synchronous VM dispatcher can
disappear while every semantic helper becomes free to call from generated code.
The resulting Amdahl value is therefore an upper bound, not a predicted AST
speedup.

The final August 26, 2026 run used CPython 3.14.7 on macOS 26.5.2 arm64:

| Workload | Dispatcher self-time share | Impossible dispatch-only upper bound |
| --- | ---: | ---: |
| Literal render | 29.80% | 1.424x |
| Text control render | 19.83% | 1.247x |
| Contextual HTML render | 5.89% | 1.063x |
| Large named-template render | 39.18% | 1.644x |

The complex HTML workload is dominated by compatibility and security helpers,
not opcode dispatch. The text workload has at most a 24.7% dispatch-only
opportunity before accounting for generated control flow. Literal and named
templates expose a larger fraction, but their absolute latency is already low,
and a recursively generated named-template implementation would regress the
tested Go-compatible 100,000-call depth behavior.

## Maintenance Cost

A production backend would need all of the following before it could be used by
default or offered as a supported option:

- identical sync and async semantics, including immediate and scheduled
  awaitables, cancellation, and async writer backpressure;
- the same lazy explicit caller stack and Go template-depth diagnostic;
- exact variable declaration, assignment, dot, range, break, and continue
  behavior;
- short-write detection and identical partial-output behavior on failures;
- innermost UTF-8 source locations and exception chaining;
- contextual HTML rewrites and security tests with no generated-code bypass;
- backend parity for every frozen text, HTML, Sprig, Slim-Sprig, and Python
  adaptation fixture; and
- bounded code size, construction latency, cache growth, and thread safety.

Duplicating or inlining semantic helpers to exceed the measured dispatcher
upper bound would create a second compatibility implementation, not merely a
backend. The current evidence does not pay for that risk.

## Reconsideration Gates

Reopen the decision only when at least one of these conditions is met:

1. dispatcher self time exceeds 35% in two representative non-literal
   workloads after VM profiling and ordinary specialization are exhausted;
2. a full-instruction prototype demonstrates at least a 25% median end-to-end
   improvement on both text control and contextual HTML with matching outputs;
3. a supported Python release adds a code-generation facility that materially
   lowers the parity and source-mapping cost; or
4. stable release benchmarks show that the VM cannot meet an adopted latency
   budget despite profile-guided optimization.

Any reopened prototype must be checked in as a benchmark first. It cannot
become a production backend until the complete backend-parity and security
gates pass.
