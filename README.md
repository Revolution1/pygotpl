# pygotpl

The `pygotpl` repository publishes the `gotpl` Python package: a pure Python
implementation of Go's `text/template` and `html/template`, with Sprig v3
compatibility and first-class synchronous and asynchronous rendering.

The project targets observable Go behavior rather than merely similar template
syntax. Runtime use requires no Go installation, subprocess, shared library, or
compiled Python extension.

> pygotpl is pre-1.0 and is not yet published as a stable release. The parser,
> async runtime, Sprig profiles, and completed milestone scopes are heavily
> tested, while the full `text/template` and `html/template` surfaces remain
> explicitly classified as partial until their remaining conformance work is
> complete.

## Highlights

- Familiar Go template syntax for Python applications.
- Reusable immutable `Template` and `HTMLTemplate` objects.
- Opt-in immutable sandbox policies and per-render execution budgets.
- Separate sync and async virtual machines; sync rendering never starts an
  event loop.
- Async functions at callable template boundaries, including concurrent
  rendering and async writers.
- Go-compatible contextual HTML analysis and escaping rather than final-string
  escaping.
- Sprig 3.3.0 and Slim-Sprig 3.0.0 function-map profiles, including hermetic
  registries.
- Default Go-compatible formatting plus an explicit Python formatting mode.
- Go-oriented adapters for typed maps, sequences, pointers, formatter hooks,
  and value/error function results.
- Python 3.11 and newer, including CPython 3.14 and PyPy testing.
- Test-driven development against a pinned Go oracle and upstream references.
- Reproducible Go, Jinja, Mako, Chameleon, async, memory, and profiling suites.

Sprout registries and reusable Helm-compatible functions are isolated opt-in
modules under `gotpl.funcs`. A miniature Helm runtime and CLI live under
`examples/`; they do not define a public chart-runtime API. None of these
layers alter the default Go or Sprig namespaces.

## Installation

Until a release is published, install from a checkout:

```console
python -m pip install \
  ./packages/goduration ./packages/gotime .
```

Cryptographic Sprig functions use an optional capability extra:

```console
python -m pip install \
  ./packages/goduration ./packages/gotime '.[crypto]'
```

The core package remains importable and usable without that extra. Functions
that require it report the exact installation requirement when called.

The repository is a uv workspace containing the independently useful
`goduration` and `gotime` distributions plus the main `gotpl` distribution.
The deliberately incomplete formatting and RE2-compatible implementations are
private modules under `gotpl._compat`; users install no extra wheels for them.
They cover only gotpl's adopted template and Sprig matrices. Python applications
that do not require compatibility should use Python formatting and `re`
directly.

## Quick Start

Render a text template:

```python
import gotpl

output = gotpl.render("Hello {{.Name}}", {"Name": "Gopher"})
assert output == "Hello Gopher"
```

Compile once and render repeatedly:

```python
template = gotpl.Template("{{range .}}{{.}} {{end}}")

assert template.render(["one", "two"]) == "one two "
assert template.render(["three"]) == "three "
```

Use `HTMLTemplate` or `render_html` for contextual HTML output:

```python
output = gotpl.render_html(
    '<a href="/search?q={{.Query}}">{{.Label}}</a>',
    {"Query": "python & go", "Label": "<Search>"},
)

assert output == '<a href="/search?q=python%20%26%20go">&lt;Search&gt;</a>'
```

The HTML engine tracks HTML text, RCDATA, attributes, URLs, JavaScript, CSS,
`srcset`, comments, MIME-sensitive scripts, recursive named-template contexts,
and Go trusted content types. Unsafe protocols and irrecoverable template
contexts are rejected or filtered according to Go behavior.

## Async Rendering

Async templates may call both synchronous and asynchronous Python functions:

```python
import asyncio

import gotpl


async def load_user(user_id: int) -> str:
    await asyncio.sleep(0)
    return f"user-{user_id}"


async def main() -> None:
    output = await gotpl.render_async(
        "Hello {{load_user .UserID}}",
        {"UserID": 42},
        functions={"load_user": load_user},
    )
    assert output == "Hello user-42"


asyncio.run(main())
```

Reusable templates provide `render_async`, `render_async_to`,
`render_template_async`, and `render_template_async_to`. Async writer methods
may return immediately or awaitably. Synchronous rendering raises
`AsyncRequiredError` when a function returns an awaitable.

## Sprig and Slim-Sprig

Registries are explicit; Sprig functions are never injected into the default
Go built-in namespace:

```python
from gotpl import Template
from gotpl.funcs.sprig import text_func_map

template = Template(
    '{{"hello world" | title}}',
    functions=text_func_map(),
)

assert template.render() == "Hello World"
```

Available profiles include:

- `gotpl.funcs.sprig.generic_func_map()`
- `gotpl.funcs.sprig.text_func_map()`
- `gotpl.funcs.sprig.html_func_map()`
- `gotpl.funcs.sprig.hermetic_text_func_map()`
- `gotpl.funcs.sprig.hermetic_html_func_map()`
- corresponding functions under `gotpl.funcs.slim_sprig`

The complete Sprig profile is powerful rather than sandboxed: selected
functions can read environment state, perform DNS lookups, use randomness, or
invoke optional cryptography. Read the
[Sprig security boundary](docs/sprig-security.md) before rendering templates
that are not fully trusted.

## Sandboxing Untrusted Templates

Sandboxing is explicit; default construction preserves Go-compatible Python
field and method adaptation. The strict preset starts from mapping data and an
explicit function allowlist:

```python
from gotpl import ExecutionBudget, SandboxPolicy, Template

policy = SandboxPolicy.strict(
    allow_functions={"upper"},
    default_budget=ExecutionBudget(
        max_output_chars=100_000,
        max_iterations=10_000,
        max_template_depth=50,
        max_function_calls=5_000,
    ),
)

template = Template(
    "{{upper .name}}",
    functions={"upper": str.upper},
    sandbox=policy,
)

assert template.render({"name": "gopher"}) == "GOPHER"
```

Policy and budget configuration is shared by text, HTML, sync, async,
named-template, and cross-file execution. `HTMLTemplate` escaping, execution
sandboxing, and operating-system isolation solve different problems. Hostile
multi-tenant rendering still belongs in a resource-limited worker process. See
the complete [sandbox and extension guide](docs/sandbox.md).

## Python Integration

### Formatting Modes

Go-compatible formatting is the default:

```python
assert gotpl.render("{{.}}", True) == "true"
```

Python applications can keep Go template syntax while selecting Python-native
representations for ordinary output and relevant `printf` verbs:

```python
output = gotpl.render(
    '{{.}} / {{printf "%T" .}}',
    {"ready": True},
    format_mode="python",
)

assert output == "{'ready': True} / dict"
```

### Python-Native Helpers

Python helpers are opt-in and never replace compatibility names:

```python
extensions = gotpl.PythonExtensions(re_match=True)
template = gotpl.Template(
    r"{{reMatch `(?<=v)\d+` .}}",
    extensions=extensions,
)

assert template.render("v12") == "true"
```

`reMatch` uses Python `re.search`, not Go RE2. Python backtracking patterns can
be computationally expensive; do not expose caller-controlled patterns without
process isolation and input limits.

### Go-Oriented Values

- `TypedMap(data, zero=...)` preserves a map element zero value for missing
  lookups.
- `GoSeq(iterable)` and `GoSeq2(pairs)` preserve Go `iter.Seq` and `iter.Seq2`
  range-binding behavior.
- `GoPointer(value, target_type=...)` supplies explicit pointer formatting.
- `__go_format__(GoFormatSpec)` provides a Python adaptation of Go's
  `fmt.Formatter`.
- `FunctionResult.success(value)` and `FunctionResult.failure(error)` represent
  an explicit Go-style value/error function result. Ordinary tuples remain
  ordinary values.

### Errors and Named Templates

Pass `name=` when errors should identify a specific source. Execution errors
expose `position`, `line`, `column`, `source_name`, and `template_name`.

Reusable text and HTML templates support root and named execution through
`render_template`, `render_template_to`, and their async counterparts. The
association namespace is immutable and supports sibling, root, and recursive
template calls.

Use `Template.from_sources()` or `HTMLTemplate.from_sources()` to compile
multiple files into one association. The HTML form analyzes the complete
namespace contextually. `gotpl.TemplateEngine` renders selected text files with
independent contexts and returns a name-to-output mapping. `with_source()` derives another
reusable immutable association, while `render_source()` and
`render_source_async()` render dynamic source against existing definitions.
These core APIs are shared by the Helm example and future gomplate-like
integrations.

## Compatibility Status

The reference targets are Go 1.27.x, Sprig 3.3.0, Slim-Sprig 3.0.0, and Python
3.11 or newer.

| Area | Status |
| --- | --- |
| Lexer and parser | compatible; 197 Go-oracle cases |
| Synchronous `text/template` | partial; completed M2 scope and 68 oracle fixtures |
| Async execution | compatible project extension with 68 sync-parity fixtures |
| Sprig generic/text and hermetic profiles | compatible; 211-function evidence ledger |
| Slim-Sprig profiles | compatible; 164-name differential matrix |
| `html/template` | partial; completed contextual engine scope and 34 oracle fixtures |
| Sprout | M8 raw registries/groups complete; 234-function evidence ledger; optional safe generation excluded |
| Helm functions and miniature runtime example | M8 scope complete; 10 pinned Helm integration cases |

See the [compatibility contract](docs/compatibility.md) for the precise meaning
of each status, Python adaptation rules, intentional extensions, and documented
differences.

## Performance

Performance is measured only after output validation. Go is the compatibility
and native-performance reference; Jinja is the primary Python performance
reference, with Mako and Chameleon as supplementary comparisons.

On the current CPython 3.14.7 arm64 baseline:

| Representative warm path | Result |
| --- | ---: |
| Text control versus Go | 14.97x slower |
| Contextual HTML versus Go | 9.30x slower |
| Sprig-heavy versus Go | 7.62x slower |
| Text control versus Jinja | 3.38x slower |
| HTML comparison versus Jinja | 2.34x slower |
| Sync callback versus Jinja | 0.95x Jinja latency |
| Yielding async callback versus Jinja | 1.01x Jinja latency |

The main bottleneck is distributed Python-level work across instruction
dispatch, operand and command evaluation, value lookup, dynamic type checks,
callable boundaries, and Go formatting. Contextual HTML additionally spends
time in URL processing, content classification, and context-specific escaping.
A same-source Cython VM prototype improved text by only 9.39% and HTML by 3.76%,
so no native extension is shipped.

Read the
[M10 release performance report](docs/reports/m10-performance.md) and the
[complete M6 performance report](docs/reports/m6-complete-performance-report.md)
for current release comparisons, cold and warm tables, memory, profiles,
optimization priorities, limitations, and reproduction commands.

The M8 cross-file runtime and Helm example baseline is published separately in
the [Helm performance report](docs/reports/m8-helm-performance.md). It measures
core compile/warm batch execution and static/dynamic Helm cold paths against
the pinned native Helm engine.

## Documentation

The user documentation is organized as a generated MkDocs site and published
at <https://blog.kyonr.com/pygotpl/> through GitHub Pages.

- [Getting started](docs/getting-started.md)
- [Template language](docs/template-language.md)
- [Async rendering](docs/async.md)
- [HTML templates](docs/html.md)
- [Function libraries](docs/function-libraries.md)
- [API overview](docs/api.md)
- [Compatibility contract](docs/compatibility.md)
- [Sandboxing](docs/sandbox.md)
- [Migration from Go](docs/migration.md)
- [Packaging, release, and support policy](docs/support.md)

Architecture, testing, performance evidence, milestone history, dependency
policy, and release procedures remain available in the site's Maintainers
section and under `docs/reports/`.

## Development

Development dependencies are locked with uv. Go is required only for the
development oracle and comparative benchmarks.

```console
uv sync --frozen --all-groups --extra crypto
uv run --frozen pytest
```

Run the complete local gate:

```console
./scripts/check.sh
```

Build and verify the coordinated wheels on the active interpreter without Go,
a compiler, optional extras, or source-built runtime dependencies:

```console
uv run --frozen python scripts/check_wheel_matrix.py
```

Build the documentation site with strict link and reference validation:

```console
uv run --frozen --group docs mkdocs build --strict
```

The gate runs Ruff, formatting, strict Pyright, branch-aware coverage, generated
artifact checks, `gofmt`, and the pinned Go oracles.

Create or update the ignored pinned upstream source checkouts with:

```console
./scripts/sync_references.sh
```

The project follows TDD. Compatibility changes begin with reference behavior
and a failing oracle-backed fixture or test; Python-specific features add their
own async, error, writer, value-adaptation, and concurrency coverage.

## Roadmap

All locally implementable M0-M10 scopes and gates are complete. The remaining
1.0 work requires external state: observing the hosted operating-system matrix,
signing release artifacts, and publishing the three coordinated distributions.
The exact status and owner sequence are maintained
in the [M10 release-readiness report](docs/reports/m10-release-readiness.md).

## License

Copyright 2026 Revolution1. Original project work is licensed under the
[Apache License 2.0](LICENSE). Go BSD and Sprig-family MIT material retains its
upstream terms and attribution in
[Third-Party Notices](THIRD_PARTY_NOTICES.md). See the
[licensing policy](docs/licensing.md) and the completed
[upstream adaptation review](docs/reports/m0-license-review.md) before adapting
upstream material.
