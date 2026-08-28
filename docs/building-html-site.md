# Build an HTML Site with gotpl

This guide builds a small static site comparable to a Jinja2 application using
`FileSystemLoader`. The application loads one template directory, shares header
and footer definitions, and renders separate home and article pages with Go
`html/template` contextual escaping.

The complete runnable project is under `examples/html_site`.

## Run the example

From a repository checkout:

```console
uv run --frozen python -m examples.html_site \
  --output /tmp/gotpl-html-site
```

The command writes:

```text
/tmp/gotpl-html-site/home.html
/tmp/gotpl-html-site/article.html
```

Open either file in a browser or inspect the generated content:

```console
grep -n "unsafe" /tmp/gotpl-html-site/article.html
```

The article deliberately contains caller-provided `<script>` text. The output
contains escaped text rather than an executable element.

## Directory layout

```text
examples/html_site/
├── renderer.py
├── __main__.py
└── templates/
    ├── partials/
    │   ├── header.html.gotpl
    │   └── footer.html.gotpl
    └── pages/
        ├── home.html.gotpl
        └── article.html.gotpl
```

Files under `partials/` define reusable associated templates. Files under
`pages/` are actual render roots. Directory names are an application convention;
gotpl receives relative source names and does not assign behavior by path.

## Jinja2 and gotpl

A typical Jinja2 application gives its environment a filesystem loader and
resolves a page lazily:

```python
from jinja2 import Environment, FileSystemLoader, select_autoescape

environment = Environment(
    loader=FileSystemLoader("templates"),
    autoescape=select_autoescape(),
)
html = environment.get_template("pages/home.html").render(context)
```

gotpl makes the application discover files and compiles the complete immutable
association before rendering:

```python
from gotpl import Environment

sources = load_template_directory("templates")
templates = Environment().from_html_sources(sources)
html = templates.render_template("pages/home.html.gotpl", context)
```

| Concern | Jinja2 application | gotpl application |
| --- | --- | --- |
| Directory discovery | `FileSystemLoader` | application-owned loader |
| Reusable parts | include, macro, or inheritance | associated `define` and `template` |
| Page selection | `get_template()` | `render_template()` |
| Escaping | configured autoescape policy | Go contextual HTML analysis |
| Reuse | environment and template cache | immutable compiled association |

This is not a syntax translation layer. Existing Jinja templates must be
rewritten in Go template syntax, and application-specific filters must be
registered as functions.

## Load the directory

The example loader is intentionally ordinary Python:

```python
from pathlib import Path


def load_template_directory(directory: str | Path) -> dict[str, str]:
    root = Path(directory)
    if not root.is_dir():
        raise ValueError(f"template path {root} must be a directory")
    sources = {
        path.relative_to(root).as_posix(): path.read_text(encoding="utf-8")
        for path in sorted(root.rglob("*.gotpl"))
        if path.is_file()
    }
    if not sources:
        raise ValueError(f"template directory {root} contains no *.gotpl files")
    return sources
```

Keeping discovery outside gotpl lets an application choose package resources,
encodings, suffixes, ignore rules, reload behavior, or a virtual filesystem.

## Define shared parts

The header owns the opening document structure and leaves the renderer in HTML
text context:

```gotemplate
{{define "site.header" -}}
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{{.Title}} · {{.SiteName}}</title>
</head>
<body>
  <header><a href="/home.html">{{.SiteName}}</a></header>
  <main>
{{- end}}
```

The footer closes the shared structure:

```gotemplate
{{define "site.footer" -}}
  </main>
  <footer>&copy; {{.Year}} {{.SiteName}}</footer>
</body>
</html>
{{- end}}
```

Definitions from both files become part of the same association. They do not
produce standalone output unless selected or called.

## Render a page

A page calls both definitions and supplies its content between them:

```gotemplate
{{template "site.header" .}}
    <article>
      <h1>{{.Article.Title}}</h1>
      <p>{{.Article.Body}}</p>
      <a href="{{.Article.SourceURL}}">Source</a>
    </article>
{{template "site.footer" .}}
```

Compile the directory once and retain the result:

```python
from gotpl import Environment


class SiteRenderer:
    def __init__(self, directory: str) -> None:
        sources = load_template_directory(directory)
        self.templates = Environment().from_html_sources(sources)

    def render_page(self, name: str, context: object) -> str:
        return self.templates.render_template(name, context)
```

Then render each page with its own root data:

```python
renderer = SiteRenderer("examples/html_site/templates")

home = renderer.render_page(
    "pages/home.html.gotpl",
    {
        "Title": "Home",
        "SiteName": "gotpl Journal",
        "Year": 2026,
        "Navigation": [],
        "Heading": "HTML templates without Go",
        "Introduction": "Compile once and render safely.",
        "Features": ["Shared partials", "Contextual escaping"],
    },
)

assert "<title>Home · gotpl Journal</title>" in home
```

The repository example adds `render_pages()` and a CLI that writes each page to
an output directory. The same compiled association is safe to reuse across
threads and asyncio tasks.

## Contextual safety

Go HTML templates do not apply one generic escape operation to the finished
document. The analyzer determines where each action appears:

```gotemplate
<p>{{.Article.Body}}</p>
<a href="{{.Article.SourceURL}}">Source</a>
```

The body is escaped as HTML text. The link value is filtered and escaped as a
URL embedded in an HTML attribute. Unsafe protocols fail closed with
`#ZgotmplZ`.

Do not wrap caller-controlled content in `gotpl.HTML`, `gotpl.URL`, or another
trusted content type. Those types assert that validation already happened; they
are not sanitizers. See [HTML Templates](html.md) for the complete contextual
escaping boundary and [Sandboxing](sandbox.md) for object access and resource
limits.

## Production choices owned by the application

The example is deliberately small. A production site renderer should decide:

- where templates come from and whether reload is allowed;
- whether an empty or unknown page name is an application error;
- which Python functions and extensions are registered;
- how data is validated before rendering;
- whether output is written atomically;
- which sandbox and execution budgets apply;
- how generated pages are cached and invalidated.

Keep the compiled association long-lived when sources and policy are stable.
Rebuild it explicitly when templates change rather than mutating a shared
loader cache during renders.
