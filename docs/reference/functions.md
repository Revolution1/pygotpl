# Function Registry API

These registries are opt-in: construct a mapping and pass it as
`Template(..., functions=...)`. For runnable setup, profile-selection, and
composition examples, start with [Function libraries](../function-libraries.md).

| Registry | Use it for |
| --- | --- |
| Sprig | Full pinned Sprig v3 compatibility profiles |
| Slim-Sprig | The smaller pinned Slim-Sprig inventory |
| Sprout | Explicit registries and auditable registry groups |
| Helm | Lower-level Helm-compatible function map for application-owned callbacks |

Registry names describe compatibility contracts, not security guarantees.
Review the [Sprig capability boundary](../sprig-security.md) before executing
templates from untrusted sources. Most Helm users should select
`gotpl.exts.helm` through the [Helm integration guide](../helm.md); the Helm
section below documents only `gotpl.funcs.helm.function_map()` and its optional
dependency error.

## Sprig

::: gotpl.funcs.sprig

## Slim-Sprig

::: gotpl.funcs.slim_sprig

## Sprout

::: gotpl.funcs.sprout

## Helm

::: gotpl.funcs.helm
