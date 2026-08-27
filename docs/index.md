# gotpl

`gotpl` brings Go's `text/template` and `html/template` model to pure Python,
with first-class synchronous and asynchronous rendering and explicit Sprig,
Slim-Sprig, Sprout, and Helm function registries.

```python
import gotpl

result = gotpl.render("Hello {{.Name}}", {"Name": "Gopher"})
assert result == "Hello Gopher"
```

## Choose an entry point

| Goal | Start with |
| --- | --- |
| Render a string once | [`gotpl.render()`](getting-started.md#render-a-template) |
| Reuse a compiled text template | [`gotpl.Template`](getting-started.md#compile-once-render-many-times) |
| Render context-aware HTML | [`gotpl.render_html()` or `gotpl.HTMLTemplate`](html.md) |
| Call async Python functions | [`gotpl.render_async()` or `gotpl.Template.render_async()`](async.md) |
| Compile associated files | [`gotpl.Template.from_sources()`](helm.md#core-cross-file-execution) |
| Render several named files | [`gotpl.TemplateEngine.from_sources()`](helm.md#batch-rendering) |
| Add Sprig-compatible functions | [`gotpl.funcs.sprig`](function-libraries.md#sprig) |

[Install gotpl and render your first template](getting-started.md){ .md-button .md-button--primary }
[Browse the API](api.md){ .md-button }

!!! note "Compatibility status"

    gotpl is currently pre-1.0. Completed feature areas have oracle-backed
    compatibility evidence, while the complete Go `text/template` and
    `html/template` surfaces are still classified as partial. Consult the
    [compatibility contract](compatibility.md) before treating a specific Go
    behavior as supported.
