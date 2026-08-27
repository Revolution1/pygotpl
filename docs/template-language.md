# Template Language

gotpl parses Go template syntax. A template is ordinary text containing actions
between `{{` and `}}`.

## Values and dot

The current value is called dot and is written as `.`. Fields, mapping keys,
and public attributes are selected with a path:

```gotemplate
Hello {{.User.Name}}
```

String mapping keys take precedence over attributes. Names beginning with an
underscore are never exposed through field lookup.

Literals include quoted and raw strings, booleans, integers, floating-point
values, complex values, and `nil`:

```gotemplate
{{printf "%s has %d messages" .Name 3}}
```

## Pipelines

A pipeline passes the result of each command as the final argument to the next
command:

```gotemplate
{{.Name | printf "Hello %s"}}
```

Functions use positional arguments. A registered Python function may be
synchronous or asynchronous; choose an async render method when any result is
awaitable.

## Conditions

```gotemplate
{{if .Enabled}}
enabled
{{else}}
disabled
{{end}}
```

`with` changes dot when its pipeline is non-empty:

```gotemplate
{{with .User}}{{.Name}}{{else}}anonymous{{end}}
```

## Ranges

```gotemplate
{{range $index, $item := .Items}}
{{$index}}: {{$item}}
{{else}}
No items
{{end}}
```

Mappings with Go-comparable homogeneous keys use Go ordering. Python-only mixed
key shapes use a stable documented fallback order. `break` and `continue` work
inside ranges.

## Variables

Declare or assign variables with `:=` and `=`:

```gotemplate
{{$name := .Name}}
{{$name = printf "%s!" $name}}
{{$name}}
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
```

## Built-in functions

The default namespace contains Go template built-ins such as `and`, `or`,
`not`, `eq`, `ne`, `lt`, `le`, `gt`, `ge`, `len`, `index`, `slice`, `call`,
`print`, `printf`, `println`, `html`, `js`, and `urlquery` where applicable.
Ecosystem libraries are never enabled implicitly.

The [compatibility contract](compatibility.md) is authoritative for supported
behavior, Python value adaptation, missing keys, and intentional differences.
