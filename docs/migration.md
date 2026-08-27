# Migration Guide

## Installing and Importing

The repository is named `pygotpl`; the distribution and Python import package
are named `gotpl`.

From a checkout:

```console
python -m pip install ./packages/goduration ./packages/gotime .
```

Application code imports `gotpl`:

```python
from gotpl import HTMLTemplate, Template, render, render_async
```

## Pre-1.0 Python Import Changes

The M10 package review made these import paths canonical:

| Earlier development path | Current path |
| --- | --- |
| `pygotpl` | `gotpl` |
| `pygotpl.sprig` | `gotpl.funcs.sprig` |
| `pygotpl.slim_sprig` | `gotpl.funcs.slim_sprig` |
| `pygotpl.sprout` | `gotpl.funcs.sprout` |
| `pygotpl.helm` | `gotpl.funcs.helm` |
| `pygotpl.extras.PythonExtensions` | `gotpl.pythonic.PythonExtensions` |
| `gofmt` distribution | private `gotpl._compat`; use gotpl public formatting APIs |
| `goregexp` distribution | private `gotpl._compat`; use a function registry or `gotpl.pythonic` |

No legacy alias is shipped. These paths were never part of a published stable
release, and retaining two module identities would make typing, tracebacks,
documentation, caches, and support ambiguous before the 1.0 freeze.

Do not import `gotpl._compat`. It contains incomplete implementation support,
not a public Go `fmt` or `regexp` product.

## Moving a Go Text Template

Most template source remains unchanged. Supply Go-style exported field names as
mapping keys or Python attributes:

```python
from gotpl import Template

template = Template("Hello {{.User.Name}}")
output = template.render({"User": {"Name": "Ada"}})

assert output == "Hello Ada"
```

`Template` parses and compiles once and is immutable from a caller's
perspective. Reuse it across renders, threads, and asyncio tasks.

Go's `template.FuncMap` becomes a Python callable mapping supplied before
parsing:

```python
def upper(value: str) -> str:
    return value.upper()


template = Template("{{upper .}}", functions={"upper": upper})
assert template.render("gopher") == "GOPHER"
```

Function names must exist at construction because Go template parsing validates
them. A synchronous render raises `AsyncRequiredError` if a callback returns an
awaitable; use `render_async` for mixed synchronous and asynchronous callbacks.

## Associated and Cross-File Templates

Use `Template.from_sources` when Go code would assemble associated templates
with `ParseFiles`, `ParseFS`, or repeated parsing:

```python
from gotpl import TemplateEngine

engine = TemplateEngine.from_sources(
    {
        "helpers.tpl": '{{define "label"}}{{.name}}:{{.value}}{{end}}',
        "first.txt": '{{template "label" .}}',
        "second.txt": '{{template "label" .}}',
    }
)

assert engine.render(
    {
        "first.txt": {"name": "first", "value": 1},
        "second.txt": {"name": "second", "value": 2},
    }
) == {"first.txt": "first:1", "second.txt": "second:2"}
```

`with_source` derives a new immutable namespace. `render_source` and
`render_source_async` compile dynamic source against existing definitions.
These are the core primitives used by the miniature Helm example and intended
for gomplate-like runtimes.

## Missing Keys and Formatting

Go-compatible formatting is the default. Select missing-key behavior at
construction:

```python
Template("{{.missing}}", missing_key="default")
Template("{{.missing}}", missing_key="zero")
Template("{{.missing}}", missing_key="error")
```

`format_mode="python"` preserves Go template syntax and `printf` verbs but uses
Python representations and type names for the documented output paths. It is
an explicit Python extension, not the default compatibility profile.

Use public `TypedMap`, `GoSeq`, `GoSeq2`, `GoPointer`, `GoFormatter`, and
`FunctionResult` adapters where Python values need otherwise unavailable Go
type or result metadata.

## Sprig and Ecosystem Functions

Function libraries remain opt-in:

```python
from gotpl import Template
from gotpl.funcs.sprig import text_func_map

template = Template('{{"hello world" | title}}', functions=text_func_map())
assert template.render() == "Hello World"
```

Slim-Sprig, Sprout, and Helm maps live under `gotpl.funcs`. They never alter
the default Go function registry. Heavy crypto and serializer dependencies are
optional extras and load only when their functions need them.

## HTML Templates

Replace Go `html/template` execution with `HTMLTemplate` or `render_html`, not
with a text template plus final-string escaping:

```python
from gotpl import HTMLTemplate

template = HTMLTemplate('<a href="{{.URL}}">{{.Label}}</a>')
assert template.render({"URL": "/a b", "Label": "<A>"}) == (
    '<a href="/a%20b">&lt;A&gt;</a>'
)
```

The analyzer tracks contextual HTML, URL, CSS, and JavaScript state across
associated template calls. Trusted Go content types have explicit gotpl
counterparts.

## Untrusted Templates

Go compatibility does not imply a sandbox. Apply `SandboxPolicy.strict()` and
an `ExecutionBudget` explicitly, start from a minimal function map, and isolate
hostile workloads in an operating-system-limited worker. Contextual HTML
escaping, capability sandboxing, and process isolation are separate boundaries.
See `docs/sandbox.md` for the complete model.

## Known Compatibility Boundaries

Consult `docs/compatibility.md` before migration. It records measured fixture
counts, Python adaptation rules, intentional extensions, and documented
differences. Do not infer complete Go API compatibility from matching template
syntax; the public claim applies only to areas classified by that matrix.
