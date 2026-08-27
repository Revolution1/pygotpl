# M5 Contextual HTML Acceptance Audit

## Scope

This audit maps the pinned Go 1.27.0 `html/template` behavior families to
current pygotpl evidence. It distinguishes the M5 contextual engine from later
work on mutable Go-style template-set APIs. A passing narrow test is not treated
as proof for an entire upstream file.

Status values are `covered`, `partial`, `inherited`, and `deferred`.

## Contextual Engine Matrix

| Upstream behavior family | Status | Current evidence |
| --- | --- | --- |
| `escape_test.go:TestEscape` | covered | Go-oracle fixtures cover HTML text, comments, RCDATA, attributes, URL, meta refresh, CSS, JavaScript, `srcset`, dynamic and partial names, doctypes, trusted content, predefined escapers, conditional valueless attributes, and loop control. |
| `escape_test.go:TestEscapeMap` | covered | Fields named `html` and `urlquery` remain ordinary operands when piped to `print`; the predefined-escaper fixture executes both cases through Go and Python. |
| `escape_test.go:TestEscapeSet` | covered | Context-specialized named calls, direct and mutual recursion, JavaScript recursion, and fixed-point failures have differential fixtures. |
| `escape_test.go:TestErrors` | covered | Ambiguous branches, range re-entry and early exits, URL/CSS/JS ambiguity, malformed attribute names and values, non-text roots, recursive-context failure, and predefined-escaper misuse are covered. Python asserts stable semantic diagnostics; fixtures retain exact pinned-Go messages without claiming identical wording where the compatibility contract does not require it. |
| `escape_test.go:TestEscapeText` | covered | Unit and differential tests cover tag/attribute transitions, partially completed names, nudged branch joins, entities in active attributes, namespace attributes, ASCII tag names, invalid less-than text, doctypes, comments, special-element boundaries, nested JavaScript template literals, and CSS URL transitions. |
| `escape_test.go:TestEnsurePipelineContains` | covered | Equivalent `html`/`urlquery` merging, direct multi-argument calls, URL-filter ordering, idempotent internal escapers, and redundant terminal escapers are tested. |
| `html_test.go` | covered | Quoted/unquoted replacement tables and trusted-HTML tag stripping have direct tests with complete escaper branch coverage. |
| `url_test.go` | covered | URL filtering, normalization, query escaping, byte/Unicode edges, and per-candidate `srcset` filtering have direct and differential tests. |
| `css_test.go` | covered | CSS decoding, keyword/name helpers, strings, URL states, comments, obfuscated active values, and filter boundaries have direct and differential tests. |
| `js_test.go` | covered | Value JSON encoding, strings, template literals, regular expressions, slash context, MIME types, comments, Unicode, map order, cycles, and encoding failures are covered. |
| `content_test.go:TestTypedContent` | covered | All seven Go-compatible trusted types have matching-context and cross-context tests, including async returns. |
| `transition_test.go:TestFindEndTag` | covered | Script/style/RCDATA boundary separators, false prefixes, mixed case, Unicode-before-marker indexing, and literal rewriting are directly tested. |
| Auxiliary escape regressions | covered | Malformed pipelines and undefined calls are inherited from the parser/runtime gates; pre-output escape failure, repeat execution, indirect methods, and incomplete named roots have direct HTML API, writer, or concurrency evidence. |
| `exec_test.go` text execution semantics | inherited | M1-M3 text parser, VM, errors, formatting, control flow, and async parity apply unchanged before contextual escapers are appended. |
| Concurrent execution and race resistance | covered | A shared compiled `HTMLTemplate` is rendered concurrently across threads and asyncio tasks with context-sensitive outputs. |

## Public API Matrix

| Capability | Status | Notes |
| --- | --- | --- |
| Reusable sync and async root rendering | covered | String and writer APIs use one analyzed immutable program. |
| Direct named-template execution | covered | Sync, async, and writer variants analyze names from text context and reject incomplete roots before output. |
| Contextual named-template calls | covered | Definitions are specialized by incoming context and may safely remain non-text fragments when called from an enclosing template. |
| Custom delimiters, functions, missing-key mode, and format mode | inherited | The HTML API delegates parsing and runtime policy to the text-template implementation. |
| Go `Clone`, post-parse redefinition, `AddParseTree`, `ParseFiles`, `ParseGlob`, and `ParseFS` | deferred | pygotpl currently exposes an immutable constructor API. The eventual Python API and observable compatibility policy require an M10 decision rather than an implicit M5 claim. |

M10 decision D013 resolves this deferred row. `HTMLTemplate.from_sources`,
`with_source`, `render_source`, and `render_source_async` preserve multi-source
association and contextual-rewrite behavior through immutable objects. Mutable
Go construction methods and application-owned file/glob discovery are a
documented Python API difference.

## Security and Performance Gates

- The dedicated HTML security corpus has no skipped cases.
- The HTML analyzer and escaper package has 100% statement and branch coverage.
- Trusted types cannot bypass unrelated contexts.
- The differential warm-render benchmark compares identical output digests and
  records seven-sample latency distributions against Go.
- Shared compiled HTML templates have explicit thread and asyncio concurrency
  tests.

## Frozen M5 Acceptance

M5 was frozen on August 26, 2026 with 33 pinned-Go contextual fixtures, 86
security cases, and 184 focused HTML tests. The final project gate passed 1,138
tests and reported 7,480 statements with zero misses. The analyzer and escaper
package retained 100% statement and branch coverage, and the checked HTML
benchmark produced identical Go and Python output digests.

Mutable template-set APIs remain assigned to M10. This deferral concerns public
construction and mutation ergonomics, not contextual escaping or execution
safety. Future compatibility defects reopen the M5 gate and require a failing
Go-derived regression fixture before release.
