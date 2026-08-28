# M10 Complex Helm Chart Validation

## Result

The local-chart example renders three representative dependency-heavy charts
with the same Kubernetes object identity set as the local Helm v4.2.4 CLI:

| Chart | Version | Rendered manifests | Missing or extra identities |
| --- | ---: | ---: | ---: |
| Bitnami PostgreSQL | 18.8.13 | 7 | 0 |
| Grafana Loki | 7.3.0 | 30 | 0 |
| kube-prometheus-stack | 88.5.4 | 122 | 0 |

PostgreSQL differs only in its generated random password. The corresponding
Grafana Secret and Deployment checksum differ for the same reason in
kube-prometheus-stack. Loki differs only in the gateway Deployment checksum:
the underlying ConfigMap is semantically equal, but PyYAML and Go YAML serialize
the long nginx scalar differently before the chart hashes it. These differences
are nondeterministic or serialization-derived rather than missing objects.

The validation exposed and fixed dependency alias, condition, and tag handling;
bound Go-style methods used as function arguments; Helm YAML scalar typing and
formatting; template-nil certificate arguments; and packaged dependency chart
loading. It also confirmed repeated values-file layering, `--set`, manifest
splitting, NOTES suppression, and Kubernetes kind ordering in the CLI path.

## Performance Finding

The original profile showed that each Helm `tpl` call reparsed and relinked the
complete associated template namespace. kube-prometheus-stack made 96 calls
from only 19 distinct source strings; the two most frequent strings appeared 32
and 30 times. A bounded cache now reuses identical compiled dynamic sources
within one render and one immutable parent namespace. It is discarded after the
render, and nested dynamic namespaces remain isolated.

The following before/after medians use the same CPython 3.14 process and five or
more samples. Render time includes chart collection, function-map construction,
parse, compile, and execution, but excludes chart-directory loading and manifest
sorting.

| Chart | Before | After | Reduction |
| --- | ---: | ---: | ---: |
| PostgreSQL | 113.44 ms | 85.39 ms | 24.7% |
| Loki | 1,770.24 ms | 651.56 ms | 63.2% |
| kube-prometheus-stack | 4,087.67 ms | 1,368.73 ms | 66.5% |

The final seven-sample phased benchmark measured:

| Chart | Load | Cold render | Manifest preparation | End to end |
| --- | ---: | ---: | ---: | ---: |
| PostgreSQL | 27.06 ms | 85.39 ms | 0.19 ms | 113.39 ms |
| Loki | 79.31 ms | 651.56 ms | 0.84 ms | 729.25 ms |
| kube-prometheus-stack | 105.96 ms | 1,368.73 ms | 8.30 ms | 1,489.71 ms |

For context, separate seven-sample Helm CLI process medians were 31.83 ms,
54.85 ms, and 86.12 ms. Those numbers include Helm process startup and therefore
do not share the Python phase boundary; they show product-level latency, not a
direct microbenchmark ratio.

After the cache, profiling still attributes most dynamic-template time to 19
full association links. Incrementally linking `Template.with_source` is the
next promising optimization, but it changes a core immutable namespace path and
needs dedicated generic/linked, sync/async, redefinition, and error-location
evidence before adoption.

## Method and Reproduction

- Machine: Apple M5, arm64
- Operating system: macOS 26.5.2
- Python: CPython 3.14.7
- Complex-chart CLI comparison: Helm v4.2.4
- Pinned engine/function oracle: Helm v4.2.3
- Timing: seven sequential samples, median reported
- Loki values: `loki.useTestSchema=true` with explicit chunks, ruler, and admin
  bucket names

Charts were downloaded and unpacked locally with Helm. Dependencies were left
complete under each chart's `charts/` directory and were not committed.

```console
uv run --frozen --extra all python -m benchmarks.helm_chart \
  /path/to/postgresql --samples 7 --profile-iterations 1 --top 15

uv run --frozen --extra all python -m benchmarks.helm_chart \
  /path/to/loki -f /path/to/loki-values.yaml \
  --samples 7 --profile-iterations 1 --top 15

uv run --frozen --extra all python -m benchmarks.helm_chart \
  /path/to/kube-prometheus-stack \
  --samples 7 --profile-iterations 1 --top 15
```

The runner records raw samples, environment metadata, output counts and digest,
and the top cumulative profile entries. Generated JSON results remain local
build artifacts.
