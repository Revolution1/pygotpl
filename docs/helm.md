# Helm Functions and Runtime Example

## Package Boundary

`gotpl.funcs.helm` provides reusable Helm-compatible function-map additions for
applications that own their rendering model. It does not expose a Chart class,
loader, release model, or Helm rendering engine.

The public `gotpl.TemplateEngine` API compiles named sources into one immutable
association, accepts an independent context for each selected source, and
provides matching synchronous and asynchronous batch APIs. Applications should
use the package-root export rather than importing runtime implementation
modules.

The repository's `examples/helm_runtime` package demonstrates how an
application can combine those pieces into a miniature Helm chart runtime. The
CLI in `examples/helm_cli.py` is an integration example, not a supported
replacement for the Helm application.

## Installation

Install the Helm serialization extra when an application uses the YAML or TOML
functions:

```console
python -m pip install "gotpl[helm]"
```

Importing `gotpl.funcs.helm` and using dependency-free functions do not require
the extra. A serializer whose dependency is absent raises an actionable
`MissingOptionalDependencyError`.

## Building an Application Function Map

Helm's `include`, `tpl`, `required`, and `fail` functions depend on application
execution state. The application supplies those late-bound callables:

```python
from gotpl import Template
from gotpl.funcs.helm import function_map


def include(name: str, value: object) -> str:
    return f"{name}:{value}"


def tpl(source: str, value: object) -> str:
    return source.replace("{{.}}", str(value))


def required(message: str, value: object) -> object:
    if value in (None, ""):
        raise ValueError(message)
    return value


def fail(message: str) -> object:
    raise ValueError(message)


functions = function_map(
    include=include,
    tpl=tpl,
    required=required,
    fail=fail,
)

template = Template('{{include "label" .}}', functions=functions)
assert template.render("demo") == "label:demo"
assert functions["getHostByName"]("example.invalid") == ""
```

The returned mapping combines the Helm text function profile with those
bindings, YAML, TOML, and decoding helpers. It removes Sprig's `env` and
`expandenv`, disables DNS by default, and uses an empty `lookup` result when no
cluster adapter is supplied. Pass `enable_dns=True` only for a runtime that
intentionally grants that capability.

`custom=` is applied last and can replace a compatibility function. Check
custom names against the returned profile before overriding unless replacement
is deliberate and tested.

## Core Cross-file Execution

Use `Template.from_sources()` when multiple sources form one template
association and the application selects the root to render:

```python
from gotpl import Template

templates = Template.from_sources(
    {
        "helpers.tpl": '{{define "greeting"}}Hello {{.}}{{end}}',
        "page.txt": '{{template "greeting" .Name}}',
    }
)

assert templates.render_template("page.txt", {"Name": "Ada"}) == "Hello Ada"
```

Definitions from every source share the same immutable namespace. Use
`render_template()` when the desired root is not the first source in the
mapping.

### Batch rendering

`TemplateEngine` adds a batch API when several named roots need independent
contexts:

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

`render_async()` awaits asynchronous functions while preserving the order of
the application-provided contexts mapping.
`with_source()` derives a new immutable engine with one added dynamic source.

## Miniature Helm Example

Within a repository checkout, the example runtime can be used directly:

```python
from examples.helm_runtime import Engine, Release, load_chart

chart = load_chart("tests/fixtures/helm/basic")
output = Engine().render(chart, release=Release(name="demo"))

assert "basic/templates/configmap.yaml" in output
assert "name: demo-basic" in output["basic/templates/configmap.yaml"]
```

The example supplies `.Values`, `.Chart`, `.Release`, `.Files`,
`.Capabilities`, `.Subcharts`, and `.Template`, plus chart traversal and Helm's
late-bound `include` and `tpl` behavior. Its fixed default capabilities match
the pinned Helm v4.2.3 build, including the ordered 55-entry API-version set.

The example intentionally supports unpacked chart directories only. Repository
access, dependency downloading, installation, release storage, and cluster
operations are outside its scope and are not pygotpl library APIs.
The example path above exists in a repository checkout; it is not installed in
the `gotpl` wheel.

## Security Boundary

The reusable functions are compatibility components, not a sandbox. DNS is
disabled by default, environment functions removed by Helm are absent, and
cluster lookup requires an injected callable. Filesystem and chart access are
owned entirely by the embedding application. Apply `SandboxPolicy`, an
`ExecutionBudget`, and operating-system isolation as described in the
[sandbox guide](sandbox.md) for untrusted templates. A strict policy rejects a
complete Helm function map unless every registered name is explicitly granted.
