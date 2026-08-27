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

## Associated templates

`HTMLTemplate.from_sources()` analyzes calls between named templates as one
association. `with_source()` creates a new immutable association and reruns the
analysis. This prevents a definition that is safe in HTML text from being
silently reused in an incompatible context.

## Trusted content types

`HTML`, `CSS`, `HTMLAttr`, `JS`, `JSStr`, `URL`, and `Srcset` correspond to Go's
trusted `html/template` content types. They bypass specific escaping steps and
must be constructed only from content already validated for that exact
context. They are not sanitizers.

## HTML safety is not a sandbox

Contextual escaping addresses output injection. It does not restrict template
access to Python objects or function capabilities. Use a
[`SandboxPolicy`](sandbox.md) and process isolation as appropriate for
untrusted workloads.
