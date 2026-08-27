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

| Need | Profile |
| --- | --- |
| Ordinary text templates | `text_func_map()` |
| Contextually escaped HTML templates | `html_func_map()` |
| Upstream generic naming | `generic_func_map()` |
| Upstream hermetic text/HTML membership | `hermetic_text_func_map()` / `hermetic_html_func_map()` |

The generic, text, and HTML profiles currently contain the same 211 names; the
separate constructors preserve Sprig's API and make application intent clear.
The hermetic profiles remove Sprig's exact 17-name exclusion list, including
environment, DNS, current-time fallback, secure random strings, bytes, and UUID
v4. They still retain pseudo-random, cryptographic, mutation, and deliberately
failing functions, so “hermetic” does not mean deterministic, bounded, or safe
for untrusted templates. Review the complete
[Sprig capability boundary](sprig-security.md) before selecting a profile.

## Slim-Sprig

`gotpl.funcs.slim_sprig` exposes the same five registry constructors with the
smaller function inventory of the pinned Slim-Sprig fork. It is a named profile,
not an alias for full Sprig.

```python
from gotpl import Template
from gotpl.funcs.slim_sprig import text_func_map

template = Template('{{"hello" | upper}}', functions=text_func_map())
assert template.render() == "HELLO"
```

## Sprout

Sprout functions are grouped into explicit registries:

```python
from gotpl import Template
from gotpl.funcs.sprout import Handler, registry

functions = Handler(registry("strings"), registry("numeric")).build()
template = Template("{{. | toUpper}}", functions=functions)
assert template.render("hello") == "HELLO"
```

Use `registry(name)` to select one registry. `group(name)` returns a pinned,
ordered set of implemented registries that can be passed to a `Handler`:

```python
from gotpl.funcs.sprout import Handler, group

selected = group("hermetic")
functions = Handler(*selected.registries).build()

assert set(functions) == set(selected.function_names)
```

The built function mapping and inventory are immutable and auditable.
Registries with cryptographic or other specialized capabilities may require an
optional extra.

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

## Combine a registry with application functions

Sprig and Slim-Sprig constructors return a fresh mutable dictionary, so an
application can add its own functions without changing another template's
registry. Check collisions explicitly instead of silently replacing a
compatibility function:

```python
from gotpl import Template
from gotpl.funcs.sprig import hermetic_text_func_map


def surround(value: str) -> str:
    return f"[{value}]"


functions = hermetic_text_func_map()
if "surround" in functions:
    raise ValueError("function name collision: surround")
functions["surround"] = surround

template = Template('{{"hello" | upper | surround}}', functions=functions)
assert template.render() == "[HELLO]"
```

`Handler.build()` returns an immutable mapping instead. Copy it before adding
application functions, while applying the same collision policy.
