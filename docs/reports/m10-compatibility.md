# M10 Compatibility Report

## Result

The M10 release-candidate suite passes all currently required conformance,
security, Python adaptation, and API tests. The evidence supports compatible
claims for the parser, async extension, Sprig, Slim-Sprig, and the completed
Sprout and Helm scopes. The broader `text/template` and `html/template` areas
remain classified as partial: their mapped behavior groups pass, but the
repository has not yet reproduced every applicable upstream standard-library
test case independently enough to justify an unqualified "fully compatible"
claim.

This distinction is about strength of proof, not a known failing template in
the required fixture set. New upstream cases may still expose defects and must
enter the red-green compatibility workflow.

## Measured Evidence

Counts below are recomputed from the checked-in fixtures and evidence ledgers.
One fixture may exercise several behaviors; a function ledger entry requires
normal, boundary, and failure evidence or an explicit not-applicable rationale.

| Area | Reference | Measured evidence | Result |
| --- | --- | ---: | --- |
| Lexer and parser | Go 1.27.0 | 88 named cases plus 109 generated acceptance cases; 197 total | compatible |
| Synchronous text execution | Go 1.27.0 | 68 differential fixtures covering every M2 behavior group | partial overall; required M2 scope passes |
| Async execution | Sync VM / Python extension | the same 68 text fixtures plus async, cancellation, writer, and concurrency tests | compatible extension |
| Contextual HTML | Go 1.27.0 | 34 differential fixtures plus the dedicated security corpus | partial overall; required contextual scope passes |
| Sprig | Sprig 3.3.0 | 63 differential fixtures and a complete 211-function evidence ledger | compatible for generic, text, HTML, and hermetic maps |
| Slim-Sprig | Slim-Sprig 3.0.0 | 45 shared fixtures, 7 fork-specific matrix templates, and all 164 exported names | compatible for named profiles |
| Sprout | Sprout 1.1.1 | 20 registries, 234 raw entries, 45 aliases, and complete all/hermetic group evidence | compatible for raw registry/group scope |
| Helm | Helm 4.2.3 | 10 pinned integration cases and a 222-name function-map audit | compatible example/function scope with serializer differences |
| `goduration.go` | Go 1.27.0 `time.Duration` | 74 standalone tests and checked-in oracle vectors | compatible audited surface |
| `gotime.go` | Go 1.27.0 `time` | 218 standalone tests and checked-in oracle vectors | partial overall; audited M7 surface passes |

The complete local gate on CPython 3.14.7 passes 1,973 tests with no skipped
release-blocking case, exact 98.1002% statement coverage, and exact 96.0893%
branch coverage. Go oracle, generated-table, inventory, Ruff, formatting, and
strict Pyright gates also pass. Hosted operating-system and Python-version
matrix results remain separate release evidence and cannot be inferred from
this local run.

## Compatibility Profiles

The default text and HTML constructors install only Go template built-ins.
Sprig, Slim-Sprig, Sprout, Helm, and Python-native helpers are explicit
registries. Their installation in the wheel does not alter the default name
set. Hermetic profiles retain their exact pinned exclusion lists.

`format_mode="go"` is the compatibility default. `format_mode="python"`,
asyncio rendering, `PythonExtensions`, sandbox policies, and execution budgets
are Python extensions. They must not change output or failures when omitted.

## Classified Differences and Boundaries

### Python host values

- Mixed or non-Go-comparable mapping keys use stable `(type name, repr)` order.
- Plain Python mappings have no statically known element zero value;
  `TypedMap` supplies one explicitly.
- Python object attributes and bound methods follow the adaptation rules in
  `docs/compatibility.md`; they do not claim Go reflection metadata.
- Invalid UTF-8 bytes use replacement characters at Python's text-only writer
  boundary.

These are documented Python adaptations where no identical Go host type exists.

### Construction API

Text and HTML multi-source associations use immutable `from_sources` and
`with_source` methods. Source-level definitions, calls, redefinition rules, and
HTML contextual specialization are retained. Go's mutable `Clone`,
`AddParseTree`, post-parse mutation, and file/glob discovery methods are not
reproduced. Decision D013 records the thread-safety and analysis rationale.

### Ecosystem layers

- Sprout safe-function generation is excluded because its typed fallback
  metadata is not present in Python's raw callable map. Raw registries and
  pinned groups are unaffected.
- Nondeterministic Sprout functions compare format, range, validity, and
  round-trip contracts rather than byte-for-byte output.
- Helm invalid YAML, TOML, and JSON diagnostics retain result shape but use the
  installed Python serializer's wording. tomli-w may choose a different valid
  array-of-tables layout.
- Optional crypto, YAML, and Helm serializer dependencies fail lazily with an
  actionable installation-extra message.

### Security extensions

The sandbox is opt-in because default field and method access must remain Go
compatible. It is not a hard CPU, wall-time, or process-memory boundary.
Non-hermetic function maps require capability review even when their optional
dependencies are installed.

## Release Claims

The 1.0 documentation may say that gotpl is a pure Python implementation
targeting observable Go compatibility and may use the compatible labels in the
table above. It must not describe the complete `text/template` or
`html/template` surface as "fully compatible" while those rows remain partial.

The proof-expansion work required to strengthen those claims is listed in the
[post-1.0 conformance backlog](../post-1.0.md). Any newly discovered mismatch is
a correctness defect, not an accepted consequence of the partial label.
