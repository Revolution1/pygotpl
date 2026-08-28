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
| Reuse configuration across templates | [`gotpl.Environment`](reusable-templates.md#reuse-construction-policy) |
| Associate files or load a directory | [Reusable Templates and Environments](reusable-templates.md) |
| Render context-aware HTML | [`gotpl.render_html()` or `gotpl.HTMLTemplate`](html.md) |
| Call async Python functions | [`gotpl.render_async()` or `gotpl.Template.render_async()`](async.md) |
| Add Sprig-compatible functions | [`gotpl.funcs.sprig`](function-libraries.md#sprig) |
| Add context-aware behavior | [`gotpl.exts` runtime extensions](extensions.md) |
| Restrict untrusted templates | [Sandbox policy and process isolation](sandbox.md) |
| Build a Jinja2-style HTML site | [HTML site integration guide](building-html-site.md) |
| Render a complete local Helm chart | [Build a Helm Renderer](building-helm.md) |
| Migrate an existing Go template | [Migration Guide](migration.md) |

[Install gotpl and render your first template](getting-started.md){ .md-button .md-button--primary }
[Browse the API](api.md){ .md-button }

!!! note "Compatibility status"

    gotpl is currently pre-1.0. Completed feature areas have oracle-backed
    compatibility evidence, while the complete Go `text/template` and
    `html/template` surfaces are still classified as partial. Consult the
    [compatibility contract](compatibility.md) before treating a specific Go
    behavior as supported.
