# M10 Reproducible Build Evidence

## Result

Two clean builds with `SOURCE_DATE_EPOCH=1704067200` produced byte-identical
wheel and source-distribution artifacts for `gotpl`, `goduration`, and
`gotime`. All six pairwise `cmp` checks passed. The version remains `0.0.0`;
final release artifacts must be rebuilt from the signed release commit and
publish their own checksums and provenance. Development checksums are not
checked into an artifact that would contain and therefore invalidate them.

Artifact inspection also confirmed the PEP 639 `Apache-2.0` expression and
canonical `LICENSE` file in every distribution. The `gotpl` artifacts
additionally contain `THIRD_PARTY_NOTICES.md` for the Go BSD and Sprig-family
MIT material.

## Automated Check

`scripts/check_reproducible_builds.sh` creates two temporary build roots,
builds all three workspace distributions twice with a fixed epoch, requires
exactly six visible artifacts in each result, and compares each pair byte for
byte. The package CI job runs the same check. Hidden uv output metadata is not a
release artifact and is ignored.

```console
SOURCE_DATE_EPOCH=1704067200 ./scripts/check_reproducible_builds.sh
```

## Remaining External Evidence

Artifact signing, GitHub provenance attestations, the signed release tag, and
PyPI trusted publishing require repository-owner configuration. They must be
verified on the Apache-2.0-licensed release commit. Local reproducibility does
not substitute for those identity and publication gates.
