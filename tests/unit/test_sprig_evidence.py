from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import cast

PROJECT_ROOT = Path(__file__).parents[2]
INVENTORY_PATH = PROJECT_ROOT / "docs/reports/sprig-v3.3.0-functions.json"
EVIDENCE_PATH = PROJECT_ROOT / "docs/reports/m4-sprig-evidence.json"
DATE_FUNCTIONS = {
    "ago",
    "date",
    "dateInZone",
    "dateModify",
    "date_in_zone",
    "date_modify",
    "duration",
    "durationRound",
    "htmlDate",
    "htmlDateInZone",
    "mustDateModify",
    "mustToDate",
    "must_date_modify",
    "now",
    "toDate",
    "unixEpoch",
}
DEFAULTS_JSON_FUNCTIONS = {
    "all",
    "any",
    "coalesce",
    "default",
    "empty",
    "fromJson",
    "mustFromJson",
    "mustToJson",
    "mustToPrettyJson",
    "mustToRawJson",
    "ternary",
    "toJson",
    "toPrettyJson",
    "toRawJson",
}
REGEX_FUNCTIONS = {
    "mustRegexFind",
    "mustRegexFindAll",
    "mustRegexMatch",
    "mustRegexReplaceAll",
    "mustRegexReplaceAllLiteral",
    "mustRegexSplit",
    "regexFind",
    "regexFindAll",
    "regexMatch",
    "regexQuoteMeta",
    "regexReplaceAll",
    "regexReplaceAllLiteral",
    "regexSplit",
}
REFLECTION_FLOW_FUNCTIONS = {
    "deepEqual",
    "fail",
    "kindIs",
    "kindOf",
    "typeIs",
    "typeIsLike",
    "typeOf",
}
URL_FUNCTIONS = {"urlJoin", "urlParse"}
DICTIONARY_FUNCTIONS = {
    "deepCopy",
    "dict",
    "dig",
    "get",
    "hasKey",
    "keys",
    "merge",
    "mergeOverwrite",
    "mustDeepCopy",
    "mustMerge",
    "mustMergeOverwrite",
    "omit",
    "pick",
    "pluck",
    "set",
    "unset",
    "values",
}
EXTERNAL_FUNCTIONS = {"env", "expandenv", "getHostByName"}
LIST_FUNCTIONS = {
    "append",
    "chunk",
    "compact",
    "concat",
    "first",
    "has",
    "initial",
    "last",
    "list",
    "mustAppend",
    "mustChunk",
    "mustCompact",
    "mustFirst",
    "mustHas",
    "mustInitial",
    "mustLast",
    "mustPrepend",
    "mustPush",
    "mustRest",
    "mustReverse",
    "mustSlice",
    "mustUniq",
    "mustWithout",
    "prepend",
    "push",
    "rest",
    "reverse",
    "slice",
    "tuple",
    "uniq",
    "without",
}
NUMERIC_FUNCTIONS = {
    "add",
    "add1",
    "add1f",
    "addf",
    "atoi",
    "biggest",
    "ceil",
    "div",
    "divf",
    "float64",
    "floor",
    "int",
    "int64",
    "max",
    "maxf",
    "min",
    "minf",
    "mod",
    "mul",
    "mulf",
    "round",
    "seq",
    "sub",
    "subf",
    "toDecimal",
    "until",
    "untilStep",
}
SEMVER_FUNCTIONS = {"semver", "semverCompare"}
STRING_FUNCTIONS = {
    "abbrev",
    "abbrevboth",
    "adler32sum",
    "b32dec",
    "b32enc",
    "b64dec",
    "b64enc",
    "base",
    "camelcase",
    "cat",
    "clean",
    "contains",
    "dir",
    "ext",
    "hasPrefix",
    "hasSuffix",
    "hello",
    "indent",
    "initials",
    "isAbs",
    "join",
    "kebabcase",
    "lower",
    "nindent",
    "nospace",
    "osBase",
    "osClean",
    "osDir",
    "osExt",
    "osIsAbs",
    "plural",
    "quote",
    "repeat",
    "replace",
    "sha1sum",
    "sha256sum",
    "sha512sum",
    "snakecase",
    "sortAlpha",
    "split",
    "splitList",
    "splitn",
    "squote",
    "substr",
    "swapcase",
    "title",
    "toString",
    "toStrings",
    "trim",
    "trimAll",
    "trimPrefix",
    "trimSuffix",
    "trimall",
    "trunc",
    "untitle",
    "upper",
    "wrap",
    "wrapWith",
}
RANDOM_FUNCTIONS = {
    "randAlpha",
    "randAlphaNum",
    "randAscii",
    "randBytes",
    "randInt",
    "randNumeric",
    "shuffle",
    "uuidv4",
}
CRYPTO_FUNCTIONS = {
    "bcrypt",
    "buildCustomCert",
    "decryptAES",
    "derivePassword",
    "encryptAES",
    "genCA",
    "genCAWithKey",
    "genPrivateKey",
    "genSelfSignedCert",
    "genSelfSignedCertWithKey",
    "genSignedCert",
    "genSignedCertWithKey",
    "htpasswd",
}
COMPLETED_FUNCTIONS = (
    DATE_FUNCTIONS
    | DEFAULTS_JSON_FUNCTIONS
    | REGEX_FUNCTIONS
    | REFLECTION_FLOW_FUNCTIONS
    | URL_FUNCTIONS
    | DICTIONARY_FUNCTIONS
    | EXTERNAL_FUNCTIONS
    | LIST_FUNCTIONS
    | NUMERIC_FUNCTIONS
    | SEMVER_FUNCTIONS
    | STRING_FUNCTIONS
    | RANDOM_FUNCTIONS
    | CRYPTO_FUNCTIONS
)


def _load_object(path: Path) -> dict[str, object]:
    return cast(dict[str, object], json.loads(path.read_text(encoding="utf-8")))


def _validate_reference(reference: str) -> str:
    location, separator, identifier = reference.partition("#")
    if not separator:
        location, separator, identifier = reference.partition("::")
    assert separator, f"evidence reference lacks an identifier: {reference}"
    path = PROJECT_ROOT / location
    assert path.is_file(), f"evidence file does not exist: {reference}"
    source = path.read_text(encoding="utf-8")
    if path.suffix == ".json":
        assert _load_object(path)["id"] == identifier
        return source
    functions = {
        node.name
        for node in ast.parse(source).body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    assert identifier in functions, f"test node does not exist: {reference}"
    return source


def test_m4_evidence_manifest_is_versioned_and_inventory_backed() -> None:
    inventory = _load_object(INVENTORY_PATH)
    evidence = _load_object(EVIDENCE_PATH)
    functions = cast(dict[str, object], evidence["functions"])

    assert evidence["schema_version"] == 1
    assert evidence["status"] == "complete"
    assert cast(dict[str, str], evidence["reference"])["revision"] == "v3.3.0"
    assert set(functions) == COMPLETED_FUNCTIONS
    assert set(functions) <= set(cast(list[str], inventory["function_names"]))
    assert evidence["completed_function_count"] == len(functions)


def test_completed_m4_evidence_has_resolvable_category_references() -> None:
    evidence = _load_object(EVIDENCE_PATH)
    functions = cast(dict[str, dict[str, object]], evidence["functions"])

    for function_name, categories in functions.items():
        referenced_sources: list[str] = []
        assert set(categories) == {"normal", "boundary", "failure"}
        for category in ("normal", "boundary"):
            references = cast(list[str], categories[category])
            assert references
            for reference in references:
                referenced_sources.append(_validate_reference(reference))
        failure = categories["failure"]
        if isinstance(failure, list):
            assert failure
            for reference in cast(list[str], failure):
                referenced_sources.append(_validate_reference(reference))
        else:
            reason = cast(dict[str, str], failure).get("not_applicable", "")
            assert len(reason) >= 20
        assert any(function_name in source for source in referenced_sources)
