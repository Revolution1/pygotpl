import json
import re
from io import StringIO
from pathlib import Path
from typing import cast

import pytest

import gotpl
import gotpl.funcs.slim_sprig as slim_sprig

from .support import (
    FIXTURE_ROOT,
    PROJECT_ROOT,
    TemplateRequest,
    load_fixture,
    run_go_oracle_many,
)

SPRIG_INVENTORY = PROJECT_ROOT / "docs" / "reports" / "sprig-v3.3.0-functions.json"
SLIM_INVENTORY = PROJECT_ROOT / "docs" / "reports" / "slim-sprig-v3.0.0-functions.json"


def _inventory_names(path: Path) -> set[str]:
    raw = cast(dict[str, object], json.loads(path.read_text(encoding="utf-8")))
    return set(cast(list[str], raw["function_names"]))


SLIM_EXCLUDED_NAMES = _inventory_names(SPRIG_INVENTORY) - _inventory_names(
    SLIM_INVENTORY
)


def _uses_only_slim_functions(path: Path) -> bool:
    template = load_fixture(path).request["template"]
    return all(
        re.search(rf"(?<![A-Za-z0-9_]){re.escape(name)}(?![A-Za-z0-9_])", template)
        is None
        for name in SLIM_EXCLUDED_NAMES
    )


SHARED_FIXTURES = [
    path
    for path in sorted((FIXTURE_ROOT / "sprig").glob("*.json"))
    if _uses_only_slim_functions(path)
]

MATRIX_TEMPLATES = [
    (
        '{{adler32sum "x"}}|{{b32enc "x"}}|{{b64enc "x"}}|'
        '{{sha1sum "x"}}|{{sha256sum "x"}}|'
        '{{clean "/a/../b"}}|{{dir "/a/b.txt"}}|{{ext "a.txt"}}|'
        '{{isAbs "/a"}}|{{join "," (list 1 2)}}|{{quote "a" 1}}|'
        '{{squote "a" 1}}|{{sortAlpha (list "b" "a") | join ""}}|'
        '{{$s := split "," "a,b"}}{{$s._1}}|'
        '{{$n := splitn "," 2 "a,b,c"}}{{$n._1}}|'
        '{{splitList "," "a,b" | join ""}}|{{substr 1 3 "abcd"}}|'
        '{{title "first try"}}|{{toString 7}}|'
        '{{toStrings (list 1 nil 2) | join ","}}|'
        '{{trimall "-" "--x--"}}|{{trunc 3 "abcdef"}}|'
        '{{osBase "/a/b.txt"}}|{{osClean "/a/../b"}}|'
        '{{osDir "/a/b.txt"}}|{{osExt "a.txt"}}|{{osIsAbs "/a"}}'
    ),
    (
        '{{append (list 1) 2 | join ""}}|{{mustAppend (list 1) 2 | join ""}}|'
        '{{prepend (list 2) 1 | join ""}}|'
        '{{mustPrepend (list 2) 1 | join ""}}|'
        "{{chunk 2 (list 1 2 3) | len}}|"
        "{{mustChunk 2 (list 1 2 3) | len}}|"
        '{{compact (list 0 1 "") | join ""}}|'
        '{{mustCompact (list 0 1 "") | join ""}}|'
        '{{concat (list 1) (list 2) | join ""}}|'
        "{{first (list 1 2)}}/{{last (list 1 2)}}|"
        '{{initial (list 1 2) | join ""}}/'
        '{{mustInitial (list 1 2) | join ""}}|'
        '{{rest (list 1 2) | join ""}}/{{mustRest (list 1 2) | join ""}}|'
        '{{reverse (list 1 2) | join ""}}/'
        '{{mustReverse (list 1 2) | join ""}}|'
        "{{has 1 (list 1 2)}}/{{mustHas 1 (list 1 2)}}|"
        '{{slice (list 1 2 3) 1 | join ""}}/'
        '{{mustSlice (list 1 2 3) 1 | join ""}}|'
        '{{uniq (list 1 1 2) | join ""}}/'
        '{{mustUniq (list 1 1 2) | join ""}}|'
        '{{without (list 1 2) 1 | join ""}}/'
        '{{mustWithout (list 1 2) 1 | join ""}}|'
        '{{tuple 1 2 | join ""}}|{{mustLast (list 1 2)}}|{{mustFirst (list 1 2)}}'
    ),
    (
        "{{ceil 1.1}}/{{floor 1.9}}|{{maxf 1.1 2.2}}/{{minf 1.1 2.2}}|"
        '{{keys (dict "b" 2 "a" 1) | sortAlpha | join ""}}|'
        '{{values (dict "b" 2 "a" 1) | sortAlpha | join ""}}'
    ),
    (
        '{{mustRegexFindAll "a" "banana" -1 | len}}|'
        '{{mustRegexReplaceAll "a" "banana" "x"}}|'
        '{{mustRegexReplaceAllLiteral "a" "banana" "$1"}}|'
        '{{mustRegexSplit "a" "banana" -1 | len}}'
    ),
    ('{{mustToPrettyJson (dict "a" (list 1))}}|{{mustToRawJson (dict "x" "<")}}'),
    (
        '{{$t := toDate "2006-01-02" "2025-01-01"}}'
        '{{date_modify "24h" $t | date "2006-01-02"}}|'
        '{{mustDateModify "24h" $t | date "2006-01-02"}}|'
        '{{must_date_modify "24h" $t | date "2006-01-02"}}|'
        '{{htmlDate $t}}|{{now | kindOf}}|{{ago now | regexMatch "^[0-9]+s$"}}'
    ),
    (
        '{{env "PYGOTPL_ORACLE_MISSING_ENV_9EBC"}}|'
        '{{expandenv "plain"}}|{{randInt 10 11}}|'
        '{{getHostByName "localhost" | regexMatch ".+"}}'
    ),
]


def test_shared_slim_sprig_fixtures_match_the_pinned_fork_oracle() -> None:
    fixtures = [load_fixture(path) for path in SHARED_FIXTURES]
    assert len(fixtures) >= 20
    requests: list[TemplateRequest] = []
    for fixture in fixtures:
        profile = fixture.request.get("function_profile")
        slim_profile = (
            "slim-sprig-hermetic" if profile == "sprig-hermetic" else "slim-sprig"
        )
        requests.append(
            cast(TemplateRequest, {**fixture.request, "function_profile": slim_profile})
        )

    expected_results = run_go_oracle_many(requests)
    for fixture, request, expected in zip(
        fixtures, requests, expected_results, strict=True
    ):
        functions = (
            slim_sprig.hermetic_text_func_map()
            if request.get("function_profile") == "slim-sprig-hermetic"
            else slim_sprig.text_func_map()
        )
        output = StringIO()
        if expected["error"] is None:
            gotpl.render_to(
                request["template"],
                output,
                request["data"],
                name=request["name"],
                functions=functions,
            )
            assert output.getvalue() == expected["output"], fixture.identifier
        else:
            with pytest.raises(gotpl.TemplateExecutionError):
                gotpl.render_to(
                    request["template"],
                    output,
                    request["data"],
                    name=request["name"],
                    functions=functions,
                )
            assert output.getvalue() == expected["output"], fixture.identifier
            assert expected["error"]["phase"] == "execute"


def test_every_slim_sprig_name_has_pinned_fork_differential_evidence() -> None:
    fixture_text = "\n".join(
        path.read_text(encoding="utf-8") for path in SHARED_FIXTURES
    )
    evidence = fixture_text + "\n" + "\n".join(MATRIX_TEMPLATES)
    names = _inventory_names(SLIM_INVENTORY)
    missing = {
        name
        for name in names
        if re.search(rf"(?<![A-Za-z0-9_]){re.escape(name)}(?![A-Za-z0-9_])", evidence)
        is None
    }
    assert missing == set()

    requests = [
        TemplateRequest(
            engine="text",
            name=f"slim-matrix-{index}",
            template=template,
            data=None,
            function_profile="slim-sprig",
        )
        for index, template in enumerate(MATRIX_TEMPLATES)
    ]
    expected_results = run_go_oracle_many(requests)
    functions = slim_sprig.text_func_map()
    for request, expected in zip(requests, expected_results, strict=True):
        assert expected["error"] is None, request["name"]
        assert (
            gotpl.render(
                request["template"],
                request["data"],
                name=request["name"],
                functions=functions,
            )
            == expected["output"]
        ), request["name"]
