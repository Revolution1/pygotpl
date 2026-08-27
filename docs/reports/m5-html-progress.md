# M5 Contextual HTML Progress

## Status

M5 is complete. The frozen reference-derived implementation provides contextual
instruction rewriting for ordinary HTML text, `title` and `textarea` RCDATA,
quoted attributes, unquoted attributes, HTML comments, URL attributes,
JavaScript and CSS contexts, `srcset`, dynamic names, and trusted content.

## Reference Evidence

The `html/basic-contexts` fixture is derived from Go 1.27.0
`html/template`'s `TestEscape` behavior family and the HTML escaper tests. It
executes through the pinned Go oracle and Python implementation. The fixture
also places actions inside `if` and `range` bodies so the first slice proves
that ordinary control flow does not bypass escaping.

The `html/url-contexts` fixture covers standard URL attribute names,
`data-*` normalization, XML namespaces, custom-name URL heuristics, relative
and absolute URLs, unsafe schemes, path continuation, query insertion, and
unquoted values. URL starts pass through the Go-compatible protocol filter and
normalizer; query and fragment insertions use the stricter URL escaper before
the enclosing HTML attribute escaper.

The `html/url-branch` and `html/url-ambiguous-failure` fixtures cover
control-flow joining. The analyzer propagates contexts over the immutable IR's
branch, `with`, range, loop, and jump edges until it reaches a fixed point.
Equivalent branch endpoints join normally; pre-query and query URL endpoints
join to an explicit unknown URL part that rejects a following action. Other
state disagreements fail closed as different HTML contexts.

The `html/template-contexts` and `html/template-recursive` fixtures cover
named-template analysis. Each callee is specialized for its incoming HTML
context, and its output context is propagated back to the caller. Analysis
iterates all discovered variants to a global fixed point, allowing direct and
mutual recursion without treating a named template as an isolated text
fragment. A single helper can therefore be used safely in both URL and HTML
text contexts, including a helper that moves a URL from path to query state.

Five `html/js-*` fixtures cover JavaScript expression values, quoted strings,
regular expressions, template literals and interpolation, block and line
comments, script MIME-type classification, quoted and unquoted event
attributes, ambiguous slash rejection, and recursive named templates in a
JavaScript value context. JavaScript values use Go-compatible compact JSON,
HTML-sensitive JSON escapes, identifier padding, deterministic map-key order,
and safe `null` comments for values that cannot be encoded. Event handlers are
HTML-entity decoded for lexical analysis before their original source is
preserved, then receive the required attribute escaper after the JavaScript
escaper.

Literal `<script`, `</script`, and `<!--` markers inside JavaScript strings,
regular expressions, and template literals are neutralized with `\x3C`.
Comments in script bodies are removed without accidentally joining tokens or
discarding significant line terminators. Control-flow joins preserve an
explicit unknown slash context and reject only if a later slash needs the
ambiguous decision.

Three `html/css-*` fixtures cover filtered CSS values, quoted strings, quoted
and unquoted `url(...)` forms, path and query escaping, unsafe protocol
filtering, style elements and attributes, comment elision, and ambiguous URL
joins. The CSS decoder follows Go's one-to-six-digit escape and optional
whitespace rules before the value filter checks token-boundary characters,
legacy `expression` payloads, and Mozilla bindings. Literal CSS string output
uses hexadecimal CSS escapes and receives a final HTML attribute escaper only
inside a style attribute.

The `html/srcset-contexts` fixture covers complete dynamic lists, individual
candidates, descriptors, unsafe-protocol filtering, repeated commas, and URL
values embedded in a source set. Non-URL values are filtered candidate by
candidate, while an explicit trusted `Srcset` can represent a complete source
set and an explicit trusted `URL` still receives the comma normalization Go
requires in this context.

The `html/trusted-content` fixture covers the seven Go-compatible trusted
string types: `CSS`, `HTML`, `HTMLAttr`, `JS`, `JSStr`, `URL`, and `Srcset`.
Each type bypasses only the matching contextual filter; cross-context use is
escaped or rejected like an ordinary string. Trusted HTML is stripped to text
inside attributes, and trusted URL values still receive context-specific
normalization. Dynamic element and attribute names use a dedicated name
filter, while active or malformed attribute names fail closed.

The analyzer tracks literal HTML state across instruction boundaries and
rewrites each dynamic output pipeline with an internal context-specific
escaper. HTML comments are removed during analysis. Rendering therefore does
not escape the final document as one string.

## Python API Evidence

`HTMLTemplate` provides reusable synchronous and asynchronous rendering plus
writer-based variants. `render_html`, `render_html_to`, `render_html_async`,
and `render_html_async_to` provide one-shot equivalents. Async functions are
awaited before their results pass through the selected contextual escaper.

Associated definitions support `render_template`, `render_template_to`,
`render_template_async`, and `render_template_async_to`. Each named template is
analyzed from HTML text context before direct execution; definitions that are
valid only as contextual fragments fail before writing partial output.

The internal escaper names are installed after caller functions and cannot be
overridden accidentally. Text templates remain independent of the HTML
package and continue to use the unchanged execution path.

Trailing predefined `html` and `urlquery` commands merge with contextual
escapers using Go's equivalence and redundancy rules. Dangerous URL schemes
are filtered before `urlquery` can obscure their colon, direct multi-argument
escaper calls retain Go `fmt.Sprint` spacing, and predefined escapers in unsafe
pipeline positions are rejected.

Static `srcdoc` values follow Go's ordinary quoted or unquoted attribute
escaping, including tag stripping for a trusted `HTML` value. A dynamically
generated `srcdoc` attribute name remains filtered because its content type can
change document structure.

Conditional valueless attributes use Go-compatible nudged context joins, so an
empty branch and a branch ending after an attribute name can safely converge.
Partially dynamic attribute names retain the semantic class established by
their static prefix; for example, `on{{.Suffix}}` keeps a JavaScript value
context. Differential range fixtures also cover compatible loop re-entry plus
fail-closed `break` and `continue` paths.

## Verification Snapshot

Focused tests cover all thirty-three Go fixtures, public sync and async APIs,
comment state across literal chunks, RCDATA closing tags, attribute delimiter
transitions, nil and missing values, NUL replacement, every initial
unquoted-attribute control replacement, URL byte normalization,
unsafe-protocol rejection, JavaScript token-state transitions, JSON boundaries
and cycles, entity-decoded event handlers, async structured JavaScript values,
CSS escape decoding, value-filter attacks, URL transitions, entity-decoded
style attributes, async CSS values, source-set candidate filtering, trusted
content boundaries, and async trusted values. The HTML analyzer and escaper
package reports 100% statement and branch coverage for this slice.

The dedicated security corpus contains 86 collected cases with no skips. It
covers fail-closed ambiguous states, complete dynamic tag structure
preservation, the complete Go unsafe dynamic-attribute classification, CSS
escape obfuscation, source-set candidate isolation, meta-refresh URL filtering,
trusted-value cross-context isolation, malformed unquoted attributes, and root
templates that end in a non-text context. It also covers predefined-escaper
placement, double-escaping prevention, URL-filter ordering, and malformed
attribute names. Representative security failures also execute through the
pinned Go oracle.

The shared contextual HTML benchmark verifies identical rendered-output
digests before comparing timings. Seven samples on the recorded Apple M5
environment measured a 149,061 ns/op Python median and a 14,248 ns/op Go
median, or 10.45x. The full methodology, raw paired ratios, variance, and
limitations are recorded in
[`m5-html-performance.md`](m5-html-performance.md).

The August 26, 2026 full-project gate passes 1,138 tests. Coverage reports 7,480
statements with zero misses and 99% total branch-aware coverage. The focused
HTML gate passes 184 tests with 100% statement and branch coverage. Ruff lint
and format checks, strict Pyright, the Go oracle module test, and the refreshed
dependency lock also pass.

## Next Milestone

M6 starts with a representative benchmark inventory and profile-guided
measurement of the immutable VM and value-adapter hot paths. The frozen M5
fixtures, security corpus, and output digest remain mandatory correctness gates
for every optimization.
