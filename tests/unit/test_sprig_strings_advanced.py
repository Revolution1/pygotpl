from collections.abc import Callable

import pytest

import gotpl.funcs.sprig as sprig
from gotpl.funcs.sprig import strings
from gotpl.runtime import INVALID, UNTYPED_NIL


def function(name: str) -> Callable[..., object]:
    return sprig.generic_func_map()[name]


def test_substring_negative_start_uses_the_prefix_boundary() -> None:
    assert function("substr")(-1, 3, "abcdef") == "abc"


def test_quote_helpers_skip_all_nil_adapters() -> None:
    assert function("quote")(None, UNTYPED_NIL, INVALID) == ""
    assert function("squote")(None, UNTYPED_NIL, INVALID) == ""
    assert function("cat")(None, UNTYPED_NIL, INVALID) == ""
    assert function("toStrings")([1, None, UNTYPED_NIL, INVALID, 2]) == ["1", "2"]
    assert function("toString")(None) == "<nil>"


def test_split_handles_zero_counts_and_empty_separators() -> None:
    assert function("splitn")(",", 0, "a,b") == {}
    assert function("splitList")("", "abc") == ["a", "b", "c"]
    assert function("splitn")("", 2, "abc") == {"_0": "a", "_1": "bc"}


def test_camelcase_preserves_connector_boundaries() -> None:
    assert function("camelcase")("") == ""
    assert function("camelcase")("word-case") == "WordCase"
    assert function("camelcase")("__word__") == "__Word__"


def test_abbreviation_covers_width_and_tail_boundaries() -> None:
    assert function("abbrev")(3, "unchanged") == "unchanged"
    assert function("abbrev")(20, "short") == "short"
    assert function("abbrevboth")(0, 3, "unchanged") == "unchanged"
    assert function("abbrevboth")(2, 7, "abcdefghijk") == "abcd..."
    assert function("abbrevboth")(20, 10, "abcdefghijklmnop") == "...jklmnop"
    assert function("abbrevboth")(8, 10, "abcdefghijklmnopqrstu") == "...ijkl..."


def test_wrap_handles_empty_values_and_nonpositive_widths() -> None:
    assert function("wrap")(5, "") == ""
    assert function("wrapWith")(0, "|", "ab") == "a|b"
    assert function("wrapWith")(5, "", "hello world") == "hello\nworld"


def test_go_simple_case_mapping_avoids_python_full_case_expansion() -> None:
    assert strings.upper("ßﬃıᾀᾇᾐᾗᾠᾧᾳῃῳ") == ("ßﬃIᾈᾏᾘᾟᾨᾯᾼῌῼ")
    assert strings.lower("İẞ") == "iß"
    assert strings.title("ßeta ᾀλφα foo—bar") == "ßeta ᾈλφα Foo—bar"


def test_legacy_goutils_byte_iteration_is_preserved() -> None:
    assert strings.initials("Élan 中文") == "Ãä"
    assert strings.nospace("a\u00a0b\u2007c") == "aÂbâ\x80\x87c"
    assert strings.nospace("a\x1cb\x85c") == "a\x1cbÂc"
    assert strings.initials("a\x1cb\x85c") == "ac"
    assert strings.trim("\x1c x \x1c") == "\x1c x \x1c"


def test_python_byte_slices_expand_for_to_strings_and_sort_alpha() -> None:
    assert function("toString")(b"BA") == "BA"
    assert function("toStrings")(b"BA") == ["66", "65"]
    assert function("join")("-", b"BA") == "66-65"
    assert function("sortAlpha")(b"BA") == ["65", "66"]
    assert function("sortAlpha")(UNTYPED_NIL) == ["<nil>"]


@pytest.mark.parametrize(
    ("name", "arguments"),
    [
        ("repeat", (-1, "x")),
        ("indent", (-1, "x")),
        ("nindent", (-1, "x")),
        ("substr", (3, 2, "abc")),
        ("substr", (4, -1, "abc")),
        ("substr", (-1, 4, "abc")),
    ],
)
def test_string_helpers_preserve_upstream_bounds_panics(
    name: str, arguments: tuple[object, ...]
) -> None:
    with pytest.raises((IndexError, ValueError)):
        function(name)(*arguments)


def test_cat_uses_go_trim_space_boundaries() -> None:
    assert function("cat")("\x1c", "value", "\x1c") == "\x1c value \x1c"


@pytest.mark.parametrize(
    ("name", "value", "expected"),
    [
        ("base", "", "."),
        ("base", "//", "/"),
        ("dir", "a//b/../c", "a"),
        ("dir", "//host/file", "/host"),
        ("clean", "//a///b/../c", "/a/c"),
        ("ext", ".profile", ".profile"),
        ("ext", "dir/name.", "."),
        ("osBase", "", "."),
        ("osDir", "a//b/../c", "a"),
        ("osClean", "//a///b/../c", "/a/c"),
        ("osExt", ".profile", ".profile"),
    ],
)
def test_path_helpers_follow_go_clean_and_extension_rules(
    name: str, value: str, expected: str
) -> None:
    assert function(name)(value) == expected
