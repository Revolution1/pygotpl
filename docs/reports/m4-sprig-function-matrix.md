# M4 Sprig Function Evidence Matrix

## Scope and Status Vocabulary

This matrix indexes every public name in Sprig v3.3.0 by its pygotpl
implementation family. `Registered` means the name is present in the exact
211-name generic map. `Explicit evidence` means at least one Python behavioral
test or Go-oracle fixture names that public entry point. It does not by itself
mean the complete upstream behavior matrix has been audited.

The executable evidence gate is
`test_every_sprig_name_has_explicit_behavioral_evidence`. It prevents a future
registry entry from being counted as covered only by the registry membership
test. Normal, boundary, failure, differential, security, and performance depth
remain tracked at the family level below and in `m4-sprig-progress.md`.

`m4-sprig-evidence.json` is the stricter acceptance ledger. Each function
records resolvable normal, boundary, and failure evidence, or an explicit
reason that an upstream-total operation has no failure result. CI validates
referenced fixture IDs and pytest nodes. The ledger covers all 211 names across
every family and has status `complete`; registry membership alone cannot
satisfy this acceptance gate.

| Family | Count | Registry | Explicit evidence | Public names |
| --- | ---: | --- | --- | --- |
| Crypto | 13 | Complete | Complete | `bcrypt`, `buildCustomCert`, `decryptAES`, `derivePassword`, `encryptAES`, `genCA`, `genCAWithKey`, `genPrivateKey`, `genSelfSignedCert`, `genSelfSignedCertWithKey`, `genSignedCert`, `genSignedCertWithKey`, `htpasswd` |
| Dates | 16 | Complete | Complete | `ago`, `date`, `dateInZone`, `dateModify`, `date_in_zone`, `date_modify`, `duration`, `durationRound`, `htmlDate`, `htmlDateInZone`, `mustDateModify`, `mustToDate`, `must_date_modify`, `now`, `toDate`, `unixEpoch` |
| Defaults and JSON | 14 | Complete | Complete | `all`, `any`, `coalesce`, `default`, `empty`, `fromJson`, `mustFromJson`, `mustToJson`, `mustToPrettyJson`, `mustToRawJson`, `ternary`, `toJson`, `toPrettyJson`, `toRawJson` |
| Dictionaries | 17 | Complete | Complete | `deepCopy`, `dict`, `dig`, `get`, `hasKey`, `keys`, `merge`, `mergeOverwrite`, `mustDeepCopy`, `mustMerge`, `mustMergeOverwrite`, `omit`, `pick`, `pluck`, `set`, `unset`, `values` |
| Environment | 2 | Complete | Complete | `env`, `expandenv` |
| Flow | 1 | Complete | Complete | `fail` |
| Lists | 31 | Complete | Complete | `append`, `chunk`, `compact`, `concat`, `first`, `has`, `initial`, `last`, `list`, `mustAppend`, `mustChunk`, `mustCompact`, `mustFirst`, `mustHas`, `mustInitial`, `mustLast`, `mustPrepend`, `mustPush`, `mustRest`, `mustReverse`, `mustSlice`, `mustUniq`, `mustWithout`, `prepend`, `push`, `rest`, `reverse`, `slice`, `tuple`, `uniq`, `without` |
| Network | 1 | Complete | Complete | `getHostByName` |
| Numeric | 27 | Complete | Complete | `add`, `add1`, `add1f`, `addf`, `atoi`, `biggest`, `ceil`, `div`, `divf`, `float64`, `floor`, `int`, `int64`, `max`, `maxf`, `min`, `minf`, `mod`, `mul`, `mulf`, `round`, `seq`, `sub`, `subf`, `toDecimal`, `until`, `untilStep` |
| Random | 8 | Complete | Complete | `randAlpha`, `randAlphaNum`, `randAscii`, `randBytes`, `randInt`, `randNumeric`, `shuffle`, `uuidv4` |
| Reflection | 6 | Complete | Complete | `deepEqual`, `kindIs`, `kindOf`, `typeIs`, `typeIsLike`, `typeOf` |
| Regular expressions | 13 | Complete | Complete | `mustRegexFind`, `mustRegexFindAll`, `mustRegexMatch`, `mustRegexReplaceAll`, `mustRegexReplaceAllLiteral`, `mustRegexSplit`, `regexFind`, `regexFindAll`, `regexMatch`, `regexQuoteMeta`, `regexReplaceAll`, `regexReplaceAllLiteral`, `regexSplit` |
| Semantic versions | 2 | Complete | Complete | `semver`, `semverCompare` |
| Strings, encoding, and paths | 58 | Complete | Complete | `abbrev`, `abbrevboth`, `adler32sum`, `b32dec`, `b32enc`, `b64dec`, `b64enc`, `base`, `camelcase`, `cat`, `clean`, `contains`, `dir`, `ext`, `hasPrefix`, `hasSuffix`, `hello`, `indent`, `initials`, `isAbs`, `join`, `kebabcase`, `lower`, `nindent`, `nospace`, `osBase`, `osClean`, `osDir`, `osExt`, `osIsAbs`, `plural`, `quote`, `repeat`, `replace`, `sha1sum`, `sha256sum`, `sha512sum`, `snakecase`, `sortAlpha`, `split`, `splitList`, `splitn`, `squote`, `substr`, `swapcase`, `title`, `toString`, `toStrings`, `trim`, `trimAll`, `trimPrefix`, `trimSuffix`, `trimall`, `trunc`, `untitle`, `upper`, `wrap`, `wrapWith` |
| URLs | 2 | Complete | Complete | `urlJoin`, `urlParse` |

Total: 211 registered names with 211 explicit evidence references.

Slim-Sprig has a separate executable matrix covering all 164 pinned v3.0.0
names against its own Go oracle. Shared names do not imply shared behavior: the
matrix currently installs a fork-specific numeric layer for Slim-Sprig's
decimal-only integer casts.

## Continuing Audit Depth

M4's function-level acceptance ledger is complete. Future compatibility work
continues as additive regression hardening rather than an unchecked function
inventory:

- add new differential vectors when upstream regressions or newly discovered
  boundary classes justify them;
- track dependency and Go-version changes against the pinned oracle;
- replace the ordered NFA's CPython-internal syntax parser before stabilizing a
  standalone `goregexp` API; this does not reopen the M4 linear execution gate.

The checked-in `sprig/function-heavy` fixture exercises dictionaries, lists,
strings, regex, hashing, semantic versions, arithmetic, and JSON through the
versioned Sprig profile in both engines. Slim-Sprig shared fixtures and the
complete 164-name matrix execute independently against the pinned fork.
