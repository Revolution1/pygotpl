# M4 Sprig Compatibility Progress

## Status

M4 is complete. The exact registries, behavior families, strict 211-function
evidence ledger, security boundary, Slim-Sprig profile, benchmark baseline, and
full project quality gate satisfy the milestone deliverables and acceptance
gates. Future upstream regression cases remain normal compatibility
maintenance rather than open M4 scope.

## Reference Inventory

The pinned Sprig v3.3.0 `genericMap` contains 211 public function names. The
machine-readable inventory is `sprig-v3.3.0-functions.json` and records the
tag, commit, complete sorted name list, aliases, and hermetic exclusions.
The function-level implementation and explicit-test index is
`m4-sprig-function-matrix.md`.
The stricter normal/boundary/failure evidence ledger covers all 211 public
names and has status `complete`.

Sprig builds text and HTML maps from the same generic registry. Its hermetic
maps remove 17 names that depend on wall-clock time, randomness, environment
variables, or DNS. This leaves 194 hermetic names.

## Implemented Families

The registry contains all 211 Sprig names. The behavior-audited and
oracle-backed slice includes:

- basic casing, trimming, containment, repetition, replacement, indentation,
  and plural selection;
- Base32 and Base64 encoding and decoding;
- SHA-1, SHA-256, SHA-512, and Adler-32 digests;
- slash-based `base`, `dir`, `clean`, `ext`, and `isAbs` path functions;
- the `hello` compatibility function and deprecated `trimall` alias.
- Sprig zero-value selection through `default`, `empty`, `coalesce`, `all`,
  `any`, and `ternary`;
- integer conversion, octal conversion, integer arithmetic, extrema,
  `until`, `untilStep`, and `seq`.
- dictionary construction, mutation, selection, plucking, nested lookup, and
  deep copying, including the `mustDeepCopy` alias.
- list construction, selection, slicing, mutation, flattening-equivalent Sprig
  operations, uniqueness, sorting, and `must*` aliases;
- JSON conversion, floating-point arithmetic, regex, URL, reflection, deep
  merge, POSIX and host path helpers, and flow-control failure;
- advanced quoting, splitting, case conversion, abbreviation, wrapping, and
  semantic-version parsing and constraints.
- Go-layout date formatting and parsing, nanosecond-preserving time values,
  time-zone conversion, Unix epochs, absolute date modification, duration
  parsing and formatting, and duration rounding.
- environment lookup and Go shell-style expansion, DNS selection, secure random
  strings and bytes, UUID v4, bounded random integers, and rune shuffling.

Sixty-three independently authored fixtures execute through the pinned Sprig
oracle and Python implementation. They cover normal, boundary, pipeline-order,
alias, and failure behavior across the implemented families.

Registry constructors accept an optional clock and bind it only to functions
that observe current time. Default calls retain Sprig behavior, while tests and
embedding applications can make `now`, `ago`, fallback date inputs, and
time-based duration rounding deterministic. The eight implemented functions in
Sprig's non-hermetic date list are excluded from hermetic maps.

Local time resolution follows Go's observable `TZ` rules for named zones, the
optional leading colon, empty values, absolute TZif paths, and invalid-zone UTC
fallback. When `TZ` is unset, tzlocal supplies a cross-platform IANA location;
tzdata supplies the IANA database on systems without one. Differential tests
cover winter and summer offsets plus absolute duration addition through a DST
gap. Date parsing, formatting, and modification preserve nine fractional
digits, including one-nanosecond and cross-second changes. A future standalone
`gotime`/`goduration` object API remains an extraction candidate rather than an
M4 public API commitment.

The `MST` layout token uses TZif type metadata instead of Python's
platform-dependent `%Z` whitelist. Go-oracle differentials cover locally valid
standard and daylight abbreviations, a daylight abbreviation outside its
active season, unknown abbreviations, Go's `GMT+3` result, mixed-case `ChST`,
and signed zone-like names. The TZif reader supports v1 and modern v2-v4 files,
system and packaged data, malformed-data rejection, and Go's relevant-type then
ordinary-name fallback order.

An integer-second and nanosecond time core now covers the complete signed
64-bit Unix input range without relying on Python's 1-9999 `datetime` range.
Static fixtures cover year 0, year 10000, both int64 endpoints, future DST,
pre-transition local mean time, and saturated `ago` durations. A batched
differential matrix covers 16 structural boundaries and 32 deterministic
int64 samples in both UTC and America/New_York, including Go's absolute-time
wrap point, negative years, weekdays, year days, and historical offset seconds.
Property tests compare the integer civil conversion with `datetime` and
`zoneinfo` throughout their shared ranges.

Entropy, pseudo-random index selection, environment mappings, and DNS resolvers
are independently injectable. Default registries use operating-system entropy,
process environment, system DNS, and Python's process-global pseudo-random
source as the corresponding pure Python runtime facilities. Hermetic membership
still follows Sprig's exact 17-name exclusion list, including its intentional
retention of `randInt` and `shuffle`.

The cryptographic surface includes Go-compatible master-password derivation,
AES-CBC key and padding rules, bcrypt and htpasswd, private-key generation, and
CA, self-signed, signed, and imported certificate pairs. The `crypto` extra
contains the bcrypt and cryptography backends and is loaded only when a
backend-dependent function is called. Standard-library-only `derivePassword`
remains available from a base installation. Tests cover upstream password
vectors, deterministic AES entropy, certificate fields and issuer
relationships, invalid inputs, and template registration.

The final crypto and randomness audit preserves Go `(value, error)` contracts
through `FunctionResult` for random bytes, AES, imported certificates, and all
certificate-generation entry points. It also covers bcrypt's 72-byte limit,
Go `uint32` counter bounds, signed-`int` range overflow for `randInt`, Unicode
rune shuffling, CR/LF in Base64 ciphertext, and Sprig's deliberately loose AES
padding removal.

Unicode string differentials preserve Go simple case mapping instead of
Python's multi-code-point case expansion. They also cover legacy Sprig
dependencies whose `initials` and `nospace` implementations iterate UTF-8
bytes, plus the observable difference between Go `unicode.IsSpace` and Python
`str.isspace` for ASCII information separators.

The active boundary audit also covers RE2 ASCII and POSIX classes, absolute-end
anchors, empty-match progression, signed 64-bit arithmetic and cast parsing,
mergo zero-value behavior, and Go `encoding/json` float64 decoding and number
formatting. Extended regex coverage includes Go named groups, braced Unicode
escapes, octal code points, Unicode case folding, counted-repeat limits, all
Go-accessible category and script tables, aliases, and complements. Generated
Go 1.27.0 Unicode 17.0.0 data prevents Python-version drift.
Regex execution now uses a pure Python ordered Thompson NFA for general
patterns and an audited single-atom linear stdlib fast path. Structured,
seeded, adversarial, nullable-loop, multiline-anchor, and repeated-capture
differentials verify leftmost-first behavior without exposing a backtracking
path. A bounded compilation cache preserves warm-render performance.

URL compatibility covers opaque URLs with and without schemes, temporary-URL
userinfo parsing, malformed escapes, control-character rejection, IPv6 zones,
Unicode and reserved host escaping, and relative paths whose first segment
contains a colon. Dictionary compatibility preserves Sprig's intentional
nested-object aliasing for merge, overwrite, pick, and omit while keeping
`deepCopy` isolated. Go `(value, error)` functions `mustDeepCopy`,
`mustMerge`, `mustMergeOverwrite`, and `dig` expose `FunctionResult` to direct
Python callers and unwrap normally inside templates.
Numeric coverage includes NaN and infinity conversion, formatting, Go math,
and decimal rejection paths. URL coverage preserves case-sensitive host
fields, decoded and re-encoded fragments, IPv6 zones, and invalid-host errors.
Semantic-version coverage follows Masterminds' relaxed leading-zero parser,
uint64 bounds, original spelling, and its complete operator aliases. These
cases replaced Python-native behavior that had previously passed narrower
family tests.

`docs/sprig-security.md` records the capability boundary, exact upstream
hermetic exclusions, intentionally retained nondeterministic functions,
blocking environment and DNS behavior, cryptographic cost and AES-CBC limits,
mutation semantics, serialization limits, and the regex execution and resource
boundary.

## Public Registry Boundary

`gotpl.funcs.sprig` exposes `generic_func_map`, `text_func_map`, `html_func_map`,
`hermetic_text_func_map`, and `hermetic_html_func_map`. Each call returns an
independent mutable dictionary suitable for `Template(functions=...)`.

The maps contain all 211 names, with the exact 17 non-hermetic names removed
from hermetic maps. Every name has validated normal, boundary, and failure
evidence or a documented total-operation rationale.

Slim-Sprig v3.0.0 and Sprout v1.1.1 are pinned in `.references/`. The versioned
Slim-Sprig inventory contains 164 names, 153 of them hermetic. Its isolated maps
contain all 164 generic and 153 hermetic names. The Go oracle loads the pinned
Slim-Sprig fork independently. Twenty-one compatible Sprig fixtures plus a
complete 164-name normal-behavior matrix execute against that fork. This audit
identified and preserved Slim-Sprig's decimal-only integer casts instead of
silently inheriting Sprig v3.3.0 cast behavior. Sprout's divergent registry and
group model is assigned to M8 with the Helm integration package.

## Performance Evidence

`benchmarks/fixtures/sprig_render.json` is a shared, versioned Sprig-heavy warm
render case. It uses Sprig v3.3.0 in both runtimes and covers dictionary merge
and lookup, list uniqueness and sorting, string conversion, regex replacement,
SHA-256, semantic-version constraints, integer arithmetic, and JSON encoding.
Run it with:

```console
python -m benchmarks.compare benchmarks/fixtures/sprig_render.json
```

An August 26, 2026 development baseline on Darwin arm64 with CPython 3.13.7 and
Go 1.26.5 measured 88,147 ns/op for Python and 9,776 ns/op for Go, a 9.02x
Python-to-Go latency ratio. This single local sample is reproducibility
evidence, not a stable performance claim; M6 owns repeated statistical runs,
allocation measurement for Python, profiling, and optimization.

## Verification Snapshot

The August 26, 2026 M4 exit verification run passed 946 tests. Coverage reported
6,046 statements with zero misses and 99% total branch-aware coverage. Ruff
lint and format checks, strict Pyright, and the Go oracle module test also
passed. These counts describe the M4 exit snapshot; the separate
211-function evidence ledger is also complete.
