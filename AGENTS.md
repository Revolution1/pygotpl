# Agent Instructions

## Project Mission

The `pygotpl` repository publishes `gotpl`, a pure Python implementation of
Go's `text/template` and `html/template`, plus the standalone `goduration` and
`gotime` value packages. Runtime use must not require Go, a subprocess, or a
compiled extension.

Sprig, Slim-Sprig, Sprout, Helm, and other ecosystem layers are explicit
opt-in registries in `gotpl`. They must not alter the default Go compatibility
path or one another's named compatibility paths.

Correctness means observable compatibility with the pinned Go and Sprig
references. Similar-looking behavior is not sufficient.

## Sources of Truth

Use these sources in descending order of authority:

1. The pinned Go standard-library source and tests.
2. The pinned Sprig source and tests.
3. The pinned Slim-Sprig, Sprout, or Helm source and tests for their named
   profiles.
4. The pinned Go `time` source and tests for `goduration.go` and `gotime.go`.
5. The repository's differential conformance fixtures.
6. The public compatibility contract in `docs/compatibility.md`.
7. Project documentation and examples.

When sources disagree, preserve the reference implementation's observable
behavior and document the decision. Never silently normalize a Go behavior into
a more idiomatic Python behavior on a compatibility path.

## Required Reading

Before changing behavior, read the relevant documents:

- `docs/architecture.md` for module and execution boundaries.
- `docs/compatibility.md` for the compatibility contract.
- `docs/testing.md` for required evidence.
- `docs/performance.md` for benchmark rules.
- `docs/dependencies.md` for toolchain and upgrade policy.
- `docs/references.md` for pinned upstream source handling.
- `docs/extraction-candidates.md` before creating reusable Go-compatibility
  package boundaries.
- `docs/sprig-security.md` before changing Sprig capabilities, non-hermetic
  profiles, cryptography, environment access, DNS, regex, or mutation.
- The active file under `docs/milestones/` for current scope and exit gates.

Update the documents in the same change when a decision, public behavior,
milestone scope, or compatibility status changes.

## Architecture Rules

- Keep lexing, parsing, semantic analysis, compilation, and execution separate.
- Treat the AST as a diagnostic and semantic representation, not the permanent
  hot-path execution format.
- Compile templates to a compact, immutable instruction representation.
- Maintain separate synchronous and asynchronous execution paths.
- Do not route synchronous rendering through an event loop.
- Synchronous rendering must raise `AsyncRequiredError` if a function returns an
  awaitable.
- Asynchronous rendering may call both synchronous and asynchronous functions
  and must await each pipeline result before continuing.
- Do not use Python `eval()` to execute template expressions.
- Keep `text/template` independent of HTML escaping and Sprig.
- Implement `html/template` escaping as contextual analysis and rewriting, not
  as escaping of the final rendered string.
- Keep built-in, compatibility-library, and Python-native function namespaces
  separate.
- Keep Python-native helpers under `gotpl.pythonic` in an explicit extension
  registry. `reMatch` uses
  Python `re` semantics and must never replace Sprig's `regexMatch`.
- Keep Sprig, Slim-Sprig, Sprout, and Helm registries under `gotpl.funcs`,
  explicit, and independently
  auditable; never inject them into a default registry.
- Keep sandboxing opt-in so default field and method behavior remains Go
  compatible. Template source must never mutate parsing, extension, or security
  policy.
- Keep heavyweight or specialized integration dependencies optional and lazily
  imported. Core imports and rendering must work without extras installed.
- Keep extracted workspace packages independent of gotpl internals. They may
  expose standalone Go-compatibility primitives but must not import the AST,
  compiler, VM, sentinels, or function registries.
- Parsed templates must be safe to reuse across threads and asyncio tasks.
- Keep incomplete formatting and RE2-compatible support private under
  `gotpl._compat`; do not expose them as independent product APIs.

## Compatibility Workflow

For every compatibility behavior:

1. Add or identify a reference case.
2. Run it against the pinned Go oracle.
3. Add the expected result to a conformance fixture.
4. Implement the behavior.
5. Test both success and failure paths.
6. Record intentional differences in `docs/compatibility.md`.

Do not claim support based only on unit tests written from memory. Do not mark a
milestone complete while a required conformance gate is skipped.

## Testing Rules

- Use test-driven development for behavioral work: write or select a failing
  test, confirm the failure, implement the smallest compatible change, and then
  refactor with the suite green.
- For Go or Sprig compatibility, begin with the relevant upstream test and
  implementation in `.references/`, then express the behavior in this
  repository's fixture or test format before implementation.
- Confirm that a new test fails for the intended reason. A test that passes
  before the behavior exists is not evidence for the change.
- Every bug fix requires a regression test.
- Every public API requires direct tests.
- Every parser branch and VM instruction requires tests.
- Test output, error phase, source position, and stable error meaning where the
  Go reference exposes them.
- Compare the sync and async executors for templates that contain no async work.
- Compare every optimized backend against the reference VM.
- Use property-based tests for parser robustness, Unicode, nested control flow,
  and value-shape variation.
- Treat contextual escaping and security regressions as release blockers.
- Do not lower coverage thresholds to make a change pass.
- Upstream-derived coverage is not enough. Add Python-native tests for asyncio,
  cancellation, Python value adaptation, exceptions, writers, concurrency, and
  public API ergonomics.

See `docs/testing.md` for the full matrix and commands.

## Performance Rules

- Preserve a correctness baseline before optimizing.
- Benchmark with checked-in fixtures shared by Python and Go.
- Report parse, compile, cold render, and warm render separately.
- Keep synchronous hot paths free of unconditional coroutine machinery.
- Include allocation and memory measurements where practical.
- Never replace compatible behavior with a benchmark-specific shortcut.
- Add a benchmark when changing a hot path or claiming a performance win.

See `docs/performance.md` for methodology and regression thresholds.

## Public API Rules

- Prefer a small Pythonic API: `render`, `render_async`, `Template`, and
  `HTMLTemplate`.
- Keep compiled templates reusable and immutable from a caller's perspective.
- Use explicit APIs for text and HTML templates.
- Raise project-specific exceptions with actionable messages.
- Avoid exposing parser or VM internals as stable API before 1.0.
- Add API aliases only when they have a concrete compatibility or usability
  benefit.

## Change Discipline

- Work within the active milestone unless a prerequisite must be fixed.
- Keep changes narrow and independently testable.
- Do not combine semantic changes with unrelated formatting or refactoring.
- Preserve user changes and inspect the working tree before editing.
- Prefer standard-library dependencies in the core; justify every runtime
  dependency in an architecture decision record.
- Prefer current stable language, packaging, tooling, and dependency standards.
  Keep development dependencies locked, and validate upgrades with the full
  applicable test and benchmark suites.
- Do not commit generated benchmark results, caches, coverage data, or build
  artifacts unless a document explicitly requires a checked-in snapshot.
- Never commit `.references/` or files copied from it without an explicit
  license and attribution review.

## Milestone Completion

A milestone is complete only when:

- All deliverables and acceptance gates in its document are satisfied.
- Required tests pass on the supported Python matrix.
- Compatibility and performance evidence has been recorded.
- User-facing documentation matches the implementation.
- Known gaps are explicit and assigned to a later milestone.
