# M5: Contextual HTML Templates

## Outcome

Provide contextual escaping and rejection behavior compatible with the targeted
Go `html/template` implementation.

## Deliverables

- [x] HTML context state model and analyzer.
- [x] Context propagation through branches and template calls.
- [x] Context-specific escaping instruction rewriting.
- [x] HTML, attribute, URL, CSS, JavaScript, and `srcset` handling.
- [x] Trusted content wrapper types.
- [x] Unsafe protocol filtering and ambiguous-context errors.
- [x] Public `HTMLTemplate` API.
- [x] Dedicated security corpus and HTML performance benchmarks.

## Acceptance Gates

- [x] Required `html/template` conformance fixtures match Go 1.27.0.
- [x] Security corpus passes with no skipped release-blocking case.
- [x] Analyzer and escapers reach 100% statement coverage.
- [x] Trusted types cannot accidentally bypass unrelated contexts.
- [x] Cross-template contexts are analyzed consistently.
- [x] A Go/Python HTML performance report is recorded.

## Non-Goals

- Sanitizing complete untrusted HTML documents.
- Treating final-string HTML escaping as contextual compatibility.

See the [M5 acceptance audit](../reports/m5-acceptance-audit.md) for contextual,
security, API, coverage, and performance evidence.
