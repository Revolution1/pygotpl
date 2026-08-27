# M1: Lexer, Parser, and IR

## Outcome

Parse the targeted Go template language into a source-mapped AST and compile it
to an immutable instruction stream.

## Deliverables

- [x] Text/action lexer with custom delimiters and whitespace trimming.
- [x] Literals, variables, fields, chains, commands, and pipelines.
- [x] `if`, `with`, `range`, `break`, and `continue` syntax.
- [x] `define`, `template`, and `block` syntax.
- [x] Comments and source positions.
- [x] Immutable AST model and diagnostic formatter.
- [x] Semantic validation and compact instruction model.
- [x] Parser limits for adversarial nesting and input size.
- [x] Differential parser fixtures and property tests.

## Acceptance Gates

- [x] Every token, grammar branch, AST node, and instruction has direct tests.
- [x] Required parser conformance fixtures match the pinned Go oracle.
- [x] Arbitrary-input tests do not hang or crash outside controlled errors.
- [x] Parser/compiler modules reach 100% statement coverage.
- [x] Parse and compile benchmark baselines are recorded.

## Non-Goals

- Complete execution semantics.
- Sprig functions.
- Contextual HTML escaping.

Evidence is recorded in the [M1 implementation report](../reports/m1-parser-ir.md)
and [M1 conformance report](../reports/m1-conformance.md).
