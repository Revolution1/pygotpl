from __future__ import annotations

import random
from io import StringIO

import gotpl
import gotpl.funcs.sprig as sprig

from .support import ExpectedResult, TemplateRequest, run_go_oracle_many

_CASES = (
    ("", "éx"),
    ("a", "banana"),
    ("a|aa", "aa"),
    ("aa|a", "aa"),
    ("a*", "baaab"),
    ("a*?", "baaab"),
    ("a+", "baaab"),
    ("a+?", "baaab"),
    ("a?", "baaab"),
    ("a??", "baaab"),
    ("a{0}", "baaab"),
    ("a{2}", "aaaaa"),
    ("a{1,3}", "aaaaa"),
    ("a{1,3}?", "aaaaa"),
    ("(a|aa)+", "aaaa"),
    ("(aa|a)+", "aaaa"),
    ("(a+)+$", "aaaa!"),
    ("(a*)*", "aa"),
    ("(|a)*", "aa"),
    ("(ab)?c", "abc-c"),
    ("(?P<word>[a-z]+)", "abc-12"),
    ("^a", "ba\na"),
    ("(?m)^a", "ba\na"),
    ("a$", "a\n"),
    ("(?m)a$", "a\nx"),
    (r"a\z", "ba"),
    (r"\Astart", "xstart-start"),
    (r"\bA\b", " A "),
    (r"\BA\B", "xAx"),
    (".", "\né"),
    ("(?s).", "\né"),
    ("[a-c]+", "zabcx"),
    ("[^a-c]+", "abXYZcd"),
    (r"\d+", "\N{ARABIC-INDIC DIGIT ONE}23"),
    (r"\D+", "\N{ARABIC-INDIC DIGIT ONE}23"),
    (r"\p{Greek}+", "AΩβZ"),
    (r"\P{ASCII}+", "aé中b"),
    ("(?i:k)+", "Kk\N{KELVIN SIGN}"),
    ("(?i:é)+", "Éé"),
    ("(?U)a.+b", "a1b2b"),
    ("a.*b|a.*c", "a1c2b"),
)
_CAPTURE_CASES = (
    ("(a|aa)(a?)", "aaa"),
    ("(a(b)?)+", "aba"),
    ("(?P<word>a+)(b*)", "aaabb"),
    ("(a*)*", "aa"),
    ("(a|b)+", "abba"),
    ("(a)?(b)?", "b"),
    ("(a|(b))+", "abb"),
)
_SEEDED_PATTERNS = (
    "a|b",
    "a|ab",
    "ab|a",
    "(?:a|b)*",
    "(?:a|ab)+",
    "(?:ab|a)+?",
    "a*b+",
    "a*?b+?",
    "a{0,3}b{1,2}",
    "(?:ab)?a",
    "(?:a*)*",
    "(?:|a)*",
    "[ab]+[^b]?",
    r"\d+\s?",
    r"\b(?:a|b)+\b",
    "^a.*b$",
    "(?m)^a.*b$",
    "(?s:a.*b)",
    "(?i:a+k)",
    "(a|b)(a*)",
)
_RANDOM = random.Random(0x5E2)
_SEEDED_CASES = tuple(
    (
        _RANDOM.choice(_SEEDED_PATTERNS),
        "".join(_RANDOM.choice("ab1 \n") for _ in range(_RANDOM.randrange(9))),
    )
    for _ in range(128)
)


def test_ordered_nfa_match_matrix_matches_go() -> None:
    requests = [
        TemplateRequest(
            engine="text",
            name=f"regex-matrix-{index}",
            template=(
                "{{regexMatch .Pattern .Value}}|"
                '{{regexFind .Pattern .Value | printf "%q"}}'
                "|{{regexFindAll .Pattern .Value -1 | toJson}}"
                '|{{regexReplaceAll .Pattern .Value "<$0>"}}'
            ),
            data={"Pattern": pattern, "Value": value},
            function_profile="sprig-hermetic",
        )
        for index, (pattern, value) in enumerate(_CASES + _SEEDED_CASES)
    ]
    expected = run_go_oracle_many(requests)
    functions = sprig.hermetic_text_func_map()
    actual: list[ExpectedResult] = []

    for request in requests:
        output = StringIO()
        gotpl.render_to(
            request["template"],
            output,
            data=request["data"],
            name=request["name"],
            functions=functions,
        )
        actual.append({"output": output.getvalue(), "error": None})

    assert actual == expected


def test_ordered_nfa_capture_priority_matches_go() -> None:
    requests = [
        TemplateRequest(
            engine="text",
            name=f"regex-captures-{index}",
            template='{{regexReplaceAll .Pattern .Value "[$0][$1][$2][${word}]"}}',
            data={"Pattern": pattern, "Value": value},
            function_profile="sprig-hermetic",
        )
        for index, (pattern, value) in enumerate(_CAPTURE_CASES)
    ]
    expected = run_go_oracle_many(requests)
    functions = sprig.hermetic_text_func_map()
    actual: list[ExpectedResult] = []

    for request in requests:
        output = StringIO()
        gotpl.render_to(
            request["template"],
            output,
            data=request["data"],
            name=request["name"],
            functions=functions,
        )
        actual.append({"output": output.getvalue(), "error": None})

    assert actual == expected
