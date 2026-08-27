# M1 Parser Conformance Report

## Reference

- Go release: 1.26.5
- Source areas: `text/template/parse` lexer, parser, nodes, and tests
- Oracle: `tools/oracle`
- Fixture files: `tests/conformance/fixtures/parser`

The checked-in inputs are independently authored compatibility cases. No
upstream test body is copied into the repository; the approved attribution
policy is recorded in [the M0 license review](m0-license-review.md).

## Evidence

- 88 traceable fixed parser cases execute against both the Go oracle and the
  Python parser.
- 109 generated term, whitespace, control, pipeline, grouping, definition, and
  invalid-structure combinations execute in one batched oracle comparison.
- 300 Hypothesis-generated arbitrary Unicode strings either parse or raise a
  project-controlled syntax error.
- Generated valid control nesting covers depths zero through forty.
- A 2,000-level parenthesized input terminates at the configured parser limit.
- Lexer, parser, semantic-analysis, and compiler modules have 100% statement
  coverage.

## Covered Behavior Groups

The fixed matrix covers:

- empty input, literal Unicode text, comments, trim markers, and UTF-8 byte
  positions;
- default, alphanumeric, Unicode, and marker-shaped delimiters;
- dot, root, fields, variables, declarations, assignments, and parse scopes;
- strings, raw strings, character constants, escape validity, booleans, nil,
  integers, decimal and hexadecimal floats, imaginary values, and complex
  values;
- integer and floating-point range boundaries, base prefixes, and underscore
  placement;
- commands, arguments, grouping, field chaining, pipelines, trailing pipe
  behavior, built-ins, registered functions, and unknown functions;
- `if`, `with`, `range`, `else if`, `else with`, `break`, and `continue`;
- `define`, `template`, `block`, nested blocks, duplicate definitions, and
  empty-definition replacement rules;
- malformed delimiters, actions, operands, pipelines, declarations, control
  structures, template names, escapes, and numeric literals;
- source, token, control nesting, and expression nesting limits.

## Differences Found and Resolved

Differential development identified and corrected:

- Go quoted-string rules versus Python's permissive escape parsing;
- octal escape values above one byte;
- hexadecimal float underscore placement and numeric underscore validation;
- integer and floating-point overflow behavior;
- Unicode identifier digits versus Python's broader `isalnum` classification;
- blocks nested in control bodies;
- empty duplicate definition replacement;
- variables retained in parser scope through a control's `else` branch;
- registered `break` and `continue` function names overriding keywords;
- trailing pipeline separators accepted after a complete command.

## Result

The M1 lexer/parser/semantic/IR surface satisfies its acceptance matrix against
the pinned Go 1.26.5 oracle. Runtime execution behavior remains assigned to M2
and is not claimed by this report.
