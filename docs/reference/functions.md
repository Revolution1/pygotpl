# Function Registry API

These registries are opt-in: construct a mapping and pass it as
`Template(..., functions=...)`. For runnable setup, profile-selection, and
composition examples, start with [Function libraries](../function-libraries.md).

| Registry | Use it for |
| --- | --- |
| Sprig | Full pinned Sprig v3 compatibility profiles |
| Slim-Sprig | The smaller pinned Slim-Sprig inventory |
| Sprout | Explicit registries and auditable registry groups |
| Helm | Helm-compatible functions supplied by gotpl |

Registry names describe compatibility contracts, not security guarantees.
Review the [Sprig capability boundary](../sprig-security.md) before executing
templates from untrusted sources, and the [Helm integration guide](../helm.md)
for application-owned Helm callbacks and context.

## Sprig

::: gotpl.funcs.sprig

## Slim-Sprig

::: gotpl.funcs.slim_sprig

## Sprout

::: gotpl.funcs.sprout

## Helm

::: gotpl.funcs.helm
