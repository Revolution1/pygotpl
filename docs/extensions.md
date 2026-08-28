# Runtime Extensions

Runtime extensions add explicitly selected behavior that needs more than an
ordinary template function. They can receive a controlled render context,
render an associated template or dynamic source, keep state for one top-level
render, declare supported template kinds, and identify sandbox capabilities.

Use [`gotpl.funcs`](function-libraries.md) for pure compatibility function
registries and `gotpl.exts` for context-aware integrations.

## Functions and extensions

| Need | Use |
| --- | --- |
| Compute only from template arguments | an ordinary callable in `functions=` |
| Install a Sprig, Slim-Sprig, or Sprout function set | a `gotpl.funcs` registry |
| Read the current root, dot, or source name | `ContextFunction` |
| Render another associated definition | `ContextFunction` in an `Extension` |
| Compile and render caller-provided template text | `ContextFunction` in an `Extension` |
| Bundle context functions with compatibility and security metadata | `Extension` |

Extensions cannot add template syntax or install arbitrary parser, compiler, or
VM hooks. The narrow protocol keeps compatibility and security behavior
auditable.

## Use an extension

Helm is the first bundled context-aware extension:

```python
from gotpl import Environment
from gotpl.exts.helm import HelmExtension

engine = Environment(
    extensions=[HelmExtension()],
    missing_key="zero",
).from_sources(
    {
        "helpers.tpl": '{{define "label"}}{{.}}-label{{end}}',
        "main.txt": '{{include "label" .}}|{{tpl "{{.}}-dynamic" .}}',
    }
)

assert engine.render_template("main.txt", "demo") == "demo-label|demo-dynamic"
```

Extension selection is immutable construction policy. Nothing in template
source can enable an extension, add capabilities, or change sandbox rules.

## Write a context function

`ContextFunction` marks a callable whose first argument is supplied by the VM.
That injected argument is not visible to template arity checks.

```python
from gotpl import ContextFunction, Environment, RenderContext


def source_label(context: RenderContext, prefix: str) -> str:
    return f"{prefix}:{context.source_name}"


environment = Environment(functions={"sourceLabel": ContextFunction(sync=source_label)})
template = environment.from_string(
    '{{sourceLabel "rendering"}}',
    name="page.txt",
)

assert template.render() == "rendering:page.txt"
```

An ordinary function should remain an ordinary callable. Use
`ContextFunction` only when the implementation genuinely needs render-local
services or metadata.

## Write an extension

An `Extension` contributes a read-only function mapping and declares whether it
supports text templates, HTML templates, or both. This example implements a
generic associated-template helper:

```python
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Literal

from gotpl import ContextFunction, Environment, RenderContext


def render_partial(
    context: RenderContext,
    name: str,
    data: object,
) -> str:
    return context.render_template(name, data)


def partial_functions() -> Mapping[str, Callable[..., object]]:
    return MappingProxyType(
        {
            "renderPartial": ContextFunction(
                sync=render_partial,
                capabilities=frozenset({"render-associated"}),
            )
        }
    )


@dataclass(frozen=True, slots=True)
class PartialExtension:
    functions: Mapping[str, Callable[..., object]] = field(
        default_factory=partial_functions
    )
    template_kinds: frozenset[Literal["text", "html"]] = frozenset({"text"})


engine = Environment(extensions=[PartialExtension()]).from_sources(
    {
        "partials.tpl": '{{define "card"}}[{{.}}]{{end}}',
        "page.txt": '{{renderPartial "card" .Name}}',
    }
)

assert engine.render_template("page.txt", {"Name": "Ada"}) == "[Ada]"
```

The extension is text-only because captured strings are not automatically
trusted HTML. An extension that advertises HTML support must verify its nested
rendering and return-value behavior under contextual analysis.

## Render context services

Synchronous context functions receive `RenderContext`; asynchronous
implementations receive `AsyncRenderContext`.

| Service | Meaning |
| --- | --- |
| `root` | root value for the current template frame |
| `dot` | current pipeline dot value |
| `source_name` | source currently executing |
| `template_name` | associated template currently executing |
| `render_template(name, data)` | capture an associated template in this render |
| `render_source(source, data, name=...)` | compile and capture dynamic source |
| `state(key, factory)` | get extension-local state for this top-level render |

Use an opaque object owned by the extension as the state key. State is isolated
between top-level renders, shared with their nested renders, and discarded when
the render finishes. Do not use it as a process-wide cache.

Provide `sync=` and `async_=` implementations when an extension supports both
execution modes. A synchronous render of an async-only context function raises
`AsyncRequiredError`; gotpl does not create an event loop on the synchronous
path.

## Capabilities and sandbox policy

Capabilities describe context services with security significance. A strict
sandbox must allow both the visible function name and every capability declared
by its `ContextFunction`:

```python
from gotpl import Environment, SandboxPolicy

policy = SandboxPolicy(
    allow_functions={"renderPartial"},
    allow_context_capabilities={"render-associated"},
)

environment = Environment(
    extensions=[PartialExtension()],
    sandbox=policy,
)
```

`render-associated` and `render-dynamic-source` are distinct grants. An
application may allow calls within a precompiled association while rejecting
dynamic template text. See [Sandboxing](sandbox.md) for function allowlists,
data access, output and iteration budgets, and operating-system isolation.

## Composition and collisions

`Environment` checks extension collisions during construction:

```python
from gotpl import Environment

try:
    Environment(
        functions={"renderPartial": lambda: "application"},
        extensions=[PartialExtension()],
    )
except ValueError as error:
    assert "runtime extension function collision" in str(error)
else:
    raise AssertionError("function collision was not rejected")
```

Extensions are composed in the order supplied, but duplicate function names
are errors rather than precedence rules. Keep compatibility profiles explicit;
do not create an extension that silently injects itself into every template.

## Helm extension

`gotpl.exts.helm.HelmExtension` uses the same protocol for `include` and `tpl`,
while contributing Helm's ordinary `required`, `fail`, `lookup`, and function
registry behavior. Use the [Helm library guide](helm.md) for its API and
[Build a Helm Renderer](building-helm.md) for the complete chart workflow.
