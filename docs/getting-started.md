# Getting Started

## Requirements

gotpl supports Python 3.11 and newer. Runtime use does not require Go, a C
compiler, a subprocess, or a compiled extension.

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

## Register a function

Functions must be registered before parsing because the Go grammar validates
function names during template construction:

```python
from gotpl import Template


def title(value: str) -> str:
    return value.title()


template = Template("{{title .}}", functions={"title": title})
assert template.render("hello gopher") == "Hello Gopher"
```

### Extend an already compiled template

Templates stay immutable. Use `with_functions()` to derive a template with an
added or replaced registry while reusing its compiled programs and associated
template namespace:

```python
from gotpl import Template

plain = Template("{{decorate .}}", functions={"decorate": str})
loud = plain.with_functions(
    {
        "decorate": lambda value: f"<{value}>",
        "upper": lambda value: str(value).upper(),
    }
)

assert plain.render("hello") == "hello"
assert loud.render("hello") == "<hello>"
assert loud.render_source("{{upper .}}", "hello") == "HELLO"
```

An original source cannot refer to an unknown function and then add it after
construction: Go-compatible semantic validation rejects the unknown name while
compiling. Register those names in the constructor. Newly added names are
available to later `with_source()` and `render_source()` calls. The same
`with_functions()` method is available on `HTMLTemplate` and `TemplateEngine`;
HTML derivatives rerun contextual analysis.

## Next steps

- Learn pipelines, control flow, variables, and built-ins in the
  [template language guide](template-language.md).
- Await Python callbacks and write output with backpressure in
  [async rendering](async.md).
- Add Sprig, Slim-Sprig, Sprout, Helm, or Python-native functions through
  [explicit function libraries](function-libraries.md).
- Compile associated files and batch-render named roots in the
  [multi-file guide](helm.md#core-cross-file-execution).
- Set policy and resource limits for untrusted input in the
  [sandbox guide](sandbox.md).
- Browse construction options and the complete public surface in the
  [API overview](api.md).
