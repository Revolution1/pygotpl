# Function Libraries

gotpl keeps every ecosystem registry explicit. Pass the returned mapping with
`functions=` when constructing a template.

## Sprig

```python
from gotpl import Template
from gotpl.funcs.sprig import text_func_map

template = Template('{{"hello world" | title}}', functions=text_func_map())
assert template.render() == "Hello World"
```

Available profiles are `generic_func_map()`, `text_func_map()`,
`html_func_map()`, `hermetic_text_func_map()`, and
`hermetic_html_func_map()`. Each call returns a fresh mapping.

Hermetic profiles exclude environment, DNS, time, randomness, and other
host-dependent functions. Complete profiles are compatibility tools, not
sandboxes. Review the [Sprig capability boundary](sprig-security.md) before
using caller-controlled templates.

## Slim-Sprig

`gotpl.funcs.slim_sprig` exposes the same five registry constructors with the
smaller function inventory of the pinned Slim-Sprig fork. It is a named profile,
not an alias for full Sprig.

## Sprout

Sprout functions are grouped into explicit registries:

```python
from gotpl import Template
from gotpl.funcs.sprout import Handler, registry

functions = Handler(registry("strings"), registry("numeric")).build()
template = Template("{{. | upper}}", functions=functions)
```

Use `group(name)` to inspect a group and `registry(name)` to select one. The
inventory is immutable and auditable. Registries with cryptographic or other
specialized capabilities may require an optional extra.

## Helm

`gotpl.funcs.helm.function_map()` supplies reusable Helm-compatible functions.
The surrounding application owns chart loading, `.Values`, `.Release`,
`.Chart`, capabilities, and the runtime-specific `include`, `tpl`, `required`,
and `fail` callables. See [Multi-file and Helm integration](helm.md).

## Python-native helpers

Python helpers are separately opt-in:

```python
from gotpl import PythonExtensions, Template

template = Template(
    r"{{reMatch `(?<=v)\d+` .}}",
    extensions=PythonExtensions(re_match=True),
)
assert template.render("v12") == "true"
```

`reMatch` uses Python `re.search` behavior. It never replaces Sprig's
RE2-compatible `regexMatch`.
