# Getting Started

## Requirements

gotpl supports CPython 3.11 through 3.14 and PyPy 3.11. Runtime use does not
require Go, a C compiler, a subprocess, or a compiled extension. See the
[support policy](support.md#python-and-platform-support) for the exact tested
matrix and pre-1.0 versioning boundary.

## Installation

```console
python -m pip install gotpl
```

This installs compatible `goduration` and `gotime` releases automatically.
Optional capabilities are installed only when an application needs them:

```console
python -m pip install "gotpl[crypto]"
python -m pip install "gotpl[helm]"
```

Installing an extra makes its dependencies available; it does not implicitly
add functions to a template. Function registries remain explicit.

Install `goduration` or `gotime` directly only when using those standalone APIs
without the template engine:

```console
python -m pip install goduration
python -m pip install gotime
```

## Render a template

```python
from gotpl import render

message = render(
    "{{if .Admin}}Admin{{else}}User{{end}}: {{.Name}}",
    {"Admin": True, "Name": "Ada"},
)

assert message == "Admin: Ada"
```

Mapping keys and public Python attributes can be selected with Go field syntax.
Use exported-looking names when sharing a template with a Go application.

!!! important "Rendering HTML"

    `render()` produces text and does not apply contextual HTML escaping. Use
    `render_html()` or `HTMLTemplate` for HTML output; the
    [HTML guide](html.md) contains a runnable escaping example and explains the
    trusted-content boundary.

## Compile once, render many times

Convenience functions parse and compile on every call. Keep a reusable
`Template` when the source does not change:

```python
from gotpl import Template

greeting = Template("Hello {{.Name}}")

assert greeting.render({"Name": "Ada"}) == "Hello Ada"
assert greeting.render({"Name": "Linus"}) == "Hello Linus"
```

Templates are immutable from the caller's perspective and may be shared across
threads and asyncio tasks.

## Reuse configuration across templates

Functions must be registered before parsing because the Go grammar validates
function names during template construction. Use an `Environment` when several
templates share functions, missing-key behavior, delimiters, sandbox policy, or
runtime extensions:

```python
from gotpl import Environment


def title(value: str) -> str:
    return value.title()


environment = Environment(
    functions={"title": title},
    missing_key="error",
)

greeting = environment.from_string("Hello {{title .Name}}")
heading = environment.from_html_string("<h1>{{title .Name}}</h1>")

assert greeting.render({"Name": "ada"}) == "Hello Ada"
assert heading.render({"Name": "linus"}) == "<h1>Linus</h1>"
```

An environment is immutable configuration, not a filesystem loader or mutable
template cache. Construct it once, then create as many unrelated templates or
complete source associations as the application needs. The
[reusable-template guide](reusable-templates.md) explains object selection,
directory loading, `TemplateEngine`, and immutable derivation.

## Next steps

- Learn pipelines, control flow, variables, and built-ins in the
  [template language guide](template-language.md).
- Await Python callbacks and write output with backpressure in
  [async rendering](async.md).
- Add Sprig, Slim-Sprig, Sprout, Helm, or Python-native functions through
  [explicit function libraries](function-libraries.md).
- Compile associated files, load directories, and batch-render named roots in
  [reusable templates and environments](reusable-templates.md).
- Add associated or dynamic rendering behavior through
  [runtime extensions](extensions.md).
- Set policy and resource limits for untrusted input in the
  [sandbox guide](sandbox.md).
- Browse construction options and the complete public surface in the
  [API overview](api.md).
