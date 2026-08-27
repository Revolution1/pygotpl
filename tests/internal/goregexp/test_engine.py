# pyright: reportPrivateUsage=false

import re

import pytest

from gotpl._compat.goregexp import _engine as engine
from gotpl._compat.goregexp import _parser
from gotpl._compat.goregexp._engine import LinearPattern


def test_linear_match_exposes_numbered_named_and_unmatched_captures() -> None:
    match = LinearPattern(r"(?P<letter>a)?b").search("b")

    assert match is not None
    assert match.start() == 0
    assert match.end() == 1
    assert match.group() == "b"
    assert match.group(1) is None
    assert match.group("letter") is None


def test_linear_pattern_supports_parser_atom_and_category_forms() -> None:
    assert LinearPattern(r"[^x]").search("y") is not None
    assert LinearPattern(r"\d\D\s\S\w\W").search("1x xx-") is not None
    assert LinearPattern(r"(?a:\d\D\s\S\w\W)").search("1x xx-") is not None
    assert LinearPattern(r"\Astart").search("start") is not None
    assert LinearPattern(r"\Astart").search("xstart") is None


def test_nullable_lazy_repetition_retains_re2_priority() -> None:
    match = LinearPattern(r"(?:|a)*?").search("aa")

    assert match is not None
    assert match.group() == ""


def test_engine_rejects_operations_outside_translated_subset() -> None:
    with pytest.raises(re.error, match="unsupported Perl syntax"):
        LinearPattern(r"(?=x)")


def test_ordered_candidate_survives_higher_priority_unfinished_thread() -> None:
    match = LinearPattern(r"a+|a").search("a")

    assert match is not None
    assert match.group() == "a"
    assert LinearPattern("a").search("", 1) is None


def test_engine_internal_guards() -> None:
    instructions: list[engine._Instruction] = []
    compiler = engine._Compiler(instructions)
    category = compiler.compile_operation(_parser.CATEGORY, _parser.CATEGORY_DIGIT, 0)
    empty_branch = compiler._branch([], 0)
    empty_assertion = compiler.compile_operation(
        _parser.ASSERT_NOT, (1, _parser.parse("", 0)), 0
    )

    assert category.start == 0
    assert empty_branch.start == 1
    assert instructions[empty_assertion.start].operation == "fail"
    assert engine._matches_rune(("category", _parser.CATEGORY_DIGIT, 0), "1")
    assert ord("k") in engine._case_variants(
        "K", _parser.SRE_FLAG_IGNORECASE | _parser.SRE_FLAG_ASCII
    )
    assert engine._case_variants("ẞ", _parser.SRE_FLAG_IGNORECASE) == {
        ord("ß"),
        ord("ẞ"),
    }
    assert engine._matches_assertion((_parser.AT_BEGINNING_LINE, 0), "x\ny", 2)

    with pytest.raises(re.error, match="character class operation"):
        engine._matches_class(((object(), None),), {ord("x")}, "x", 0)
    with pytest.raises(re.error, match="unsupported translated category"):
        engine._matches_category(object(), "x", 0)
    with pytest.raises(re.error, match="unsupported translated assertion"):
        engine._matches_assertion((object(), 0), "x", 0)


def test_nullable_analysis_covers_nested_nonnullable_shapes() -> None:
    assert not engine._nullable(_parser.parse("(a)", 0))
    assert not engine._nullable(_parser.parse("(a+|b+)", 0))
    assert not engine._nullable(_parser.parse("a+", 0))
    assert not engine._nullable(_parser.parse("^a", 0))
    assert not engine._nullable(((object(), None),))
