# Upstream Test Map

## Purpose

This map turns the ignored upstream test repositories into a milestone-ordered
TDD backlog. It identifies where behavior should be studied; it does not grant
permission to copy upstream material without license and attribution review.

## M1: Lexer and Parser

Primary tests:

- Go `src/text/template/parse/lex_test.go`
- Go `src/text/template/parse/parse_test.go`

Primary implementation references:

- Go `src/text/template/parse/lex.go`
- Go `src/text/template/parse/parse.go`
- Go `src/text/template/parse/node.go`

Translate one grammar family at a time. Start with plain text and empty input,
then actions and literals, pipelines, variables and fields, control structures,
template definitions, whitespace trimming, custom delimiters, and invalid
syntax. Every family needs success, boundary, and diagnostic cases before its
implementation.

Python companion tests cover arbitrary Unicode strings, controlled nesting
limits, immutable node behavior, stable source spans, and parser non-hanging
properties.

## M2: Synchronous Text Execution

Primary tests:

- Go `src/text/template/exec_test.go`
- Go `src/text/template/multi_test.go`
- Go `src/text/template/examplefunc_test.go`
- Go `src/text/template/examplefiles_test.go`
- Go `src/text/template/link_test.go`

Supporting implementation references:

- Go `src/text/template/exec.go`
- Go `src/text/template/funcs.go`
- Go `src/text/template/template.go`
- Go `src/text/template/helper.go`
- Go `src/text/template/option.go`

Prioritize dot and root behavior, variable scope, truthiness, field and map
lookup, pipeline argument ordering, built-ins, iteration, template association,
missing-key modes, errors, and writer failures.

Python companion tests cover mappings, dataclasses, named tuples, properties,
bound methods, large integers, mixed-key dictionaries, private attributes,
thread reuse, exceptions, and Python writer protocols.

## M3: Async Execution

There is no Go upstream equivalent. Derive the expected synchronous semantics
from `text/template` execution tests, then run each applicable case through both
VMs.

Python-native tests must cover coroutine functions at every pipeline position,
synchronous functions returning custom awaitables, conditions and ranges fed by
awaitables, cancellation, cleanup, context-variable propagation, task reuse,
writer backpressure, partial output, and rejection by the synchronous API.

## M4: Sprig

Primary tests are the top-level `*_test.go` files in `.references/sprig`, grouped
with their matching implementation files:

- `strings`, `numeric`, `list`, `dict`, `defaults`, and `reflect`
- `regex`, `url`, `date`, `semver`, `crypto`, and `network`
- `functions_test.go` for registry composition and aliases
- `flow_control_test.go` and issue regression tests
- Platform-specific function tests

Inventory every public function from `functions.go` before implementation.
Each function begins with reference-derived normal, boundary, invalid-input, and
pipeline-order cases where applicable. Non-hermetic functions also require
Python tests for injected time, entropy, environment, network isolation, and
async interaction.

Slim-Sprig `v3.0.0` is tested as an independently inventoried registry profile
against `.references/slim-sprig/functions.go` and its top-level tests. Shared
function behavior reuses Sprig conformance evidence only after the two pinned
references are shown to agree; profile membership and omissions have direct
tests.

## M8: Ecosystem Integrations

Sprout work starts from each package under `.references/sprout/registry`, then
its `all` and `hermetic` groups. Inventory names, aliases, notices, and safe
function classifications before translating registry tests. Reuse a Sprig
implementation only when differential fixtures prove identical behavior at the
pinned versions.

Helm fixtures begin with public Helm chart behavior for `include`, `required`,
`tpl`, YAML helpers, lookup isolation, chart globals, and named-template
association. The miniature Python Helm CLI is an example and end-to-end test
harness, not a claim of full Helm command compatibility.

## M5: Contextual HTML Escaping

Primary tests:

- Go `src/html/template/escape_test.go`
- Go `src/html/template/transition_test.go`
- Go `src/html/template/html_test.go`
- Go `src/html/template/js_test.go`
- Go `src/html/template/css_test.go`
- Go `src/html/template/url_test.go`
- Go `src/html/template/content_test.go`
- Go `src/html/template/template_test.go`
- Go `src/html/template/exec_test.go`
- Go `src/html/template/multi_test.go`
- Go `src/html/template/clone_test.go`

Primary implementation references are the corresponding context, transition,
escape, HTML, JavaScript, CSS, URL, content, and template source files.

Implement by context family with a failing security or conformance case first.
Python companion tests add modern attack payloads, malformed Unicode, custom
awaitables returning trusted types, async template calls, cancellation during
escaped writes, and backend parity.

## M7: Extracted Go Compatibility Packages

`gotime` uses Go 1.27 `src/time` as its primary specification:

- `time_test.go` for instants, civil accessors, Unix units, calendar
  normalization, arithmetic, rounding, serialization, and zone behavior;
- `format_test.go` for every layout token, parsing, formatting, fractional
  seconds, time-zone offsets, and structured errors;
- `zoneinfo_test.go` and platform zone tests for TZif loading, validation,
  historical transitions, and local-location rules;
- `mono_test.go` for monotonic-clock comparison and arithmetic rules; and
- `sleep_test.go` and `tick_test.go` for scheduling semantics that have an
  honest Python equivalent.

The standalone package also has Python-specific tests for `datetime`, `date`,
`time`, `timedelta`, `tzinfo`, `zoneinfo`, serialization protocols, injected
clocks, threading, asyncio cancellation, deadlines, and async iteration. See
`packages/gotime/docs/api-scope.md` for the complete API ledger.

## Fixture Traceability

Every reference-derived conformance fixture should record:

- Reference project and exact revision.
- Upstream source file and test name or behavior group.
- Template source, input schema, options, and function registry profile.
- Expected output or expected failure phase.
- Whether wording and source positions are strict or semantic comparisons.
- License and attribution status.

The first implementation commit for a fixture must demonstrate that the fixture
was red before the production change and green afterward.
