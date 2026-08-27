# M8 Helm Function Evidence

## Baseline

- Helm reference: v4.2.3
- Sprig reference beneath Helm: v3.3.0
- Python surface: `gotpl.funcs.helm.function_map`
- Concrete integration harness: `examples/helm_runtime`

The function map contains 222 names. Relative to pygotpl's 211-name Sprig text
map, it removes `env` and `expandenv`, adds 13 Helm names, and overrides the
context-sensitive `fail`, DNS, JSON, and late-bound functions as required.

## Evidence Matrix

| Area | Evidence | Status |
| --- | --- | --- |
| Registry membership | Exact count, additions, removals, and late-binding unit tests | compatible |
| `include`, `tpl`, `required`, `fail` | Ten pinned engine cases covering callbacks, dynamic definitions, recursion, failures, and strict mode | compatible for the example-runtime scope |
| `lookup` | Empty default and injectable callable tests | compatible for application-owned lookup |
| DNS default | Disabled-result and registry-isolation tests | compatible |
| YAML encode/decode | Pinned ordinary, nested, array, and pretty-output cases | compatible success paths |
| TOML encode/decode | Pinned scalar and ordinary nested-table cases | compatible common paths |
| JSON decode and inherited encode | Pinned map and array cases plus Sprig evidence | compatible common paths |
| Missing extras | Forced-absence YAML and TOML writer tests | compatible actionable failure |

## Documented Serializer Differences

Invalid YAML, TOML, and JSON diagnostics retain Helm's result shape but use the
installed Python serializer's wording. tomli-w can encode a short array of
tables inline rather than as repeated `[[table]]` sections. These boundaries
are recorded in [decision D008](../implementation-decisions.md#d008-use-python-serializers-with-explicit-helm-diagnostic-boundaries); they avoid shipping
three template-specific parser implementations.

## Completed M8 Integration Matrix

- Parent/child definition ordering for `tpl` plus `include` matches Helm.
- Recursive `include` agrees at a practical depth; M9 owns strict call budgets.
- Missing includes and invalid dynamic sources retain the same failure meaning.
- Custom functions override the base map in the same order as Helm.
- Strict missing-key failures retain source context and stable missing-key
  meaning; Python and Go host-map diagnostic wording is not identical.
- The versioned latency, memory, allocation, and hotspot profile is published
  in `docs/reports/m8-helm-performance.md`.
- The explicit capability matrix consumed by M9 is published in the
  [M8 capability matrix](m8-capability-matrix.md).
