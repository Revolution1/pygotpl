# gotpl

`gotpl` brings Go's `text/template` and `html/template` model to pure Python,
with first-class synchronous and asynchronous rendering and explicit Sprig,
Slim-Sprig, Sprout, and Helm function registries.

```python
import gotpl

result = gotpl.render("Hello {{.Name}}", {"Name": "Gopher"})
assert result == "Hello Gopher"
```

## Why gotpl?

- Run existing Go-style templates without embedding Go or starting a
  subprocess.
- Compile a `Template` once and safely reuse it across threads or asyncio
  tasks.
- Await Python functions directly from a template with `render_async()`.
- Render HTML with contextual escaping compatible with Go's `html/template`.
- Add function libraries explicitly, without changing the default Go
  namespace.
- Choose Go-compatible formatting by default or opt into Python-native value
  formatting.

## Choose an entry point

| Goal | Start with |
| --- | --- |
| Render a string once | `gotpl.render()` |
| Reuse a compiled text template | `gotpl.Template` |
| Render context-aware HTML | `gotpl.render_html()` or `gotpl.HTMLTemplate` |
| Call async Python functions | `gotpl.render_async()` or `Template.render_async()` |
| Compile associated files | `Template.from_sources()` |
| Render several named files | `TemplateEngine.from_sources()` |
| Add Sprig-compatible functions | `gotpl.funcs.sprig` |

[Install gotpl and render your first template](getting-started.md){ .md-button .md-button--primary }
[Browse the API](api.md){ .md-button }

!!! note "Compatibility status"

    gotpl is currently pre-1.0. Completed feature areas have oracle-backed
    compatibility evidence, while the complete Go `text/template` and
    `html/template` surfaces are still classified as partial. Consult the
    [compatibility contract](compatibility.md) before treating a specific Go
    behavior as supported.
