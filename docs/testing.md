# Testing Strategy

## Development Method

Behavioral development follows red-green-refactor:

1. Select an upstream behavior or define a Python-specific requirement.
2. Add the smallest test or conformance fixture that expresses it.
3. Run the test and confirm that it fails for the intended reason.
4. Implement the minimum behavior required to pass.
5. Run the focused test and then the complete applicable suite.
6. Refactor only with all tests green.

Implementation-first compatibility changes are not complete until their test is
shown to detect the previously missing behavior. Tests should describe public
semantics rather than mirror internal implementation structure.

Use `docs/upstream-test-map.md` to select upstream suites in milestone order.

## Test Layers

### Unit Tests

Unit tests cover every token kind, grammar branch, AST node, compiler rule, VM
instruction, value adapter path, escaper, public API, and project exception.

Upstream tests are the primary source for Go and Sprig edge cases. Python-native
tests remain mandatory for behavior not represented upstream, including:

- Coroutine functions and custom awaitables.
- Cancellation propagation and cleanup.
- Async writer backpressure and partial writes.
- Task and thread reuse of compiled templates.
- Mapping, dataclass, named-tuple, property, and bound-method adaptation.
- Python exceptions raised by registered functions and writers.
- Python API validation, typing, and ergonomic error messages.
- Event-loop independence of synchronous rendering.

The current test layout is:

```text
tests/
    architecture/   dependency directions and package boundaries
    async/          asyncio, cancellation, concurrency, and async writers
    unit/           isolated Python components
    conformance/    data-driven Go and Sprig compatibility cases
    internal/       private implementation contracts
    security/       contextual escaping and adversarial inputs
    performance/    benchmark correctness and fixture validation
```

Python adaptation, public API, and Hypothesis property cases currently live in
`unit/`; fixture data lives under `tests/fixtures/`.

### Conformance Tests

Data-driven fixtures run equivalent templates and inputs through the pinned Go
oracle and gotpl. Fixtures compare output, success or failure, failure phase,
source location where available, and stable error meaning.

Each conformance fixture must identify its feature area and reference version.
Fixtures requiring Python-only values belong in a separate adaptation suite.
Where a fixture is derived from an upstream case, it must also identify the
upstream repository and source file. The centralized license status for that
metadata is defined in `docs/licensing.md`. Copyrightable upstream expression
or substantial data requires an artifact-specific notice and review before it
is committed.

### Backend Parity Tests

Templates without async work must produce the same result in the sync and async
VMs. Every later optimized backend must match the VM for output and failures.

### Property and Fuzz Tests

Hypothesis tests cover token combinations, Unicode, whitespace trimming, nested
control flow, pipelines, value shapes, and contextual escaping. The parser must
not hang, crash, or recurse without a controlled limit on arbitrary input.

### Security Tests

HTML tests include tag, attribute, URL, CSS, JavaScript, script-string, Unicode,
safe-type, malformed-markup, and cross-template context cases. A security
regression blocks release.

Sandbox tests separately cover property and method denial, custom lookup,
data-supplied callables, registry allowlists, mutation and resource-amplifying
capabilities, source size, output-before-write accounting, iteration,
function-call and associated-template depth budgets, sync/async parity, and
fresh counters on template reuse. Contextual escaping tests do not substitute
for sandbox tests, and neither substitutes for process-isolation tests in an
embedding application.

### Concurrency Tests

Tests share compiled templates across threads and asyncio tasks. Async tests
cover synchronous callbacks, coroutine callbacks, custom awaitables,
cancellation, exceptions, partial output, and writer backpressure.

## Coverage Policy

The initial repository threshold is 95% branch-aware coverage. Milestone targets
raise this to:

- At least 98% statement coverage across the repository.
- At least 95% branch coverage across the repository.
- 100% statement coverage for lexer, parser, compiler, VMs, and HTML escapers.
- Direct coverage of every public API and documented error.

Coverage thresholds must not be reduced to merge a change. High coverage does
not replace differential or security evidence.

The test gate writes a Coverage.py JSON report and runs
`scripts/check_coverage.py`. This enforces the statement and branch targets
independently from their exact covered and total counts; the rounded combined
percentage printed by `coverage report` is informational only.

## CI Matrix

The required matrix includes:

- CPython 3.11, 3.12, 3.13, and 3.14.
- CPython 3.14 as the primary development job.
- PyPy 3.11.
- Linux, macOS, and Windows.
- The exact pinned Go reference.
- Ruff, strict Pyright, a strict generated-documentation build, unit tests,
  conformance tests, and package installation.

Every supported-interpreter job also runs `scripts/check_wheel_matrix.py`. It
builds the three coordinated universal wheels, installs the project artifacts
without consulting an index or building dependencies from source, installs
only binary runtime dependencies, removes Go and compiler commands from
`PATH`, and exercises the public installation smoke test. A source-tree test
run does not substitute for this wheel check.

Preview Python and Go releases may run as non-blocking forward-compatibility
jobs. Stable releases are adopted only after the complete applicable suite
passes and pinned metadata is updated.

Full fuzz, security, and performance suites may run on dedicated or manually
requested runners, but release candidates must pass them.

Hosted jobs run only for pull requests carrying the `release` label, `v*`
release tags, or an explicit manual dispatch. Ordinary pushes and unlabeled
pull requests rely on local `scripts/check.sh` evidence and allocate no hosted
runner. The release label is retained while a candidate is under review so
synchronized commits rerun the matrix.

`mkdocs build --strict` is the documentation gate. It must resolve navigation,
internal links, and mkdocstrings objects without warnings. The hosted Pages job
builds the same source and deploys only its generated `site/` artifact.

## Bug-Fix Protocol

Every defect begins with a failing regression test at the lowest useful layer.
Compatibility defects should also gain a conformance fixture. Performance
defects should gain a benchmark case when reproducible.

The regression test must be observed failing before the fix. The pull request or
change record should state the failure and the suite that proves the fix.
