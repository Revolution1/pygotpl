# Go 1.27 Baseline Upgrade

## Decision

The compatibility, oracle, benchmark, generated-data, and CI baseline moves
from Go 1.26.5 to Go 1.27.0. Go 1.27.0 was released on August 19, 2026 and was
the latest stable Go release when this upgrade was audited on August 26, 2026.

The pinned upstream tags were also checked directly. Sprig v3.3.0,
Slim-Sprig v3.0.0, and Sprout v1.1.1 remain their latest repository tags. The
Python lockfile resolves without an available upgrade for any direct runtime,
optional, test, quality, or benchmark dependency.

## Reference Changes

- `scripts/sync_references.sh` now checks out `go1.27.0`.
- Repository oracle and benchmark modules use the Go 1.27 language level and
  were normalized with Go 1.27 `go mod tidy`; CI selects the exact 1.27.0
  toolchain.
- CI and historical-performance jobs install exactly Go 1.27.0.
- Local quality and generated-artifact gates reject any other Go version.
- All 104 Go conformance fixtures identify `go1.27.0` as their verified
  revision.
- The generated regexp tables now use Go 1.27's Unicode 17.0.0 data.

Go module transitive dependencies intentionally remain those selected by the
pinned Sprig and Slim-Sprig releases. Upgrading them independently would make
the oracle represent a dependency combination other than the upstream release.

## Upstream Template Audit

A directory comparison between the ignored Go 1.26.5 and Go 1.27.0 checkouts
found changes in seven `text/template` files and nine `html/template` files.
The observable changes relevant to pygotpl were:

- Go parse-tree `String` methods now preserve custom delimiters. pygotpl does
  not expose Go parse-tree stringification; existing custom-delimiter parse and
  render fixtures remain the applicable public contract.
- `html/template` updates JavaScript slash context after `{` and `}` to fix
  CVE-2026-56858. A new differential security fixture covers all five upstream
  cases, including attacker input and template-literal interpolation. The
  initial Python run failed by emitting quoted JavaScript values; the context
  analyzer was fixed and the fixture then matched Go 1.27.
- Go regexp Unicode-name lookup now ignores case, underscores, spaces, and
  hyphens for category aliases and scripts. The initial full gate exposed the
  changed `Old_Italic` result. pygotpl now performs the same canonical lookup,
  with direct tests for spelling variants and full generated-table differential
  coverage.
- Go's Unicode data moved from 15.0.0 to 17.0.0. The generated table grew from
  157,203 to 164,049 bytes and includes new scripts such as Beria Erfe, Todhri,
  and Tolong Siki.

Go 1.27 also backs `encoding/json` with its v2 implementation while preserving
v1 API behavior. Exact error text may change upstream. All checked-in Sprig
JSON success and failure fixtures pass the upgraded oracle without a pygotpl
change.

## Verification

The final local gate used CPython 3.14.7 and Go 1.27.0 on macOS 26.5.2 arm64:

- 1,345 tests passed;
- 7,496 executable statements had zero misses;
- 3,066 branches had one pre-existing partial lexer branch;
- branch-aware coverage rounded to 99%; and
- Ruff, Ruff format, strict Pyright, generated Unicode verification, `gofmt`,
  and the Go oracle module all passed.

The Unicode matrix differentially verifies every Go-addressable category and
script. The complete text, async, Sprig, Slim-Sprig, HTML security, parser,
property, and performance-correctness suites ran without skips introduced for
the upgrade.

## Performance Baseline Effect

Seven-sample medians were regenerated on the same machine and interpreter. Go
1.27 reduced the Go median for every shared workload. Selected changes from the
former Go 1.26.5 baseline are:

| Workload | Go 1.26.5 ns/op | Go 1.27.0 ns/op | Change |
| --- | ---: | ---: | ---: |
| Parser | 3,706 | 3,189 | -14.0% |
| Literal render | 36 | 29 | -19.4% |
| Text control render | 1,247 | 1,102 | -11.6% |
| Contextual HTML render | 14,396 | 13,239 | -8.0% |
| Sprig-heavy render | 9,468 | 9,048 | -4.4% |
| Cold parse, compile, and render | 3,008 | 2,567 | -14.7% |
| Large named-template set | 2,160 | 1,845 | -14.6% |

The larger Python/Go ratios in the current M6 report therefore primarily
reflect a faster comparison engine, not a pygotpl regression. The checked-in
benchmark commands verify identical output before timing.

## Sources

- [Go 1.27 release announcement](https://go.dev/blog/go1.27)
- [Go 1.27 release notes](https://go.dev/doc/go1.27)
- [Go release history](https://go.dev/doc/devel/release)
