# Helm Functions and Runtime Example

## Package Boundary

`gotpl.funcs.helm` provides reusable Helm-compatible function-map additions for
applications that own their rendering model. It does not expose a Chart class,
loader, release model, or Helm rendering engine.

Generic cross-file execution belongs to `gotpl.runtime`.
`gotpl.TemplateEngine` compiles named sources into one immutable
association, accepts an independent context for each selected source, and
provides matching synchronous and asynchronous batch APIs.

The repository's `examples/helm_runtime` package demonstrates how an
application can combine those pieces into a miniature Helm chart runtime. The
CLI in `examples/helm_cli.py` is an integration example, not a supported
replacement for the Helm application.

## Installation

Install the Helm serialization extra when an application uses the YAML or TOML
functions:

```console
python -m pip install 'gotpl[helm]'
```

Importing `gotpl.funcs.helm` and using dependency-free functions do not require the
extra. A serializer whose dependency is absent raises an actionable
`MissingOptionalDependencyError`.

## Building an Application Function Map

Helm's `include`, `tpl`, `required`, and `fail` functions depend on application
execution state. The application supplies those late-bound callables:

```python
from gotpl.funcs.helm import function_map

functions = function_map(
    include=application_include,
    tpl=application_tpl,
    required=application_required,
    fail=application_fail,
    lookup=application_lookup,
)
```

The returned mapping combines the Helm text function profile with those
bindings, YAML, TOML, and decoding helpers. It removes Sprig's `env` and
`expandenv`, disables DNS by default, and uses an empty `lookup` result when no
cluster adapter is supplied. Pass `enable_dns=True` only for a runtime that
intentionally grants that capability.

## Core Cross-file Execution

```python
from gotpl import TemplateEngine

engine = TemplateEngine.from_sources(
    {
        "helpers.tpl": '{{define "label"}}{{.prefix}}:{{.value}}{{end}}',
        "first.txt": '{{template "label" .}}',
        "second.txt": '{{template "label" .}}',
    }
)

output = engine.render(
    {
        "first.txt": {"prefix": "one", "value": 1},
        "second.txt": {"prefix": "two", "value": 2},
    }
)

assert output == {"first.txt": "one:1", "second.txt": "two:2"}
```

`render_async()` awaits asynchronous functions while preserving source order.
`with_source()` derives a new immutable engine with one added dynamic source.

## Miniature Helm Example

Within a repository checkout, the example runtime can be used directly:

```python
from examples.helm_runtime import Engine, Release, load_chart

chart = load_chart("path/to/unpacked-chart")
output = Engine().render(chart, release=Release(name="demo"))
```

The example supplies `.Values`, `.Chart`, `.Release`, `.Files`,
`.Capabilities`, `.Subcharts`, and `.Template`, plus chart traversal and Helm's
late-bound `include` and `tpl` behavior. Its fixed default capabilities match
the pinned Helm v4.2.3 build, including the ordered 55-entry API-version set.

The example intentionally supports unpacked chart directories only. Repository
access, dependency downloading, installation, release storage, and cluster
operations are outside its scope and are not pygotpl library APIs.

## Security Boundary

The reusable functions are compatibility components, not a sandbox. DNS is
disabled by default, environment functions removed by Helm are absent, and
cluster lookup requires an injected callable. Filesystem and chart access are
owned entirely by the embedding application. M9 adds explicit resource-policy
controls for untrusted templates.
