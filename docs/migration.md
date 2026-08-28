# Migration Guide

## Installing and Importing

The repository is named `pygotpl`; the distribution and Python import package
are named `gotpl`.

```console
python -m pip install gotpl
```

The distribution installs compatible `goduration` and `gotime-py` versions as
dependencies; application code does not need to install them separately.

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
| `pygotpl.helm` runtime | `gotpl.exts.helm` |
| `pygotpl.helm` function map | `gotpl.funcs.helm` |
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

| Go operation | gotpl replacement |
| --- | --- |
| `template.New(...).Parse(...)` | `Template(...)` |
| `ParseFiles`, `ParseFS`, or repeated `Parse` | Application loading plus `Template.from_sources(...)` |
| `ExecuteTemplate(writer, name, data)` | `render_template_to(name, writer, data)` |
| `Clone()` followed by `Parse()` | Immutable `with_source(...)` |
| Execute several named roots with separate data | `TemplateEngine.from_sources(...).render(contexts)` |

Use `Template.from_sources()` for one associated namespace; a runnable
[multi-source example](reusable-templates.md#associate-named-sources) shows
selecting a root with `render_template()`. `TemplateEngine` is the additional
batch API for rendering several roots with independent contexts:

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

`with_source()` derives a new immutable namespace. `render_source()` and
`render_source_async()` compile dynamic source against existing definitions.
`Environment` reuses functions and construction policy across otherwise
independent templates. See
[Reusable Templates and Environments](reusable-templates.md) for the complete
selection and directory-loading guide.

## Missing Keys and Formatting

Go-compatible formatting is the default. Missing-key modes differ only when a
lookup is absent, so test the selected policy explicitly during migration:

```python
from gotpl import Template, TemplateExecutionError, TypedMap

assert Template("{{.missing}}").render({}) == "<no value>"

typed = TypedMap({}, zero=0)
assert Template("{{.missing}}", missing_key="zero").render(typed) == "0"

strict = Template("{{.missing}}", missing_key="error")
try:
    strict.render({})
except TemplateExecutionError as error:
    assert "missing" in str(error)
else:
    raise AssertionError("missing key did not fail")
```

`format_mode="python"` preserves Go template syntax and `printf` verbs but uses
Python representations and type names for the documented output paths. It is
an explicit Python extension, not the default compatibility profile.

```python
from gotpl import render

assert render("{{.}}", True) == "true"
assert render("{{.}}", True, format_mode="python") == "True"
```

Use public `TypedMap`, `GoSeq`, `GoSeq2`, `GoPointer`, `GoFormatter`, and
`FunctionResult` adapters where Python values need otherwise unavailable Go
type or result metadata. The [API overview](api.md#values-and-formatting)
describes their individual contracts; do not add an adapter unless the input
actually needs that missing metadata.

## Sprig and Ecosystem Functions

Function libraries remain opt-in:

```python
from gotpl import Template
from gotpl.funcs.sprig import text_func_map

template = Template('{{"hello world" | title}}', functions=text_func_map())
assert template.render() == "Hello World"
```

Slim-Sprig and Sprout registries, plus the lower-level Helm function map, live
under `gotpl.funcs`. They never alter the default Go function registry.
Context-aware integrations such as Helm `include` and `tpl` live under
`gotpl.exts`; see [Runtime Extensions](extensions.md). Heavy crypto and
serializer dependencies are optional extras and load only when their functions
need them.

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
See the [sandbox guide](sandbox.md) for the complete model.

## Known Compatibility Boundaries

Consult the [compatibility contract](compatibility.md) before migration. It
records measured fixture counts, Python adaptation rules, intentional
extensions, and documented
differences. Do not infer complete Go API compatibility from matching template
syntax; the public claim applies only to areas classified by that matrix.
