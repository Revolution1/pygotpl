# pyright: reportPrivateUsage=false

from __future__ import annotations

import pytest

from gotpl._compat.goregexp import _unicode_properties
from gotpl._compat.goregexp._unicode_properties import (
    UNICODE_VERSION,
    property_class_contents,
)
from gotpl._compat.goregexp._unicode_tables import CATEGORY_ALIASES, PROPERTY_RANGES
from gotpl._compat.goregexp.go import compile


def matches(pattern: str, value: str) -> bool:
    return compile(pattern).matches(value)


def test_ascii_posix_classes_anchors_and_quotes() -> None:
    assert not matches(r"^\d+$", "\u0661")
    assert not matches(r"^\w+$", "é")
    assert not matches(r"^\s$", "\v")
    assert matches(r"^\S$", "\v")
    assert matches(r"^[[:alpha:]]+$", "abc")
    assert matches(r"^[[:^digit:]]+$", "abc")
    assert matches(r"x\z", "x")
    assert not matches(r"x$", "x\n")
    assert matches(r"\Qa+b\E", "a+b")
    with pytest.raises(ValueError):
        compile(r"\Qunterminated")


def test_empty_match_progression_matches_go() -> None:
    pattern = compile("a*")

    assert pattern.find_all("baaab") == ["", "aaa", ""]
    assert compile("").split("éx") == ["é", "x"]
    assert pattern.replace_all("baaab", "-") == "-b-b-"


def test_named_groups_codepoint_escapes_and_unicode_folding() -> None:
    assert compile(r"(?<word>[a-z]+)").replace_all("abc-12", "<${word}>") == "<abc>-12"
    assert matches(r"\x{1F600}", "😀")
    assert matches(r"\x{1001}", "\N{MYANMAR LETTER KHA}")
    assert matches(r"(?i:é)", "É")
    assert matches(r"\123", "S")
    assert matches(r"\400", "Ā")
    assert matches(r"\777", "ǿ")
    assert not matches(r"^\d+$", "\N{ARABIC-INDIC DIGIT ONE}")
    assert matches(r"^[\D]+$", "\N{ARABIC-INDIC DIGIT ONE}")
    assert matches(r"^[\W]+$", "é")
    assert matches(r"^[^\W]+$", "A")
    assert matches(r"^[\S]+$", "\v")
    assert matches(r"^[^\S]+$", " ")
    assert not matches(r"\bé\b", "é")
    assert matches(r"\bA\b", "A")


@pytest.mark.parametrize(
    "pattern",
    ["a{1001}", "a{1,1001}", r"\x{", r"\x{ZZ}", r"\x{110000}"],
)
def test_invalid_repetition_and_hexadecimal_escapes(pattern: str) -> None:
    with pytest.raises(ValueError):
        compile(pattern)


def test_ungreedy_and_mid_expression_flags_follow_go_scopes() -> None:
    assert compile("a.+b").find("a1b2b") == "a1b2b"
    assert compile("(?U)a.+b").find("a1b2b") == "a1b"
    assert compile("(?U)a.+?b").find("a1b2b") == "a1b2b"
    assert compile("a(?U).+b").find("a1b2b") == "a1b"
    assert compile("(?U:a.+b)c").find("a1b2bc3bc") == "a1b2bc"
    assert matches("a(?i)b", "aB")
    assert matches("(?i:a(?-i:b)c)", "AbC")
    assert not matches("(?i:a(?-i:b)c)", "ABC")


def test_flag_scopes_alternation_and_dotall() -> None:
    assert matches("(?m:^x$)", "x\ny")
    assert not matches("(?m:^x$)$", "x\n")
    assert not matches("(?m:^x$)(?-m:$)", "x\n")
    assert matches("a(?i)b|c", "C")
    assert matches("a(?i)b|c", "aB")
    assert not matches("(?i:a(?-i)b|c)", "C")
    assert matches("(?i:a(?-i)b|c)", "c")
    assert compile("(?U)a.{1,3}b").find("a1b2b") == "a1b"
    assert compile("(?U)a.{1,3}?b").find("a1b2b") == "a1b2b"
    assert matches("(?s:^a.b$)", "a\nb")
    assert matches("(?is-m:^a.b$)", "A\nB")
    with pytest.raises(ValueError):
        compile("(?x)a")


def test_groups_and_nested_alternatives() -> None:
    assert matches("(?:a|b)+", "aba")
    for pattern in (")", "(abc", "(?P<name"):
        with pytest.raises(ValueError):
            compile(pattern)
    pattern = r"(?i)a\|b|[c|d]|(?:e|f)"
    assert matches(pattern, "A|B")
    assert matches(pattern, "C")
    assert matches(pattern, "F")


def test_unicode_properties_use_pinned_go_tables() -> None:
    assert UNICODE_VERSION == "17.0.0"
    assert matches(r"^\pL+$", "é中")
    assert matches(r"^\p{Greek}+$", "Ωβ")
    assert matches(r"^\p{Cased_Letter}+$", "Ab")
    assert matches(r"^\P{ASCII}+$", "é")
    assert matches(r"^[\p{Greek}]+$", "Ω")
    assert matches(r"^[^\p{Greek}]+$", "A")
    assert matches(r"(?i:^\p{Lu}+$)", "abc")
    for name in ("Old_Italic", "old_italic", "OLD-ITALIC", "__old italic"):
        assert matches(rf"\p{{{name}}}", "𐌀")
    assert matches(r"\p{SignWriting}", "\U0001d800")


def test_unicode_complements_errors_and_bounded_caches() -> None:
    assert matches(r"\p{Any}", "\n")
    assert not matches(r"\P{Any}", "x")
    assert not matches(r"[\P{Any}]", "x")
    assert matches(r"[^\P{Any}]", "x")
    assert not matches(r"\p{Assigned}", "\u0378")
    assert matches(r"\P{Assigned}", "\u0378")
    assert matches(r"\p{^Greek}", "A")
    assert matches(r"\P{^Greek}", "Ω")
    for pattern in (r"\p", r"\p{}", r"\p{Greek", r"\p{Unknown}"):
        with pytest.raises(ValueError):
            compile(pattern)
    assert _unicode_properties._merge([]) == ()
    assert property_class_contents.cache_info().maxsize == 256
    assert _unicode_properties._property_intervals.cache_info().maxsize == 256
    assert _unicode_properties._table_intervals.cache_info().maxsize == 256


def test_every_generated_unicode_table_and_alias_is_well_formed() -> None:
    for alias, target in CATEGORY_ALIASES.items():
        assert property_class_contents(alias) == property_class_contents(target)
    for ranges in PROPERTY_RANGES.values():
        previous_upper = -1
        for lower, upper, stride in ranges:
            assert 0 <= lower <= upper <= 0x10FFFF
            assert stride >= 1
            assert lower > previous_upper
            previous_upper = upper


def test_compile_cache_is_bounded() -> None:
    from gotpl._compat.goregexp.go import _compile

    _compile.cache_clear()
    first = _compile("abc")
    assert _compile("abc") is first
    assert _compile.cache_info().maxsize == 256
