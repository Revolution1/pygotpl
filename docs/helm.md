# Helm Functions and Runtime

For a command-first walkthrough and a complete application example, start with
[Build a Helm Renderer with gotpl](building-helm.md).

## Package Boundary

`gotpl.funcs.helm` provides the reusable Helm-compatible function registry.
`gotpl.exts.helm` provides `HelmExtension` and the convenient
`HelmTemplateEngine` facade. The generic gotpl render session owns the lifecycle
required by `include`, `tpl`, `required`, and `fail`. Neither package exposes a
Chart class, chart loader, release model, repository client, or cluster client.

The public `gotpl.TemplateEngine` compiles named sources into one immutable
association. Generic association and batch-rendering concepts are owned by
[Reusable Templates and Environments](reusable-templates.md); this page covers
only Helm-specific behavior.

The repository's `examples/helm_runtime` package builds Chart values and file
contexts on top of the reusable engine. The CLI in `examples/helm_cli.py` is an
integration example, not a supported replacement for the Helm application.

## Installation

Install the Helm serialization extra when an application uses the YAML or TOML
functions:

```console
python -m pip install "gotpl[helm]"
```

Importing `gotpl.funcs.helm` and using dependency-free functions do not require
the extra. A serializer whose dependency is absent raises an actionable
`MissingOptionalDependencyError`.

## Reusable Helm Execution

Use `HelmExtension` when an application already constructs templates through a
generic environment:

```python
from gotpl import Environment
from gotpl.exts.helm import HelmExtension

engine = Environment(
    extensions=(HelmExtension(),),
    missing_key="zero",
).from_sources(
    {
        "helpers.tpl": '{{define "label"}}{{.}}-label{{end}}',
        "main.txt": '{{include "label" .}}|{{tpl "{{.}}-tpl" .}}',
    }
)

assert engine.render_template("main.txt", "demo") == "demo-label|demo-tpl"
```

This is the extensible path: the same environment can compose application
functions, immutable policies, and other runtime extensions. Function-name
collisions are rejected instead of silently changing the selected profile.

Use `HelmTemplateEngine` when associated sources invoke Helm's late-bound
functions and no other environment customization is needed:

```python
from gotpl.exts.helm import HelmTemplateEngine

engine = HelmTemplateEngine.from_sources(
    {
        "helpers.tpl": '{{define "label"}}{{.name}}-label{{end}}',
        "main.txt": (
            '{{include "label" .}}|{{tpl .dynamic .}}|'
            '{{required "name required" .name}}'
        ),
    }
)

output = engine.render(
    {"main.txt": {"name": "demo", "dynamic": '{{include "label" .}}'}}
)
assert output == {"main.txt": "demo-label|demo-label|demo"}
```

Both APIs compile their base association once. Every render receives isolated
include-recursion state and a bounded dynamic `tpl` cache, so the same instance
can be reused across threads and asyncio tasks. `render_async()` awaits both
ordinary asynchronous functions and calls made through `include` or `tpl`.

The lower-level `function_map()` remains available for applications with their
own execution engine. Such applications must bind `include`, `tpl`, `required`,
and `fail` explicitly. The returned mapping removes Sprig's `env` and
`expandenv`, disables DNS by default, and uses an empty `lookup` result when no
cluster adapter is supplied. Pass `enable_dns=True` only for a runtime that
intentionally grants that capability.

`custom=` is applied last and can replace a compatibility function. Check
custom names against the returned profile before overriding unless replacement
is deliberate and tested.

## Application Layer

The surrounding application still owns chart loading and the `.Values`,
`.Chart`, `.Release`, `.Files`, `.Capabilities`, `.Subcharts`, and `.Template`
root objects. The repository's `examples/helm_runtime` package demonstrates
that layer without making a chart model part of gotpl's stable API.

Follow [Build a Helm Renderer](building-helm.md) for the runnable CLI, values
precedence, dependency preparation, direct Python integration, complex-chart
command, `lookup` injection, and current example limitations. The example path
exists only in a repository checkout and is not installed in the `gotpl` wheel.

## Security Boundary

The reusable functions are compatibility components, not a sandbox. DNS is
disabled by default, environment functions removed by Helm are absent, and
cluster lookup requires an injected callable. Filesystem and chart access are
owned entirely by the embedding application. Apply `SandboxPolicy`, an
`ExecutionBudget`, and operating-system isolation as described in the
[sandbox guide](sandbox.md) for untrusted templates. A strict policy rejects a
complete Helm function map unless every registered name is explicitly granted.
