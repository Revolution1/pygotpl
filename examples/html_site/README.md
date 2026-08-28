# HTML Template Directory Example

This example is the gotpl equivalent of a small Jinja2 application with a
filesystem loader, reusable header and footer partials, and multiple pages.

Run it from the repository root:

```console
uv run --frozen python -m examples.html_site --output /tmp/gotpl-html-site
```

The command writes:

```text
/tmp/gotpl-html-site/home.html
/tmp/gotpl-html-site/article.html
```

Open those files in a browser, or inspect the contextual escaping directly:

```console
grep -n "unsafe" /tmp/gotpl-html-site/article.html
```

The caller-provided `<script>` text is escaped. Values in links are processed
as URLs rather than with a single whole-document escaping pass.

See [Build an HTML Site with gotpl](../../docs/building-html-site.md) for the
Jinja2 comparison, directory-loader implementation, template association,
contextual safety explanation, and production design choices.
