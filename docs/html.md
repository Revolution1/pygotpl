# HTML Templates

Use `HTMLTemplate` or the `render_html*` helpers for HTML output. They analyze
the complete template before execution and apply an escaper chosen for each
HTML, attribute, URL, CSS, JavaScript, RCDATA, or `srcset` context.

```python
from gotpl import render_html

output = render_html(
    '<a href="/search?q={{.Query}}">{{.Label}}</a>',
    {"Query": "python & go", "Label": "<Search>"},
)

assert output == '<a href="/search?q=python%20%26%20go">&lt;Search&gt;</a>'
```

Escaping the final rendered string is not equivalent: the same value needs
different treatment in HTML text, a URL, and JavaScript. Unsafe or ambiguous
template contexts fail during construction instead of rendering uncertain
output.

## Unsafe URLs

URL contexts filter unsafe protocols before applying URL escaping. The
`#ZgotmplZ` value is Go's visible fail-closed marker, not a usable sanitized
URL:

```python
from gotpl import render_html

output = render_html('<a href="{{.}}">open</a>', "javascript:alert(1)")
assert output == '<a href="#ZgotmplZ">open</a>'
```

Do not recover the rejected original value or remove this marker after
rendering. Templates whose branches end in incompatible or incomplete contexts
raise `TemplateSyntaxError` during `HTMLTemplate` construction.

## Associated templates

`HTMLTemplate.from_sources()` analyzes calls between named templates as one
association. `with_source()` creates a new immutable association and reruns the
analysis. This prevents a definition that is safe in HTML text from being
silently reused in an incompatible context.

```python
from gotpl import HTMLTemplate

template = HTMLTemplate.from_sources(
    {
        "page.html": '<a href="/search?q={{template "value" .}}">open</a>',
        "value.html": '{{define "value"}}{{.}}{{end}}',
    }
)

assert template.render("a&b") == '<a href="/search?q=a%26b">open</a>'
assert template.render_template("value", "<&") == "&lt;&amp;"
```

The same definition is rewritten for the URL query when called by `page.html`
and for HTML text when rendered directly. File discovery remains
application-owned; pass the resulting source mapping to `from_sources()`.

## Trusted content types

`HTML`, `CSS`, `HTMLAttr`, `JS`, `JSStr`, `URL`, and `Srcset` correspond to Go's
trusted `html/template` content types. They bypass specific escaping steps and
must be constructed only from content already validated for that exact
context. They are not sanitizers.

```python
from gotpl import HTML, render_html

untrusted = "<strong>review me</strong>"

assert render_html("{{.}}", untrusted) == ("&lt;strong&gt;review me&lt;/strong&gt;")
assert render_html("{{.}}", HTML(untrusted)) == untrusted
```

Wrapping caller-controlled text in `HTML` disables the protection shown in the
first assertion. Other trusted types are similarly context-specific: for
example, `JS` is not interchangeable with `CSS` or `URL`.

## Template directory example

The repository includes a runnable static-site example comparable to a small
Jinja2 application using `FileSystemLoader`. It loads a directory into one
immutable HTML association, shares header and footer definitions, and renders
separate home and article pages. Follow
[Build an HTML Site with gotpl](building-html-site.md) for the command, Jinja2
concept mapping, directory loader, partial definitions, rendering code, and
production ownership decisions.

## HTML safety is not a sandbox

Contextual escaping addresses output injection. It does not restrict template
access to Python objects or function capabilities. Use a
[`SandboxPolicy`](sandbox.md) and process isolation as appropriate for
untrusted workloads.
