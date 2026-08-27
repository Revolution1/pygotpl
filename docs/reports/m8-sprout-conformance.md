# M8 Sprout v1.1.1 Conformance Audit

## Result

All 20 pinned Sprout registries are implemented. Their 234 raw function names,
45 aliases, ordered notices, and the exact `all` and `hermetic` group
memberships are enforced against the generated v1.1.1 inventory.

Every exposed raw function has an executable evidence route. The audit test
fails if a new or renamed function lacks one:

| Evidence route | Raw functions | Meaning |
| --- | ---: | --- |
| Exact Sprig callable | 50 | Uses the already completed Sprig 3.3.0 function ledger |
| Direct Sprout differential case | 159 | Go and Python render the same deterministic case |
| Supplemental oracle contract | 25 | Randomized, wall-clock, generated crypto/UUID, YAML, or failure-shape evidence |
| Total | 234 | Complete raw inventory |

All 45 aliases route to an evidenced original. Inventory and handler tests also
verify that aliases, notices, UID deduplication, registration order, group
membership, caching, and immutability remain exact.

## Supplemental Evidence

The 25 supplemental routes are intentionally not compared byte-for-byte where
upstream output is nondeterministic:

- ten cryptographic certificate/key/hash adapters reuse the completed Sprig
  implementations and retain Sprout-specific error adaptation tests;
- six random functions compare character sets, lengths, decoded byte counts,
  and integer ranges against both runtimes;
- generated UUID v4/v7 values compare version and validity contracts;
- `shuffle` compares Unicode code-point multisets in both runtimes;
- `now` and `dateAgo` compare the pinned wall-clock result range;
- YAML functions use direct successful-output differential cases; and
- `hasField` compares the pinned non-struct failure contract, while Python
  object behavior has separate adaptation tests.

The direct matrix additionally covers deterministic conversion, maps, network,
numeric, regexp/regex, slices, strings, time, UUID derivation, checksums,
encoding, filesystem, reflection, semver, standard helpers, and deprecated
compatibility names.

## Documented Boundaries

Python objects do not have Go struct reflection metadata. `hasField` rejects
maps and scalar/container values like the Go function rejects non-structs, then
checks an attribute on an ordinary caller-provided Python object. This is a
host-value adaptation, not a claim that Python class layout is a Go struct.

Random, wall-clock, UUID, bcrypt, key, and certificate output cannot be equal
across runs. Their deterministic inputs, format, version, range, parseability,
round-trip, and error contracts are compared instead.

Sprout's optional generated safe-function feature is not exposed. D010 records
why returning a generic Python fallback would be observably wrong and defines
the metadata and oracle gates required to revisit it. This limitation does not
alter the default raw registries or either pinned group.

## Reproduction

```console
./scripts/check_sprout_inventory.sh
pytest -q tests/unit/sprout tests/conformance/test_sprout.py
```

The conformance suite dynamically invokes the pinned Go oracle. The inventory
check regenerates upstream metadata and compares both the report artifact and
the copy packaged in the pygotpl wheel.
