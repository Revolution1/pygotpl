from __future__ import annotations

import pytest

from gotpl._compat.goregexp import Pattern, RegexpError, compile, quote_meta
from gotpl._compat.goregexp.go import (
    regex_find,
    regex_find_all,
    regex_match,
    regex_quote_meta,
    regex_replace_all,
    regex_replace_all_literal,
    regex_split,
)
from gotpl._compat.goregexp.types import Limits


def test_top_level_defaults_to_immutable_go_surface() -> None:
    pattern = compile(r"(?P<word>[a-z]+)")

    assert isinstance(pattern, Pattern)
    assert pattern.source == r"(?P<word>[a-z]+)"
    assert pattern.matches("12-abc")
    assert pattern.find("12-abc") == "abc"
    assert pattern.find("12") == ""
    assert pattern.find_all("a-12-b") == ["a", "b"]
    assert pattern.find_all("a", 0) is None
    assert pattern.find_all("12") is None
    with pytest.raises(AttributeError):
        pattern.source = "changed"  # type: ignore[misc]


def test_go_replacement_split_and_quote_semantics() -> None:
    pattern = compile(r"(?P<word>[a-z]+)")

    assert pattern.replace_all("abc-12", "<${word}>") == "<abc>-12"
    assert pattern.replace_all("abc", "$$") == "$"
    assert pattern.replace_all_literal("abc", "$word") == "$word"
    assert compile("(a)").split("banana") == ["b", "n", "n", ""]
    assert compile("a").split("banana", 1) == ["banana"]
    assert compile("a").split("banana", 0) == []
    assert quote_meta(r"a+b[0]") == r"a\+b\[0\]"


def test_go_surface_exposes_only_sprout_required_submatch_operations() -> None:
    pattern = compile(r"(?P<key>\w+)=(?P<value>\w+)(?:-(x))?")

    assert pattern.find_groups("a=1 b=2-x") == ["a=1", "a", "1", ""]
    assert pattern.find_all_groups("a=1 b=2-x") == [
        ["a=1", "a", "1", ""],
        ["b=2-x", "b", "2", "x"],
    ]
    assert pattern.find_all_groups("a=1 b=2", 1) == [["a=1", "a", "1", ""]]
    assert pattern.find_all_groups("a=1", 0) == []
    assert pattern.find_groups("none") == []
    assert pattern.find_named("a=1") == {"key": "a", "value": "1"}
    assert pattern.find_all_named("a=1 b=2") == [
        {"key": "a", "value": "1"},
        {"key": "b", "value": "2"},
    ]
    assert pattern.find_all_named("a=1 b=2", 1) == [{"key": "a", "value": "1"}]
    assert pattern.find_all_named("a=1", 0) == []
    assert pattern.find_named("none") == {}


def test_go_surface_rejects_python_only_syntax_and_enforces_limits() -> None:
    for source in (r"(?=a)", r"(a)\1", r"(?x)a"):
        with pytest.raises(RegexpError):
            compile(source)
    with pytest.raises(RegexpError, match="max_pattern_length"):
        compile("ab", limits=Limits(max_pattern_length=1))
    with pytest.raises(RegexpError, match="max_repeat_count"):
        compile("a{3}", limits=Limits(max_repeat_count=2))
    with pytest.raises(RegexpError, match="max_program_instructions"):
        compile("ab", limits=Limits(max_program_instructions=1))
    with pytest.raises(RegexpError, match="max_captures"):
        compile("(a)(b)", limits=Limits(max_captures=1))
    with pytest.raises(TypeError, match="pattern must be a string"):
        Pattern(1)  # type: ignore[arg-type]


def test_go_surface_uses_linear_backend_for_ambiguous_repetition() -> None:
    pattern = compile(r"^(a|aa)+$")

    assert pattern.backend == "ordered-nfa"
    assert not pattern.matches("a" * 4096 + "!")
    assert compile(r"[0-9]+").backend == "stdlib-atomic"


def test_function_surface_preserves_sprig_facing_contract() -> None:
    assert regex_match("[", "value") is False
    assert regex_find("a", "banana") == "a"
    assert regex_find_all("a", "banana", 2) == ["a", "a"]
    assert regex_replace_all("a", "banana", "x") == "bxnxnx"
    assert regex_replace_all_literal("a", "banana", "$1") == "b$1n$1n$1"
    assert regex_split("a", "banana", 2) == ["b", "nana"]
    assert regex_quote_meta("a+b") == r"a\+b"
