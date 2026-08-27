# M4: Sprig Compatibility

## Outcome

Implement the public function maps and observable behavior of Sprig v3.3.0,
plus the pinned Slim-Sprig v3.0.0 registry profile.

## Deliverables

- [x] Versioned inventory of all target function names and aliases.
- [x] String, numeric, collection, default, and conversion functions.
- [x] Encoding, JSON, URL, regex, path, and semantic-version functions.
- [x] Date, duration, crypto, random, environment, and network function names.
- [x] `must*` variants and error behavior.
- [x] Generic, text, HTML, and hermetic function-map membership.
- [x] Injectable clocks for deterministic date and duration tests.
- [x] Injectable entropy and pseudo-random selection for deterministic tests.
- [x] Function-level conformance table and Sprig-heavy benchmarks.
- [x] Versioned Slim-Sprig function inventory.
- [x] Slim-Sprig generic, text, HTML, and hermetic map membership.

## Acceptance Gates

- [x] Every Sprig v3.3.0 public function is registered with an implementation.
- [x] Every function has normal, boundary, and failure tests where applicable.
- [x] Deterministic cases match the Go Sprig oracle.
- [x] Non-hermetic profiles and security implications are documented.
- [x] Registry tests permit only Sprig's intentional `slice` built-in override.
- [x] Slim-Sprig membership and every public name have pinned-fork differential evidence.

## Non-Goals

- Project extras in the Sprig namespace.
- Silent behavior changes intended to make Sprig more Pythonic.
