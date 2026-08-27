# Licensing and Upstream Attribution

## Scope

This policy applies to source code, tests, conformance fixtures, generated
artifacts, documentation, and other material distributed in gotpl. Local
checkouts under `.references/` are development inputs, remain ignored, and
retain their own upstream licenses.

The project owner selected Apache License 2.0 on August 27, 2026 and approved
this upstream-attribution policy. Original gotpl, goduration, and gotime work is
licensed under SPDX identifier `Apache-2.0`. Each independently published
distribution carries the complete canonical license text.

Copyright 2026 Revolution1.

Apache-2.0 governs original project work only. It does not replace the licenses
or attribution requirements of upstream material. The completed review is
recorded in [`reports/m0-license-review.md`](reports/m0-license-review.md).

## Behavioral Compatibility Work

Go, Sprig, Slim-Sprig, and Sprout implementations and tests may be used to
identify observable behavior, edge cases, and error semantics. Contributors
must express that behavior in pygotpl's own fixture schema or Python test
structure. Do not mechanically translate or copy upstream source or test
bodies.

Every reference-derived conformance fixture records:

- `project`, which selects the upstream license family;
- `revision`, which pins the reviewed upstream version;
- `source`, which identifies the source file, test, or behavior group;
- `behavior`, which states the independently reviewable compatibility claim;
- `derived: true`, which declares that upstream material informed the case.

The fixture metadata and this document form the attribution record. A fixture
with `derived: false` is independently authored and uses its upstream metadata
only as verification provenance.

If a case needs copyrightable upstream expression, data, comments, or a
substantial table rather than independently expressed behavior, preserve the
applicable copyright notice, add a specific entry to
`THIRD_PARTY_NOTICES.md`, and obtain review before committing it. Generated
artifacts follow the same rule and must document their generator and source.

## License Mapping

| Fixture `project` or material source | Upstream license | Distribution action |
| --- | --- | --- |
| `go` and Go standard-library material | BSD 3-Clause | Retain the Go notice in `THIRD_PARTY_NOTICES.md`. |
| `sprig` and Sprig material | MIT | Retain the Masterminds notice in `THIRD_PARTY_NOTICES.md`. |
| Slim-Sprig material | MIT | Retain the Masterminds notice in `THIRD_PARTY_NOTICES.md`. |
| Sprout material | MIT | Retain the notice shipped by the pinned Sprout revision in `THIRD_PARTY_NOTICES.md`. |

These permissive upstream licenses allow modification and redistribution when
their notice conditions are met. They do not determine the license for
original pygotpl work.

`THIRD_PARTY_NOTICES.md` reproduces the applicable Go BSD-3-Clause and
Sprig-family MIT notices. The main gotpl distribution includes that file as
license metadata. The independent goduration and gotime distributions contain
original implementations and independently authored oracle clients; they do
not redistribute Go standard-library source or tests.

## Review Checklist

Before accepting upstream-informed work:

1. Confirm the reference revision matches `docs/references.md`.
2. Confirm the test was developed red-green-refactor.
3. Confirm fixture provenance is complete and accurate.
4. Confirm the new expression is independently authored where practical.
5. Add a material-specific notice when copied or adapted expression is needed.
6. Run the complete applicable conformance and Python test suites.

Reference upgrades require a new review because upstream licenses and file
headers may change.

## Contribution License

Unless explicitly stated otherwise, a contribution intentionally submitted for
inclusion is licensed under Apache-2.0 under Section 5 of that license. A
contributor must have the right to submit the work and must identify any
third-party material that needs separate terms or attribution. No contributor
license agreement is currently required.
