# Sandboxing and Python Extensions

## Three Separate Safety Boundaries

`HTMLTemplate` provides contextual output safety. It analyzes HTML, URL, CSS,
and JavaScript contexts and applies Go-compatible escaping. It does not stop a
template from calling a registered function or reading an allowed Python
object.

`SandboxPolicy` provides an opt-in in-process capability boundary. Its strict
preset limits Python lookup to mapping data by default, removes the
data-callable `call` built-in, requires explicit grants for attributes,
properties, methods, and registered functions, bounds source length, and
supplies conservative per-render execution defaults.

Neither mechanism is an operating-system isolation boundary. A Python process
cannot reliably interrupt every long-running callback, regex match, serializer,
or native dependency, and its memory allocator cannot enforce a hard per-render
heap limit. Multi-tenant or hostile workloads must render in a worker process
or container with operating-system CPU, wall-time, memory, file, network, and
process limits. Terminate and replace that worker when a deadline expires.

## Strict Policy

The strict preset is immutable and mapping-only unless the embedding
application grants additional capabilities:

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

Mapping keys do not require an attribute grant. The allowlists below apply when
the application deliberately passes Python objects instead of mapping-only
data.

## Grant Python object access deliberately

Plain attributes, descriptor-backed properties, and bound methods are separate
capabilities:

```python
from gotpl import SandboxPolicy, Template


class Record:
    def __init__(self, name: str) -> None:
        self.name = name

    @property
    def label(self) -> str:
        return f"user:{self.name}"

    def greet(self) -> str:
        return f"hello:{self.name}"


policy = SandboxPolicy.strict(
    allow_attributes={"name"},
    allow_properties={"label"},
    allow_methods={"greet"},
)
template = Template("{{.name}}/{{.label}}/{{.greet}}", sandbox=policy)

assert template.render(Record("Ada")) == "Ada/user:Ada/hello:Ada"
```

Attributes, descriptor-backed properties, and methods have separate
allowlists. Granting an attribute does not execute a property or method with
the same name. Custom `__gotemplate_lookup__` adapters are disabled unless
`allow_custom_lookup=True` is explicit.

Complete Sprig, Slim-Sprig, Sprout, and Helm maps are rejected by a strict
policy unless every registered name is explicitly granted. Start with a small
function map. In particular, mutation, environment, network, random,
cryptographic, serializer, and resource-amplifying functions should remain
absent from untrusted profiles.

## Execution budgets

The default strict budget is one million output characters, 100,000 range
items, 100 active template calls, and 10,000 function or method calls. An
explicit `budget=` replaces that preset for the template. Counters are created
fresh for every sync or async render and shared across associated template
calls. Output is charged before each writer mutation, so a chunk that would
exceed the limit is not written.

```python
from io import StringIO

from gotpl import BudgetExceededError, ExecutionBudget, Template

writer = StringIO()
template = Template("ab{{.}}", budget=ExecutionBudget(max_output_chars=3))

try:
    template.render_to(writer, "cd")
except BudgetExceededError as error:
    assert "output character" in str(error)
else:
    raise AssertionError("output budget was not enforced")

assert writer.getvalue() == "ab"
```

The literal prefix fits and is written. The dynamic chunk would exceed the
limit, so the writer never receives that chunk.

Budgets limit VM-visible work, not callback-internal work. For example, one
function call can still perform expensive cryptography or construct a very
large collection. Use capability denial and operating-system isolation for
those cases.

## Python `reMatch`

Python-native helpers are selected through immutable construction options:

```python
from gotpl import PythonExtensions, Template

template = Template(
    r"{{reMatch `(?<=release-)\d+` .}}",
    extensions=PythonExtensions(re_match=True),
)

assert template.render("release-42") == "true"
```

`reMatch(pattern, value)` uses `re.search`, including Python lookaround and
backtracking semantics. It is distinct from Sprig `regexMatch`, which follows
Go RE2 syntax and matching behavior. Compiled Python patterns use a bounded
256-entry least-recently-used cache.

Python `re` may take exponential time for adversarial patterns and inputs.
There is no safe in-process step counter for the standard-library matcher.
Do not grant `reMatch` to untrusted pattern authors; if compatibility requires
it, apply small application-level input limits and execute in a deadline-bound
worker process.

`reMatch` is absent by default and never enters Go, Sprig, Slim-Sprig, Sprout,
or Helm registries. A strict sandbox also rejects it unless `reMatch` appears in
`allow_functions`.

## Configuration and Reuse

Policy, budget, and extension selection are constructor inputs stored on the
immutable `Template`. `Template.from_sources`, `with_source`, `TemplateEngine`,
and HTML templates retain the same configuration. Template source cannot alter
parsing, extensions, budgets, or sandbox grants.

The configuration is therefore part of the reusable template object's
identity. Applications that cache compiled templates must include source,
delimiters, functions, missing-key mode, format mode, sandbox policy, budget,
and extension configuration in their cache key.
