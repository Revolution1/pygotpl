# M8 Sprout v1.1.1 Inventory

## Result

The pinned Sprout v1.1.1 module registers 234 raw functions and 45 aliases
across 20 public registries. The upstream `all` group builds 251 names from 17
registries; `hermetic` builds 227 names from 14 registries.

The complete machine-readable inventory is
`docs/reports/sprout-v1.1.1-inventory.json`. It includes:

- schema version 1 for explicit consumer compatibility;
- every registry name and UID;
- sorted raw function names;
- original-to-alias mappings;
- ordered notices with function names, kind, and message; and
- ordered registry membership and built function names for `all` and
  `hermetic`.

## Group Boundary

The `all` group contains checksum, conversion, encoding, environment,
filesystem, maps, network, numeric, random, reflect, deprecated regexp, semver,
slices, std, strings, time, and unique ID registries.

The `hermetic` group removes environment, network, and random. It retains the
filesystem registry because that registry performs path manipulation rather
than filesystem I/O. It also retains unique ID and time functions exactly as
the pinned upstream group does; the group name must not be interpreted as a
stronger determinism guarantee than Sprout defines.

Crypto, backward compatibility, and the replacement `regex` registry are not
members of either pinned group. The groups use the deprecated `regexp` registry
for compatibility with Sprout v1.1.1.

## Reproduction

```console
./scripts/check_sprout_inventory.sh
```

The command runs `tools/oracle/sprout_inventory` against the pinned Go module
and compares its output with both the report JSON and the resource embedded in
the `pygotpl` wheel. A mismatch fails the repository check.

Inventory coverage is not behavioral compatibility. Implemented function maps
are tracked separately and must pass dynamic Go/Python conformance cases before
their registry is exposed.
