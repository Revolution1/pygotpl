# API Reference

## Stability Boundary

The names listed in `gotpl.__all__` and the explicit exports documented below
form the 1.0 public API candidate. They follow semantic versioning after the 1.0
release. Constructor parameters and public methods documented here are part of
the same contract.

For most applications, begin with `render`, `render_async`, `Template`, or
`HTMLTemplate`. `TemplateEngine` serves multi-source runtimes. Policies,
budgets, trusted HTML types, and Go-oriented value adapters are advanced APIs
for explicit safety or compatibility requirements.

Modules under `gotpl._compat`, `gotpl.parse`, `gotpl.compile`, and VM-specific
runtime modules are implementation details. Applications must not import them.
The examples package demonstrates integrations and is not a stable chart-runtime
API.

## Convenience Rendering

### Text

```python
gotpl.render(source, data=None, **options) -> str
gotpl.render_to(source, writer, data=None, **options) -> None
await gotpl.render_async(source, data=None, **options) -> str
await gotpl.render_async_to(source, writer, data=None, **options) -> None
```

### Contextual HTML

```python
gotpl.render_html(source, data=None, **options) -> str
gotpl.render_html_to(source, writer, data=None, **options) -> None
await gotpl.render_html_async(source, data=None, **options) -> str
await gotpl.render_html_async_to(source, writer, data=None, **options) -> None
```

All convenience functions parse and compile on every call. Reuse `Template` or
`HTMLTemplate` when rendering the same source repeatedly.

Text and contextual HTML helpers expose the same named construction options.
This symmetry is part of the public signature contract, including for static
typing and generated documentation.

Text constructors and helpers accept these keyword options:

| Option | Meaning |
| --- | --- |
| `name="template"` | Source name used by definitions and diagnostics. |
| `delimiters=("{{", "}}")` | Non-empty left and right action delimiters. |
| `functions=None` | Explicit registered Python callables. |
| `missing_key="default"` | `"default"`, `"zero"`, or `"error"`. |
| `format_mode="go"` | Go-compatible `"go"` or Python-native `"python"`. |
| `sandbox=None` | Optional immutable `SandboxPolicy`. |
| `budget=None` | Optional per-render `ExecutionBudget`. |
| `extensions=None` | Optional immutable `PythonExtensions`. |

## Reusable Templates

### `Template`

`Template(source, **options)` parses and compiles a reusable immutable text
template. Construction raises `TemplateSyntaxError` for invalid source.

```python
template.render(data=None) -> str
template.render_to(writer, data=None) -> None
await template.render_async(data=None) -> str
await template.render_async_to(writer, data=None) -> None

template.render_template(name, data=None) -> str
template.render_template_to(name, writer, data=None) -> None
await template.render_template_async(name, data=None) -> str
await template.render_template_async_to(name, writer, data=None) -> None

template.with_source(source, *, name="template") -> Template
template.render_source(source, data=None, *, name="template") -> str
await template.render_source_async(source, data=None, *, name="template") -> str
```

`Template.from_sources(sources, **options)` constructs one association from an
ordered mapping of source name to source text. `with_source` returns a new
association and never mutates its parent.

### `HTMLTemplate`

`HTMLTemplate(source, **options)` provides the corresponding reusable API for
Go-style contextual HTML escaping. It supports `render`, writer, async, all
four named-template methods, `from_sources`, `with_source`, `render_source`,
and `render_source_async`. Every derived association is immutable and reruns
contextual analysis across the complete namespace before execution.

### `TemplateEngine`

`TemplateEngine.from_sources(sources, **options)` owns one reusable text
association for cross-file runtimes.

```python
engine.with_source(source, *, name="template") -> TemplateEngine
engine.render(contexts) -> dict[str, str]
await engine.render_async(contexts) -> dict[str, str]
```

Each key in `contexts` selects a named source and supplies that source's dot
value. Output preserves input mapping order.

## Values and Formatting

- `TypedMap(data, zero, key_type=None, value_type=None)` supplies an explicit
  missing element value and optional Go type names.
- `GoSeq(values)` and `GoSeq2(values)` opt into Go iterator binding semantics.
- `GoPointer(value, target_type="interface {}")` supplies explicit pointer
  formatting.
- `FunctionResult.success(value)` and `FunctionResult.failure(error, value)`
  express a Go-style function value/error result.
- `GoFormatter` and `GoFormatSpec` define the `__go_format__` protocol.
- `FormatMode` is the literal type `"go" | "python"`.
- `MissingKeyMode` is the literal type `"default" | "zero" | "error"`.

`AsyncTextWriter` is the protocol accepted by async writer methods. Its
`write(str)` method may return an integer immediately or awaitably.

## Sandboxing and Budgets

`SandboxPolicy(...)` and `SandboxPolicy.strict(...)` construct immutable
allowlists for attributes, properties, methods, registered functions, and
custom lookup. `ExecutionBudget(...)` independently limits output characters,
range iterations, associated-template depth, and function calls. Passing a
policy without a budget uses the policy's default budget.

Every text and HTML render entry point, including named-template async writers,
enforces the selected policy and a fresh budget state. See
[Sandboxing and Python extensions](sandbox.md) for the complete threat model.

## Trusted HTML Content

`HTML`, `CSS`, `HTMLAttr`, `JS`, `JSStr`, `URL`, and `Srcset` are explicit
trusted-content string types corresponding to Go `html/template` content
types. Construct them only from content already validated for the named
context. They bypass specific escaping steps and are not general sanitizers.

## Exceptions

```text
TemplateError
├── TemplateSyntaxError
└── TemplateExecutionError
    ├── AsyncRequiredError
    ├── SandboxViolationError
    └── BudgetExceededError
```

`TemplateSyntaxError` exposes `position`, `line`, and `column`.
`TemplateExecutionError` exposes `message`, optional `position`, `line`, and
`column`, plus `source_name` and `template_name`. Errors raised by application
functions are retained as `__cause__` where applicable.

Configuration mistakes such as an invalid mode, empty delimiter, invalid
function name, or non-callable registry value raise `ValueError` or `TypeError`
before execution.

## Function Libraries

Sprig and Slim-Sprig expose the following functions from
`gotpl.funcs.sprig` and `gotpl.funcs.slim_sprig`:

- `generic_func_map()`
- `text_func_map()` and `html_func_map()`
- `hermetic_text_func_map()` and `hermetic_html_func_map()`

Each returns a fresh function mapping. The complete name and evidence matrices
are linked from [Compatibility](compatibility.md). Non-hermetic maps may expose
environment, DNS, randomness, or optional cryptographic behavior.

Sprout exposes immutable inventory types, `registry(name)`, `group(name)`, and
`Handler`. Build an explicit function map with
`Handler(registry("strings"), registry("numeric")).build()`.

Helm exposes `gotpl.funcs.helm.function_map(...)`. Applications must provide
the runtime-owned `include`, `tpl`, `required`, and `fail` callables. `lookup`,
DNS, and custom overrides are explicit options. Serializer and diagnostic
differences are documented in [Helm Integration](helm.md).

## Python-Native Functions

`PythonExtensions(re_match=True)` enables `reMatch`, which uses Python
`re.search` semantics. It never replaces Sprig's RE2-compatible `regexMatch`
and is disabled by default.

## Version

`gotpl.__version__` contains the installed distribution version. Applications
should use package metadata for dependency decisions and must not parse
development-version strings as feature flags.
