# Getting Started

## Requirements

gotpl supports Python 3.11 and newer. Runtime use does not require Go, a C
compiler, a subprocess, or a compiled extension.

## Installation

gotpl has not yet published its first stable package-index release. Install all
three workspace distributions from a checkout:

```console
python -m pip install ./packages/goduration ./packages/gotime .
```

Optional capabilities are installed only when an application needs them:

```console
python -m pip install './packages/goduration' './packages/gotime' '.[crypto]'
python -m pip install './packages/goduration' './packages/gotime' '.[helm]'
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

Continue with the [template language guide](template-language.md),
[async rendering](async.md), or [function libraries](function-libraries.md).
