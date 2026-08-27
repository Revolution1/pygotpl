# API Overview

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

This page explains how the public pieces fit together. The generated
[gotpl reference](reference/gotpl.md) owns complete signatures and docstrings;
the guides linked below own runnable task-oriented examples.

## Convenience Rendering

The [Getting Started](getting-started.md) guide contains the canonical text
example, while the [HTML](html.md) and [Async](async.md) guides demonstrate the
contextual and awaitable variants.

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
template.with_functions(functions) -> Template
template.render_source(source, data=None, *, name="template") -> str
await template.render_source_async(source, data=None, *, name="template") -> str
```

`Template.from_sources(sources, **options)` constructs one association from an
ordered mapping of source name to source text. `with_source` returns a new
association and never mutates its parent. `with_functions` returns an immutable
derivative that reuses compiled programs while adding or replacing registered
callbacks. See the runnable
[associated-source example](helm.md#core-cross-file-execution).

### `HTMLTemplate`

`HTMLTemplate(source, **options)` provides the corresponding reusable API for
Go-style contextual HTML escaping. It supports `render`, writer, async, all
four named-template methods, `from_sources`, `with_source`, `with_functions`, `render_source`,
and `render_source_async`. Every derived association is immutable and reruns
contextual analysis across the complete namespace before execution.

### `TemplateEngine`

`TemplateEngine.from_sources(sources, **options)` owns one reusable text
association for cross-file runtimes.

```python
engine.with_source(source, *, name="template") -> TemplateEngine
engine.with_functions(functions) -> TemplateEngine
engine.render(contexts) -> dict[str, str]
await engine.render_async(contexts) -> dict[str, str]
```

Each key in `contexts` selects a named source and supplies that source's dot
value. Output preserves input mapping order. The
[batch-rendering example](helm.md#batch-rendering) shows the complete
construction and result.

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

### Typed maps and Go iterator binding

Use `TypedMap` only when a Python mapping needs a known Go element zero or type
name. `GoSeq` and `GoSeq2` distinguish Go iterator binding from an ordinary
Python iterable:

```python
from gotpl import GoSeq2, TypedMap, render

values = TypedMap({"present": 7}, zero=0)
assert render('{{index . "missing"}}', values) == "0"
assert render("{{.missing}}", values, missing_key="zero") == "0"

pairs = GoSeq2([("a", 1), ("b", 2)])
source = "{{range $key, $value := .}}{{$key}}={{$value}};{{end}}"
assert render(source, pairs) == "a=1;b=2;"
```

`GoSeq` permits zero or one range binding. `GoSeq2` yields keys for one binding
and key/value pairs for two bindings.

### Pointer and formatter metadata

`GoPointer` supplies pointer nil-ness and a Go target type that an ordinary
Python object cannot express. Implement `GoFormatter` when a value must own the
complete result of a Go `printf` formatting operation:

```python
from gotpl import GoFormatSpec, GoPointer, render

pointer = GoPointer(None, target_type="widget")
assert render('{{printf "%T/%v" . .}}', pointer) == "*widget/<nil>"


class CustomValue:
    def __go_format__(self, spec: GoFormatSpec) -> str:
        return f"{spec.verb}:{spec.flags}:{spec.width}:{spec.precision}"


assert render('{{printf "%#+8.3z" .}}', CustomValue()) == "z:#+:8:3"
```

The formatter return value must be a string and is the complete formatted
representation, not an intermediate value for another formatting pass.

### Explicit value/error results

Ordinary Python functions signal failure by raising. `FunctionResult` is for a
callback that deliberately models Go's `(value, error)` result without treating
every two-item tuple as an error pair:

```python
from gotpl import FunctionResult, Template, TemplateExecutionError


def load() -> FunctionResult:
    return FunctionResult.failure(RuntimeError("load failed"))


template = Template("before/{{load}}/after", functions={"load": load})
try:
    template.render()
except TemplateExecutionError as error:
    assert isinstance(error.__cause__, RuntimeError)
    assert str(error.__cause__) == "load failed"
else:
    raise AssertionError("failed result did not stop rendering")
```

## Sandboxing and Budgets

`SandboxPolicy(...)` and `SandboxPolicy.strict(...)` construct immutable
allowlists for attributes, properties, methods, registered functions, and
custom lookup. `ExecutionBudget(...)` independently limits output characters,
range iterations, associated-template depth, and function calls. Passing a
policy without a budget uses the policy's default budget.

Every text and HTML render entry point, including named-template async writers,
enforces the selected policy and a fresh budget state. See
[Sandboxing and Python extensions](sandbox.md) for runnable policy, object
allowlist, and budget-failure examples and for the complete threat model.

## Trusted HTML Content

`HTML`, `CSS`, `HTMLAttr`, `JS`, `JSStr`, `URL`, and `Srcset` are explicit
trusted-content string types corresponding to Go `html/template` content
types. Construct them only from content already validated for the named
context. They bypass specific escaping steps and are not general sanitizers.
The [trusted-content comparison](html.md#trusted-content-types) demonstrates the
effect of opting into `HTML` and explains why caller-controlled text must not be
wrapped in a trusted type.

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

Catch the most specific project exception that the application can handle.
Execution errors retain source and template names when supplied:

```python
from gotpl import TemplateExecutionError, render

try:
    render("{{.missing}}", {}, name="config.tpl", missing_key="error")
except TemplateExecutionError as error:
    assert error.source_name == "config.tpl"
    assert error.template_name == "config.tpl"
    assert error.line == 1
else:
    raise AssertionError("missing key did not fail")
```

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

See [Function Libraries](function-libraries.md) for profile selection,
capability warnings, runnable Sprig/Slim-Sprig/Sprout examples, and safe
composition with application functions.

## Python-Native Functions

`PythonExtensions(re_match=True)` enables `reMatch`, which uses Python
`re.search` semantics. It never replaces Sprig's RE2-compatible `regexMatch`
and is disabled by default. The [sandbox guide](sandbox.md#python-rematch)
contains the runnable example and its backtracking-risk boundary.

## Version

`gotpl.__version__` contains the installed distribution version. Applications
should use package metadata for dependency decisions and must not parse
development-version strings as feature flags.
