# M1 Parser and Compiler Baseline

## Status

This is the final M1 baseline. The parser, semantic analyzer, source-mapped AST,
and compact IR passed the milestone acceptance gates recorded in
`docs/reports/m1-conformance.md`.

## Environment

- Date: 2026-08-25
- Platform: Darwin 25.5.0, arm64
- Python: CPython 3.13.7
- Go: 1.26.5, darwin/arm64
- Fixture: `benchmarks/fixtures/parser.json`

## Command

```console
python -m benchmarks.parser_baseline
```

## Results

| Runtime and phase | ns/op | allocs/op | bytes/op |
| --- | ---: | ---: | ---: |
| Python parse | 84,755.43 | not measured | not measured |
| Python compile | 11,869.24 | not measured | not measured |
| Python parse and compile | 99,067.12 | not measured | not measured |
| Go parse | 3,765.00 | 89 | 5,432 |

For this run, Python parse-and-compile took 26.31 times the Go parse duration.
Go's `Template.Parse` includes the native parse-tree construction needed for
execution; Go does not expose a directly equivalent separate compilation phase.

These values are directional baselines from one local run. They are not release
thresholds and must not be compared across unlike machines as regressions.

## Quality Evidence

- 218 tests passed after semantic, property, and differential expansion.
- The parser/compiler statement-coverage gate reached 100%.
- Eighty-eight fixed and 109 generated parser cases matched the pinned Go oracle.
- Hypothesis exercised 300 arbitrary Unicode inputs and generated valid nesting
  depths from zero through forty.
