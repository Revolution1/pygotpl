# Helm Runtime Example

Run the checked-in chart from the repository root:

```console
uv run --frozen --extra helm python -m examples.helm_cli \
  template demo tests/fixtures/helm/basic \
  --namespace testing \
  --set name=Python
```

See [Build a Helm Renderer with gotpl](../../docs/building-helm.md) for the CLI
options, complex-chart workflow, architecture, and direct library examples.
