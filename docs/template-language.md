# Template Language

gotpl parses Go template syntax. A template is ordinary text containing actions
between `{{` and `}}`.

## Values and dot

The current value is called dot and is written as `.`. Fields, mapping keys,
and public attributes are selected with a path:

```gotemplate
Hello {{.User.Name}}
```

String mapping keys take precedence over attributes. Mapping keys may begin
with an underscore, but private Python attributes beginning with an underscore
are not exposed.

Literals include quoted and raw strings, booleans, integers, floating-point
values, complex values, and `nil`:

```gotemplate
{{printf "%s has %d messages" .Name 3}}
```

## Pipelines

A pipeline passes the result of each command as the final argument to the next
command. This is why the value appears after the format string below:

```python
from gotpl import render

result = render('{{.Name | printf "Hello %s"}}', {"Name": "Ada"})
assert result == "Hello Ada"
```

Functions use positional arguments. A registered Python function may be
synchronous or asynchronous; choose an async render method when any result is
awaitable.

## Conditions

```python
from gotpl import render

source = "{{if .Enabled}}enabled{{else}}disabled{{end}}"

assert render(source, {"Enabled": True}) == "enabled"
assert render(source, {"Enabled": False}) == "disabled"
```

`with` changes dot when its pipeline is non-empty:

```gotemplate
{{with .User}}{{.Name}}{{else}}anonymous{{end}}
```

## Ranges

```python
from gotpl import render

source = "{{range $index, $item := .Items}}{{$index}}={{$item}};{{else}}empty{{end}}"

assert render(source, {"Items": ["a", "b"]}) == "0=a;1=b;"
assert render(source, {"Items": []}) == "empty"
```

Mappings with Go-comparable homogeneous keys use Go ordering. Python-only mixed
key shapes use a stable documented fallback order. `break` and `continue` work
inside ranges.

## Variables

Declare a new variable with `:=` and assign an existing variable with `=`:

```python
from gotpl import render

source = '{{$name := .Name}}{{$name = printf "%s!" $name}}{{$name}}'
assert render(source, {"Name": "Ada"}) == "Ada!"
```

`$` starts as the root value. Named template calls receive their explicit dot
and do not dynamically inherit caller variables, matching Go.

## Named templates

```gotemplate
{{define "label"}}{{.Name}}: {{.Value}}{{end}}
{{template "label" .}}
```

Use `Template.from_sources()` to associate definitions from several named
sources. Use `render_template()` to execute a particular root or definition.
See the runnable [associated-source example](helm.md#core-cross-file-execution).
`block` is shorthand for defining a default template and invoking it in place.

## Whitespace and comments

Comments do not render:

```gotemplate
{{/* explanatory comment */}}
```

A minus sign adjacent to an action delimiter trims surrounding whitespace:

```gotemplate
before {{- .Value -}} after
```

Custom delimiters are an immutable construction option:

```python
from gotpl import Template

template = Template("Hello [[.Name]]", delimiters=("[[", "]]"))
assert template.render({"Name": "Ada"}) == "Hello Ada"
```

## Missing keys

The default mode renders a missing dynamically typed mapping value as
`<no value>`. Select `missing_key="error"` when omission must fail instead of
silently reaching the output:

```python
from gotpl import Template, TemplateExecutionError

assert Template("{{.missing}}").render({}) == "<no value>"

strict = Template("{{.missing}}", missing_key="error")
try:
    strict.render({})
except TemplateExecutionError as error:
    assert "missing" in str(error)
else:
    raise AssertionError("missing key did not fail")
```

`missing_key="zero"` uses the element zero value when type information exists.
Plain Python mappings have no declared element type; use `TypedMap` when a
specific Go-style zero value matters. The [API overview](api.md#values-and-formatting)
documents that adapter.

## Built-in functions

The default namespace contains Go template built-ins such as `and`, `or`,
`not`, `eq`, `ne`, `lt`, `le`, `gt`, `ge`, `len`, `index`, `slice`, `call`,
`print`, `printf`, `println`, `html`, `js`, and `urlquery` where applicable.
Ecosystem libraries are never enabled implicitly.

`and` and `or` return the selected operand rather than coercing it to a boolean,
and evaluate left to right:

```python
from gotpl import render

assert render('{{or .Primary "fallback"}}', {"Primary": ""}) == "fallback"
assert render("{{index . 1}}", ["zero", "one"]) == "one"
```

See [Built-in Functions](builtin-functions.md) for every signature, behavior,
boundary, example, and implementation-source location.

The [compatibility contract](compatibility.md) is authoritative for supported
behavior, Python value adaptation, missing keys, and intentional differences.
