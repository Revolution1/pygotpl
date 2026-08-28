# Build a Helm Renderer with gotpl

`gotpl` supplies the template-language and runtime pieces needed to build a
Helm-style renderer in Python. This guide starts with the repository's runnable
`helm template` example, then builds the same execution boundary directly from
the installed library.

The important separation is:

```text
local chart directory
        |
        v
application-owned loader ---- Chart.yaml, values, files, dependencies
        |
        v
application-owned context --- .Values, .Release, .Chart, .Capabilities
        |
        v
gotpl.exts.helm -------------- include, tpl, required, fail, Helm function map
        |
        v
gotpl runtime ---------------- parse, compile, associate, render
        |
        v
application-owned output ----- YAML documents, ordering, files, diagnostics
```

`gotpl` deliberately does not download charts, contact a Kubernetes cluster, or
manage releases. Use Helm to fetch and prepare dependencies when necessary, then
give your application a complete local chart.

## Try the Example CLI

The CLI is run from a repository checkout because `examples` is not installed
in the wheel. Install the Helm serialization dependencies first:

```console
uv sync --frozen --extra helm
```

Show the available command and template options:

```console
uv run --frozen --extra helm python -m examples.helm_cli --help
uv run --frozen --extra helm python -m examples.helm_cli template --help
```

Render the checked-in example chart:

```console
uv run --frozen --extra helm python -m examples.helm_cli \
  template demo tests/fixtures/helm/basic \
  --namespace testing \
  --set name=Python
```

The command produces:

```yaml
---
# Source: basic/templates/configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: demo-basic
data:
  greeting: "hello Python"
  script: |-
    #!/bin/sh
    echo ready
```

The positional arguments follow Helm's familiar order:

```text
gotpl-helm template RELEASE CHART [options]
```

The example supports:

- repeated `-f/--values` files, merged from left to right;
- repeated `--set key=value` assignments, applied after values files;
- `--namespace` and `--kube-version`;
- `--strict` missing-key failures;
- unpacked and packaged dependencies already present under `charts/`;
- manifest splitting, NOTES suppression, and Kubernetes kind ordering.

For example, layer an additional values file and save the result:

```console
mkdir -p /tmp/gotpl-helm-demo
printf 'name: from-values-file\n' > /tmp/gotpl-helm-demo/values.yaml

uv run --frozen --extra helm python -m examples.helm_cli \
  template demo tests/fixtures/helm/basic \
  -f /tmp/gotpl-helm-demo/values.yaml \
  --set name=from-set \
  > /tmp/gotpl-helm-demo/rendered.yaml
```

`--set` wins in this example because it is applied after every values file.

## Try a Complete Third-party Chart

Use Helm for acquisition and dependency preparation, then use the Python
example only for local rendering. This PostgreSQL version is one of the complex
chart snapshots used by the repository's compatibility suite:

```console
mkdir -p .charts
helm pull oci://registry-1.docker.io/bitnamicharts/postgresql \
  --version 18.8.13 \
  --untar \
  --untardir .charts
helm dependency build .charts/postgresql

uv run --frozen --extra all python -m examples.helm_cli \
  template demo .charts/postgresql \
  --namespace testing \
  > /tmp/postgresql-gotpl.yaml
```

The `all` extra is useful for complex charts that select optional cryptographic
Sprig functions. A chart using only Helm YAML and TOML helpers can use the
smaller `helm` extra.

Generated passwords, certificates, timestamps, and checksums can make bytewise
comparison nondeterministic. For deterministic charts, compare object output
with Helm directly:

```console
helm template demo .charts/postgresql \
  --namespace testing \
  > /tmp/postgresql-helm.yaml

diff -u /tmp/postgresql-helm.yaml /tmp/postgresql-gotpl.yaml
```

## Use the Example Runtime from Python

The example separates directory loading from rendering, so an application can
reuse it without going through command-line output formatting:

```python
from examples.helm_runtime import Engine, Release, load_chart

chart = load_chart("tests/fixtures/helm/basic")
rendered = Engine().render(
    chart,
    {"name": "Python"},
    release=Release(name="demo", namespace="testing"),
)

manifest = rendered["basic/templates/configmap.yaml"]
assert "name: demo-basic" in manifest
assert 'greeting: "hello Python"' in manifest
```

The example implementation has three application-owned stages:

1. `examples.helm_runtime.loader` reads `Chart.yaml`, `values.yaml`, templates,
   ordinary files, unpacked dependencies, and packaged dependency archives.
2. `examples.helm_runtime.Engine` merges defaults and overrides, traverses the
   dependency tree, and creates Helm's root objects for every renderable source.
3. `examples.helm_cli` applies CLI overrides and turns rendered sources into an
   ordered manifest stream.

This code is intentionally an example rather than a stable chart-model API.
Copy or adapt those application-owned pieces when building a product-specific
renderer.

## Build Directly on the Installed Library

Applications that already own chart loading should use
`gotpl.exts.helm.HelmTemplateEngine`. Supply the complete source association and
the root context for each manifest:

```python
from gotpl.exts.helm import HelmTemplateEngine

sources = {
    "demo/templates/_helpers.tpl": (
        '{{define "demo.fullname"}}{{.Release.Name}}-{{.Chart.Name}}{{end}}'
    ),
    "demo/templates/configmap.yaml": """\
apiVersion: v1
kind: ConfigMap
metadata:
  name: {{include "demo.fullname" .}}
data:
  message: {{required "message is required" .Values.message | quote}}
  dynamic: {{tpl .Values.dynamic . | quote}}
""",
}

context = {
    "Values": {
        "message": "hello",
        "dynamic": "{{.Release.Namespace}}",
    },
    "Release": {"Name": "example", "Namespace": "testing"},
    "Chart": {"Name": "demo", "Version": "1.0.0"},
    "Capabilities": {},
    "Files": {},
    "Subcharts": {},
    "Template": {
        "Name": "demo/templates/configmap.yaml",
        "BasePath": "demo/templates",
    },
}

engine = HelmTemplateEngine.from_sources(sources)
manifest = engine.render_template("demo/templates/configmap.yaml", context)

assert "name: example-demo" in manifest
assert 'message: "hello"' in manifest
assert 'dynamic: "testing"' in manifest
```

Every helper and manifest must be in the same `sources` mapping so `define`,
`template`, and `include` share one immutable association. Do not render files
individually and attempt to copy definitions between them.

For multiple manifests, prepare a context per root and render them as one batch:

```python
rendered = engine.render(
    {
        "demo/templates/configmap.yaml": context,
        # "demo/templates/deployment.yaml": deployment_context,
    }
)
```

`HelmTemplateEngine` instances are reusable across threads and asyncio tasks.
Use `render_async()` or `render_template_async()` when custom functions may be
asynchronous.

## Compose Helm with Other gotpl Configuration

Use `HelmTemplateEngine` for the shortest Helm-specific path. Use an
`Environment` with `HelmExtension` when the renderer must also compose custom
functions, execution budgets, sandbox policy, Python helpers, or another
runtime extension. Both paths use the same parser, compiler, VM, render context,
and Helm behavior.

The [Helm library guide](helm.md#reusable-helm-execution) owns the two API
forms. [Reusable Templates and Environments](reusable-templates.md) explains
shared configuration, and [Runtime Extensions](extensions.md) explains the
extension and capability model.

## Add Cluster-backed `lookup`

`lookup` is empty by default because gotpl does not own a Kubernetes client.
Inject an application function only when cluster access is intentional:

```python
from gotpl.exts.helm import HelmExtension


def lookup(
    api_version: str,
    kind: str,
    namespace: str,
    name: str,
) -> object:
    # Adapt these arguments to an application-owned Kubernetes client.
    return {}


extension = HelmExtension(lookup=lookup)
```

The caller owns authentication, authorization, timeouts, retries, and the exact
shape returned by that adapter. Keep `lookup` unset for hermetic local renders.

## Scope and Known Gaps

The example is a local template renderer, not a replacement for all Helm
commands. It intentionally leaves these operations to Helm or the embedding
application:

- chart repository and OCI authentication;
- dependency resolution and downloading;
- values-schema validation;
- CRD installation policy;
- Kubernetes discovery and OpenAPI validation;
- install, upgrade, rollback, hooks, release storage, and cluster mutation.

The example retains dependency `import-values` metadata but does not apply the
imports. It also does not currently expose Helm's `--include-crds` or
schema-validation switches. See [Helm Functions and Runtime](helm.md) for the
full compatibility and security boundary.
