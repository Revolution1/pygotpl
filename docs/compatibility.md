# Compatibility Contract

## Reference Versions

The initial target is:

- Go `1.27.x` for `text/template` and `html/template`.
- Sprig `v3.3.0`.
- Slim-Sprig `v3.0.0` for its reduced function-map profile.
- Sprout `v1.1.1` for opt-in registry compatibility.
- Helm `v4.2.3` for opt-in chart-template compatibility.
- Python `3.11` and newer.

Exact patch versions used by CI will be pinned in the Go oracle module and the
CI configuration. A reference upgrade is a deliberate compatibility change and
requires a conformance report.

Local source and test checkouts are pinned and managed as described in
`docs/references.md`. They are ignored by Git and are not runtime dependencies.

## Meaning of Compatibility

Compatibility covers observable template behavior:

- Parsing success or failure.
- Rendered output.
- Variable scope and dot movement.
- Pipeline evaluation and function argument order.
- Truthiness, comparison, iteration, and missing values.
- Named-template association and invocation.
- Contextual HTML escaping and unsafe-context rejection.
- Sprig function names, inputs, results, and error variants.
- Error phase, useful source position, and stable semantic meaning.

Exact error wording is required only where fixtures declare it stable. Python
object behavior with no Go equivalent must follow the Python adaptation rules
and be reported separately from Go-compatible cases.

## Runtime Independence

Installing and using the package must not require Go, a Go shared library, a
subprocess, or a compiled Python extension. Go is permitted in development and
CI as a reference oracle and benchmark target.

## Compatibility Matrix

Status values are `planned`, `partial`, `compatible`, and `documented-difference`.

| Area | Reference | Status | Target milestone |
| --- | --- | --- | --- |
| Lexer and parser | Go 1.27.x | compatible (197 oracle cases) | M1 |
| Sync `text/template` | Go 1.27.x | partial (68 oracle fixtures; M2 scope complete) | M2 |
| Async function execution | Project extension | compatible (68 sync-parity fixtures) | M3 |
| Sprig generic/text maps | Sprig 3.3.0 | compatible (211-function strict evidence ledger) | M4 |
| Sprig hermetic maps | Sprig 3.3.0 | compatible (194 names; exact 17-name exclusion) | M4 |
| Slim-Sprig generic/text maps | Slim-Sprig 3.0.0 | compatible (164-name differential matrix) | M4 |
| Slim-Sprig hermetic maps | Slim-Sprig 3.0.0 | compatible (153 names; pinned-fork matrix) | M4 |
| `html/template` | Go 1.27.x | partial (M5 contextual engine complete; 34 oracle fixtures) | M5 |
| Optimized backend decision | Python VM | compatible; AST backend not justified by M6 evidence | M6 |
| Sprout registries | Sprout 1.1.1 | compatible M8 raw registry/group scope (234-function evidence ledger; safe generation excluded) | M8 |
| Helm functions and example runtime | Helm 4.2.3 | compatible example scope (10 oracle integration cases) | M8 |

Sprig's only function-name intersection with the Go template built-ins is
`slice`. This is the same intentional override installed by Sprig v3.3.0;
pygotpl registry tests reject any additional accidental built-in collision.

The table must be updated with measured conformance counts as implementation
lands. A feature is not `compatible` while required cases are skipped.

The consolidated measured evidence and release-claim boundary are published in
the [M10 compatibility report](reports/m10-compatibility.md).

## Python Adaptation Rules

- String mapping keys take precedence over attributes. Non-mapping objects use
  normal public attribute lookup, including dataclasses, named tuples, and
  properties.
- A bound method used as a command is invoked with the command arguments.
- Names beginning with an underscore are not exposed through field lookup.
- Sprout `hasField` rejects Python maps, scalars, and containers as non-struct
  values, then checks public attributes on an ordinary caller-provided Python
  object. Python class layout is not represented as Go reflection metadata.
- Native Python integers retain arbitrary precision. Template numeric literals
  still follow the Go parser's accepted syntax and range rules.
- Mappings with Go-comparable homogeneous keys follow Go's ordered range
  behavior. Mixed or otherwise non-Go-comparable Python keys use a stable
  `(type name, repr)` order; this is a documented Python-only difference.
- Exceptions from caller functions and bound methods become
  `TemplateExecutionError` instances and retain the original exception as
  `__cause__`.
- Execution errors retain the innermost compiled source location. Public error
  attributes include a UTF-8 byte `position`, character-based `line` and
  `column`, the root `source_name`, and the currently executing
  `template_name`. The optional public `name` argument labels a template
  source and defaults to `"template"`.
- `Template.render_template` and `Template.render_template_to` execute any
  associated definition or the named root. Definitions share the complete
  immutable association namespace, including sibling and root templates.
- `Template.from_sources` constructs that namespace from named source files.
  `with_source` returns a new namespace with one additional or replacing
  source, leaving its parent unchanged. `render_source` parses and renders a
  dynamic source against inherited definitions; its async counterpart also
  awaits registered functions.
- `gotpl.runtime.engine.TemplateEngine` owns an immutable multi-source `Template`
  and renders an ordered mapping of named sources with independent per-source
  contexts. It is also re-exported as `gotpl.TemplateEngine`.
  `render_async` provides the same result shape while awaiting callbacks.
- `HTMLTemplate.from_sources` and `with_source` provide the same immutable
  association model while rerunning contextual analysis across the complete
  namespace. File and glob discovery remain application-owned; gotpl does not
  reproduce Go's mutable `Clone`, `AddParseTree`, `ParseFiles`, `ParseGlob`, or
  `ParseFS` method surface.
- Async counterparts exist for string, writer, root, and named-template
  rendering. Writers may return an integer immediately or awaitably; every
  write is awaited before execution continues and short writes are errors.
- The async VM awaits coroutine and custom-awaitable function results at call
  boundaries. The sync VM never manages an event loop and raises
  `AsyncRequiredError` if a callable returns an awaitable.
- Python functions normally express failure by raising. Functions that need an
  explicit Go-style `(value, error)` result return `FunctionResult`; ordinary
  tuples remain ordinary template values.
- Python functions may use defaulted positional parameters and optional
  keyword-only defaults. Required keyword-only parameters are rejected because
  template commands cannot supply keyword arguments. Positional arity failures
  use stable Go-style diagnostics.
- Enforceable positional annotations are checked before registered functions,
  bound methods, and `call` targets run. Built-in scalar types, unions,
  `Literal`, and parameterized runtime containers are supported. Unknown or
  non-runtime annotations remain informational instead of being evaluated as
  arbitrary Python expressions.
- A missing value uses an internal sentinel in `default` mode, `None` in
  `zero` mode, and raises `TemplateExecutionError` in `error` mode. Both the
  sentinel and a dynamic `None` render as `<no value>` at top level.
- `TypedMap(data, zero=...)` carries an explicit Go map element zero value.
  Its missing elements use that value for `index` and for field lookup in
  `missing_key="zero"` mode. Plain Python mappings remain dynamically typed and
  therefore use `None` when no element type is available.
- `GoSeq(iterable)` enforces Go `iter.Seq` single-value range binding.
  `GoSeq2(pairs)` exposes keys with zero or one declaration and key-value pairs
  with two declarations. Ordinary Python iterables use indexed array/channel
  semantics. Asynchronous iterables are outside the approved M3 scope and are
  not consumed by either runtime.

## Intentional Extensions

Async rendering and project extras are extensions, not Go compatibility claims.
They must preserve Go behavior when no extension is used. Extension behavior
must be isolated, documented, and tested against the synchronous baseline where
applicable.

`format_mode="python"` is an explicit Python-only extension. The default
`format_mode="go"` remains part of the compatibility contract. Python mode
keeps Go template syntax and `printf` verbs, but ordinary output, `%v`, `%#v`,
and `%T` use Python string, representation, and type names. The selected mode
also applies consistently to `print`, `println`, `html`, `js`, and `urlquery`.
Missing values and untyped `nil` retain their execution semantics in both modes.

Homogeneous Python mappings with Boolean, integer, float, complex, or string
keys use Go-compatible natural ordering. Mixed or custom Python key types use
the stable `(type name, repr)` fallback described above.

Go mode formats `bytes` and `bytearray` as `[]uint8`, including byte-slice
string, quote, hexadecimal, default, and syntax verbs. Invalid UTF-8 is replaced
when Python's text-only writer boundary cannot preserve arbitrary bytes.
`GoPointer` supplies explicit typed pointer formatting based on Python object
identity. A custom value may implement `__go_format__(GoFormatSpec)` as the
Python adaptation of Go's `fmt.Formatter`; Python format mode deliberately
bypasses this Go-only hook.

The Python extension registry may expose `reMatch(pattern, value)`. It uses
Python standard-library `re` syntax and search semantics and is intentionally
separate from Sprig's `regexMatch` and the Go-compatible `goregexp` package.
It is never enabled by a Go, Sprig, Slim-Sprig, Sprout, Helm, or strict-sandbox
profile. A caller may add it explicitly to a strict policy's function
allowlist, accepting Python backtracking risk.

Future Python-native syntax or semantic options must be immutable construction
configuration and part of template cache identity. Template source cannot
enable or disable features, parsing rules, or security policy at execution
time. The default dialect remains Go-compatible.

Execution sandboxing is an opt-in Python policy. It is distinct from
`html/template` contextual escaping and cannot change the default exported
field and method behavior required by Go compatibility.

`SandboxPolicy.strict()` defaults to mapping-only data, separate explicit
attribute/property/method grants, an explicit registered-function allowlist,
no custom lookup adapter, no data-callable `call` built-in, and conservative
per-render budgets. `ExecutionBudget` accounts for output characters, range
items, active associated-template depth, and function or method calls. These
limits cover VM-visible work only and are not hard CPU, wall-time, or heap
limits. The operational boundary is documented in `docs/sandbox.md`.

## Upstream Test Material

The project uses Apache-2.0 for original work and retains the applicable Go BSD
and Sprig-family MIT notices in `THIRD_PARTY_NOTICES.md`. Oracle fixtures contain
independently authored inputs and recorded outputs with pinned source metadata.
Copyrightable upstream expression requires a specific review and notice under
`docs/licensing.md` before inclusion.

All compatibility implementation follows a test-first workflow: establish a
failing fixture from the reference behavior before changing runtime code.
