# Reusable Templates and Environments

Use a reusable object when template construction should be separate from
rendering. Parsing, semantic analysis, compilation, function validation, and
HTML contextual analysis happen during construction; each render supplies only
the data for that operation.

## Choose an object

| Task | API |
| --- | --- |
| Render one text source repeatedly | `Template` |
| Render one HTML source repeatedly | `HTMLTemplate` |
| Reuse configuration across unrelated templates | `Environment` |
| Associate named text sources and render one root | `Template.from_sources()` |
| Batch-render named text roots with independent data | `TemplateEngine` |
| Associate and contextually analyze named HTML sources | `HTMLTemplate.from_sources()` |

The one-shot `render()` and `render_html()` helpers remain the shortest entry
points when reuse is unnecessary.

## Compile one source

```python
from gotpl import Template

greeting = Template("Hello {{.Name}}")

assert greeting.render({"Name": "Ada"}) == "Hello Ada"
assert greeting.render({"Name": "Linus"}) == "Hello Linus"
```

Reusable templates are immutable from the caller's perspective. A single
instance may be shared across threads and asyncio tasks; render-local counters,
extension state, and writers are not stored on it.

## Reuse construction policy

`Environment` groups configuration that several templates should share. It
does not discover files or retain a mutable loader cache.

```python
from gotpl import Environment, ExecutionBudget


def label(value: object) -> str:
    return f"item:{value}"


environment = Environment(
    functions={"label": label},
    missing_key="error",
    budget=ExecutionBudget(max_output_chars=100_000),
)

text = environment.from_string("{{label .Value}}")
assert text.render({"Value": 3}) == "item:3"

html = environment.from_html_string("<strong>{{label .Value}}</strong>")
assert html.render({"Value": "<&"}) == "<strong>item:&lt;&amp;</strong>"
```

Use `with_functions()` or `with_extensions()` to derive another environment.
Construction rejects accidental name collisions instead of silently replacing
the selected compatibility profile.

```python
from gotpl import Environment

base = Environment(functions={"prefix": lambda value: f"base:{value}"})
derived = base.with_functions({"suffix": lambda value: f"{value}:derived"})

assert base.from_string("{{prefix .}}").render("x") == "base:x"
assert derived.from_string("{{suffix .}}").render("x") == "x:derived"
```

Deriving an environment does not modify templates already constructed from the
original environment.

## Associate named sources

Go templates resolve `define`, `template`, and `block` across one associated
namespace. Provide the complete source mapping before rendering:

```python
from gotpl import Template

templates = Template.from_sources(
    {
        "partials.tpl": '{{define "greeting"}}Hello {{.}}{{end}}',
        "page.txt": '{{template "greeting" .Name}}',
    }
)

assert templates.render_template("page.txt", {"Name": "Ada"}) == "Hello Ada"
```

Mapping keys are diagnostic source names. Definitions from every source share
one immutable association, while `render_template()` selects the root to
execute.

For HTML, construct the complete association with `HTMLTemplate.from_sources()`
or `Environment.from_html_sources()`. The analyzer follows calls between named
templates and rewrites each use for its actual HTML, URL, CSS, JavaScript, or
text context. See [HTML Templates](html.md#associated-templates).

## Batch-render independent roots

`TemplateEngine` is a small batch facade over a text association. Each selected
root receives independent data:

```python
from gotpl import Environment

engine = Environment().from_sources(
    {
        "labels.tpl": '{{define "label"}}{{.prefix}}:{{.value}}{{end}}',
        "first.txt": '{{template "label" .}}',
        "second.txt": '{{template "label" .}}',
    }
)

rendered = engine.render(
    {
        "first.txt": {"prefix": "one", "value": 1},
        "second.txt": {"prefix": "two", "value": 2},
    }
)

assert rendered == {
    "first.txt": "one:1",
    "second.txt": "two:2",
}
```

The result follows the insertion order of the caller's contexts mapping. Use
`render_template()` when only one root is needed and `render_async()` or
`render_template_async()` when a registered function may be asynchronous.

## Load a directory

File discovery is application-owned so callers can choose encodings, suffixes,
ignore rules, package resources, virtual filesystems, or reload policy. A small
directory loader can pass relative POSIX names to an environment:

```python
from pathlib import Path

from gotpl import Environment


def load_sources(directory: str | Path) -> dict[str, str]:
    root = Path(directory)
    return {
        path.relative_to(root).as_posix(): path.read_text(encoding="utf-8")
        for path in sorted(root.rglob("*.gotpl"))
        if path.is_file()
    }


engine = Environment().from_sources(load_sources("templates"))
```

Load and compile once at application startup when the files are stable. For a
complete contextually escaped site example with reusable header and footer
partials, see [Build an HTML Site](building-html-site.md).

## Derive a compiled association

`with_source()` and `with_functions()` return new reusable objects. They do not
mutate the original:

```python
from gotpl import Template

base = Template.from_sources({"partials.tpl": '{{define "label"}}base:{{.}}{{end}}'})
page = base.with_source('{{template "label" .}}', name="page.txt")

assert page.render_template("page.txt", "value") == "base:value"
```

`render_source()` is different: it compiles an ad hoc source for that call and
captures its output. Prefer a retained association when the same source will be
rendered repeatedly.

## Next steps

- Add pure compatibility functions through [Function Libraries](function-libraries.md).
- Add context-aware behavior through [Runtime Extensions](extensions.md).
- Use contextual output analysis through [HTML Templates](html.md).
- Await callbacks and writers through [Async Rendering](async.md).
- Apply object access and resource limits through [Sandboxing](sandbox.md).
