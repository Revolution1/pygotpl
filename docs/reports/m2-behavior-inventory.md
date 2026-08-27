# M2 Synchronous Behavior Inventory

This inventory defines the required differential groups for the scoped M2
synchronous runtime. Counts refer to independently authored fixtures executed
against Go 1.27.0 and pygotpl; Python-only adapters have direct companion tests.

| Behavior group | Primary evidence | Status |
| --- | --- | --- |
| Dot, root, fields, variables, and scope | `dot`, `root`, `field`, `variables`, `scope` fixtures | covered |
| Pipelines, grouped operands, and function operands | `pipeline`, `logical-pipeline`, function result and type fixtures | covered |
| Truthiness and comparisons | `if`, `with`, comparison fixtures, Python slice/pointer comparison tests | covered |
| Index, slice, and length | index/slice fixtures and UTF-8 string built-in fixture | covered |
| Range, else, bindings, control, integer, maps, and iterators | range fixture family, `GoSeq`, `GoSeq2`, nil-range tests | covered |
| Built-in print and formatting | print and `printf` fixture family, formatter unit matrix | covered |
| HTML, JavaScript, and URL query text helpers | escaping fixtures including Unicode/control edges | covered |
| Missing keys and typed map zero values | missing-key fixtures and `TypedMap` fixtures | covered |
| Registered functions, methods, `call`, arity, types, and errors | function fixture family and callable adaptation tests | covered |
| Named templates, blocks, root, sibling calls, and direct execution | template/block fixtures and `render_template` API tests | covered |
| Partial output, writer errors, and short writes | function error fixtures and writer protocol tests | covered |
| Reuse and concurrent isolation | reusable API and 100-thread warm-render tests | covered |
| Source-mapped execution errors | top-level, Unicode, nested-template, and defensive IR tests | covered |

## Deferred Boundaries

- Async callables, awaitables, async iterables, cancellation, and async writers
  are M3.
- Sprig registries and functions are M4.
- Contextual `html/template` escaping is M5; M2 covers only the explicit text
  helper functions.
- Explicit call frames, the final recursion limit, optimized backends, and
  headline performance work are M6.
- Platform/package release validation and exhaustive release compatibility
  matrices are M10.

All M2-owned groups above have executable evidence. New compatibility defects
remain subject to the regression protocol and may reopen M2 evidence without
changing these milestone boundaries.
