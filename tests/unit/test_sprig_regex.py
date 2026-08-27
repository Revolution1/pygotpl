# pyright: reportPrivateUsage=false

import re
from collections.abc import Callable

import pytest

import gotpl
import gotpl.funcs.sprig as sprig
from gotpl._compat.goregexp import _unicode_properties
from gotpl._compat.goregexp._unicode_properties import UNICODE_VERSION
from gotpl.funcs.sprig.regex import _compile


def function(name: str) -> Callable[..., object]:
    return sprig.generic_func_map()[name]


def test_regex_backend_uses_an_ordered_nfa_for_ambiguous_repetition() -> None:
    _compile.cache_clear()
    compiled = _compile(r"^(a|aa)+$")

    assert compiled.backend == "ordered-nfa"
    assert _compile(r"^(a|aa)+$") is compiled
    assert _compile.cache_info().maxsize == 256
    assert compiled.search("a" * 4096 + "!") is None


def test_regex_backend_uses_the_audited_atomic_fast_path() -> None:
    compiled = _compile(r"[0-9]+")

    assert compiled.backend == "stdlib-atomic"
    assert [match.group() for match in compiled.finditer("v12-build34")] == [
        "12",
        "34",
    ]


def test_non_must_match_swallows_invalid_patterns() -> None:
    assert function("regexMatch")("[", "value") is False
    assert function("regexMatch")("(?=value)", "value") is False
    assert function("regexMatch")(r"(a)\1", "aa") is False


def test_must_regex_variants_return_explicit_errors() -> None:
    calls = {
        "mustRegexMatch": ("[", "value"),
        "mustRegexFind": ("[", "value"),
        "mustRegexFindAll": ("[", "value", -1),
        "mustRegexReplaceAll": ("[", "value", "replacement"),
        "mustRegexReplaceAllLiteral": ("[", "value", "replacement"),
        "mustRegexSplit": ("[", "value", -1),
    }
    for name, arguments in calls.items():
        result = function(name)(*arguments)
        assert isinstance(result, gotpl.FunctionResult)
        assert result.error is not None


@pytest.mark.parametrize(
    ("name", "arguments", "expected"),
    [
        ("mustRegexMatch", ("a", "a"), True),
        ("mustRegexFind", ("a", "banana"), "a"),
        ("mustRegexFindAll", ("a", "banana", 2), ["a", "a"]),
        ("mustRegexReplaceAll", ("a", "banana", "x"), "bxnxnx"),
        ("mustRegexReplaceAllLiteral", ("a", "banana", "$1"), "b$1n$1n$1"),
        ("mustRegexSplit", ("a", "banana", 2), ["b", "nana"]),
    ],
)
def test_must_regex_variants_return_successful_function_results(
    name: str, arguments: tuple[object, ...], expected: object
) -> None:
    result = function(name)(*arguments)
    assert isinstance(result, gotpl.FunctionResult)
    assert result.error is None
    assert result.value == expected


def test_must_regex_variants_preserve_empty_and_count_boundaries() -> None:
    calls = {
        "mustRegexMatch": (("", ""), True),
        "mustRegexFind": (("z", "banana"), ""),
        "mustRegexFindAll": (("z", "banana", -1), None),
        "mustRegexReplaceAll": (("", "x", "-"), "-x-"),
        "mustRegexReplaceAllLiteral": (("", "x", "$"), "$x$"),
        "mustRegexSplit": (("", "éx", -1), ["é", "x"]),
    }
    for name, (arguments, expected) in calls.items():
        result = function(name)(*arguments)
        assert isinstance(result, gotpl.FunctionResult)
        assert result.error is None
        assert result.value == expected


@pytest.mark.parametrize(
    ("name", "arguments"),
    [
        ("regexFind", ("[", "value")),
        ("regexFindAll", ("[", "value", -1)),
        ("regexReplaceAll", ("[", "value", "replacement")),
        ("regexReplaceAllLiteral", ("[", "value", "replacement")),
        ("regexSplit", ("[", "value", -1)),
    ],
)
def test_non_must_panicking_regex_variants_raise_compile_errors(
    name: str, arguments: tuple[object, ...]
) -> None:
    with pytest.raises(re.error):
        function(name)(*arguments)


def test_quote_meta_covers_empty_and_every_go_metacharacter() -> None:
    quote = function("regexQuoteMeta")

    assert quote("") == ""
    assert quote(r"\\.+*?()|[]{}^$") == r"\\\\\.\+\*\?\(\)\|\[\]\{\}\^\$"


def test_literal_replacement_preserves_dollars_and_empty_matches() -> None:
    replace = function("regexReplaceAllLiteral")

    assert replace("a", "banana", "$1") == "b$1n$1n$1"
    assert replace("", "x", "$") == "$x$"


def test_find_all_count_and_empty_results_match_go() -> None:
    assert function("regexFindAll")("a", "banana", 0) is None
    assert function("regexFindAll")("z", "banana", -1) is None
    assert function("regexFind")("z", "banana") == ""


def test_split_ignores_capture_groups_and_honors_counts() -> None:
    assert function("regexSplit")("(a)", "banana", -1) == ["b", "n", "n", ""]
    assert function("regexSplit")("a", "banana", 1) == ["banana"]
    assert function("regexSplit")("a", "banana", 0) == []


def test_replacement_expands_names_dollars_and_missing_groups() -> None:
    replace = function("regexReplaceAll")
    assert replace(r"(?P<word>[a-z]+)", "abc", "$word") == "abc"
    assert replace("a", "a", "$$") == "$"
    assert replace("a", "a", "$missing") == ""
    assert replace("a", "a", "$") == "$"
    assert replace("a", "a", "${missing") == "${missing"


def test_re2_ascii_classes_posix_classes_and_anchors() -> None:
    match = function("regexMatch")

    assert match(r"^\d+$", "\u0661") is False
    assert match(r"^\w+$", "é") is False
    assert match(r"^\s$", "\v") is False
    assert match(r"^\S$", "\v") is True
    assert match(r"^[[:alpha:]]+$", "abc") is True
    assert match(r"^[[:^digit:]]+$", "abc") is True
    assert match(r"x\z", "x") is True
    assert match(r"x$", "x\n") is False
    assert match(r"\Qa+b\E", "a+b") is True
    assert match(r"\Qunterminated", "unterminated") is False


def test_re2_ignores_empty_matches_adjacent_to_previous_matches() -> None:
    assert function("regexFindAll")("a*", "baaab", -1) == ["", "aaa", ""]
    assert function("regexSplit")("", "éx", -1) == ["é", "x"]
    assert function("regexReplaceAll")("a*", "baaab", "-") == "-b-b-"


def test_re2_named_groups_codepoint_escapes_and_unicode_folding() -> None:
    match = function("regexMatch")

    assert (
        function("regexReplaceAll")(r"(?<word>[a-z]+)", "abc-12", "<${word}>")
        == "<abc>-12"
    )
    assert match(r"\x{1F600}", "😀") is True
    assert match(r"\x{1001}", "\N{MYANMAR LETTER KHA}") is True
    assert match(r"(?i:é)", "É") is True
    assert match(r"\123", "S") is True
    assert match(r"\400", "Ā") is True
    assert match(r"\777", "ǿ") is True
    assert match(r"^\d+$", "\N{ARABIC-INDIC DIGIT ONE}") is False
    assert match(r"^[\D]+$", "\N{ARABIC-INDIC DIGIT ONE}") is True
    assert match(r"^[\W]+$", "é") is True
    assert match(r"^[^\W]+$", "A") is True
    assert match(r"^[\S]+$", "\v") is True
    assert match(r"^[^\S]+$", " ") is True
    assert match(r"\bé\b", "é") is False
    assert match(r"\bA\b", "A") is True


def test_re2_rejects_repeat_counts_above_one_thousand() -> None:
    for pattern in ("a{1001}", "a{1,1001}"):
        result = function("mustRegexMatch")(pattern, "a")
        assert isinstance(result, gotpl.FunctionResult)
        assert result.error is not None


def test_re2_rejects_malformed_braced_hexadecimal_escapes() -> None:
    for pattern in (r"\x{", r"\x{ZZ}", r"\x{110000}"):
        result = function("mustRegexMatch")(pattern, "value")
        assert isinstance(result, gotpl.FunctionResult)
        assert result.error is not None


def test_re2_ungreedy_and_mid_expression_flags_follow_go_scopes() -> None:
    find = function("regexFind")
    match = function("regexMatch")

    assert find("a.+b", "a1b2b") == "a1b2b"
    assert find("(?U)a.+b", "a1b2b") == "a1b"
    assert find("(?U)a.+?b", "a1b2b") == "a1b2b"
    assert find("a(?U).+b", "a1b2b") == "a1b"
    assert find("(?U:a.+b)c", "a1b2bc3bc") == "a1b2bc"
    assert match("a(?i)b", "aB") is True
    assert match("(?i:a(?-i:b)c)", "AbC") is True
    assert match("(?i:a(?-i:b)c)", "ABC") is False


def test_re2_scoped_multiline_flags_do_not_leak_to_absolute_end_anchors() -> None:
    match = function("regexMatch")

    assert match("(?m:^x$)", "x\ny") is True
    assert match("(?m:^x$)$", "x\n") is False
    assert match("(?m:^x$)(?-m:$)", "x\n") is False


def test_re2_mid_expression_flags_preserve_alternation_precedence() -> None:
    match = function("regexMatch")
    find = function("regexFind")

    assert match("a(?i)b|c", "C") is True
    assert match("a(?i)b|c", "aB") is True
    assert match("(?i:a(?-i)b|c)", "C") is False
    assert match("(?i:a(?-i)b|c)", "c") is True
    assert find("(?U)a.{1,3}b", "a1b2b") == "a1b"
    assert find("(?U)a.{1,3}?b", "a1b2b") == "a1b2b"


def test_re2_dotall_flag_combinations_and_invalid_flags() -> None:
    match = function("regexMatch")

    assert match("(?s:^a.b$)", "a\nb") is True
    assert match("(?is-m:^a.b$)", "A\nB") is True
    assert match("(?x)a", "a") is False
    result = function("mustRegexMatch")("(?x)a", "a")
    assert isinstance(result, gotpl.FunctionResult)
    assert result.error is not None


def test_re2_group_translation_covers_noncapturing_and_malformed_groups() -> None:
    match = function("regexMatch")

    assert match("(?:a|b)+", "aba") is True
    for pattern in (")", "(abc", "(?P<name"):
        result = function("mustRegexMatch")(pattern, "value")
        assert isinstance(result, gotpl.FunctionResult)
        assert result.error is not None


def test_re2_mid_flag_alternatives_preserve_escaped_and_nested_pipes() -> None:
    match = function("regexMatch")
    pattern = r"(?i)a\|b|[c|d]|(?:e|f)"

    assert match(pattern, "A|B") is True
    assert match(pattern, "C") is True
    assert match(pattern, "F") is True


def test_re2_unicode_properties_use_the_pinned_go_tables() -> None:
    match = function("regexMatch")

    assert UNICODE_VERSION == "17.0.0"
    assert match(r"^\pL+$", "é中") is True
    assert match(r"^\p{Greek}+$", "Ωβ") is True
    assert match(r"^\p{Cased_Letter}+$", "Ab") is True
    assert match(r"^\P{ASCII}+$", "é") is True
    assert match(r"^[\p{Greek}]+$", "Ω") is True
    assert match(r"^[^\p{Greek}]+$", "A") is True
    assert match(r"(?i:^\p{Lu}+$)", "abc") is True
    for name in ("Old_Italic", "old_italic", "OLD-ITALIC", "__old italic"):
        assert match(rf"\p{{{name}}}", "𐌀") is True
    assert match(r"\p{SignWriting}", "\U0001d800") is True


def test_unicode_property_caches_are_bounded() -> None:
    assert _unicode_properties.property_class_contents.cache_info().maxsize == 256
    assert _unicode_properties._property_intervals.cache_info().maxsize == 256
    assert _unicode_properties._table_intervals.cache_info().maxsize == 256


def test_re2_unicode_property_complements_and_errors() -> None:
    match = function("regexMatch")

    assert match(r"\p{Any}", "\n") is True
    assert match(r"\P{Any}", "x") is False
    assert match(r"[\P{Any}]", "x") is False
    assert match(r"[^\P{Any}]", "x") is True
    assert match(r"\p{Assigned}", "\u0378") is False
    assert match(r"\P{Assigned}", "\u0378") is True
    empty_class = function("mustRegexMatch")(r"\P{Any}", "x")
    assert isinstance(empty_class, gotpl.FunctionResult)
    assert empty_class.error is None
    assert empty_class.value is False
    assert match(r"\p{^Greek}", "A") is True
    assert match(r"\P{^Greek}", "Ω") is True
    for pattern in (r"\p", r"\p{}", r"\p{Greek", r"\p{Unknown}"):
        result = function("mustRegexMatch")(pattern, "value")
        assert isinstance(result, gotpl.FunctionResult)
        assert result.error is not None
    assert _unicode_properties._merge([]) == ()
