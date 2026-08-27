# pygotpl

`pygotpl` publishes `gotpl`, a pure Python implementation of Go's
`text/template` and `html/template`, with Sprig v3 compatibility and separate
synchronous and asynchronous rendering paths. Runtime use requires no Go
installation, subprocess, shared library, or compiled extension.

> `pygotpl` is pre-1.0. Completed areas have oracle-backed compatibility
> evidence, while the complete Go
> `text/template` and `html/template` surfaces remain classified as partial.
> Check the [compatibility contract](docs/compatibility.md) before relying on a
> specific Go behavior.

## Installation

```console
python -m pip install gotpl
```

Optional cryptographic and Helm capabilities are available through the
`crypto` and `helm` extras. `gotpl` installs its compatible `goduration` and
`gotime` dependencies automatically. See
[Getting Started](docs/getting-started.md) for the exact commands and supported
Python versions.

## Quick Start

Render a text template once:

```python
import gotpl

result = gotpl.render("Hello {{.Name}}", {"Name": "Gopher"})
assert result == "Hello Gopher"
```

Compile a template when the same source will be rendered repeatedly:

```python
import gotpl

greeting = gotpl.Template("Hello {{.Name}}")

assert greeting.render({"Name": "Ada"}) == "Hello Ada"
assert greeting.render({"Name": "Linus"}) == "Hello Linus"
```

For HTML output, use the contextual HTML API rather than escaping a completed
string:

```python
import gotpl

result = gotpl.render_html(
    '<a href="/search?q={{.Query}}">{{.Label}}</a>',
    {"Query": "python & go", "Label": "<Search>"},
)

assert result == '<a href="/search?q=python%20%26%20go">&lt;Search&gt;</a>'
```

## Where to Go Next

- [Getting Started](docs/getting-started.md) — installation, repeated renders,
  and registering Python functions.
- [Template Language](docs/template-language.md) — pipelines, control flow,
  variables, associations, and built-ins.
- [Async Rendering](docs/async.md) — async callbacks, writers, cancellation,
  and concurrency.
- [HTML Templates](docs/html.md) — contextual escaping and trusted content.
- [Function Libraries](docs/function-libraries.md) — Sprig, Slim-Sprig,
  Sprout, Helm, and Python-native profiles.
- [Sandboxing](docs/sandbox.md) — policies, budgets, and the security boundary.
- [Multi-file and Helm Integration](docs/helm.md) — associated sources and
  batch rendering.
- [API Overview](docs/api.md) — the candidate 1.0 public surface.
- [Compatibility](docs/compatibility.md) and
  [Performance](docs/performance.md) — measured support and benchmark evidence.

The generated documentation site is published at
<http://blog.kyonr.com/pygotpl/>.

## Development

Development dependencies are locked with uv. Go is needed only for reference
oracles and comparative benchmarks.

```console
uv sync --frozen --all-groups --extra crypto
./scripts/check.sh
```

See [Contributing](CONTRIBUTING.md), [Testing](docs/testing.md), and the active
[M10 milestone](docs/milestones/m10-v1.md) before changing compatibility
behavior.

## License

Copyright 2026 Revolution1. Original project work is licensed under the
[Apache License 2.0](LICENSE). Upstream terms and attribution are recorded in
[Third-Party Notices](THIRD_PARTY_NOTICES.md).
