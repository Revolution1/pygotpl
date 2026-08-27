from __future__ import annotations

from collections import Counter

from gotpl.funcs.sprout import Handler, registry
from gotpl.runtime import FunctionResult


def _functions():
    return Handler(registry("strings")).build()


def test_strings_registry_covers_the_pinned_inventory() -> None:
    functions = _functions()

    assert set(functions) == {
        "capitalize",
        "contains",
        "ellipsis",
        "ellipsisBoth",
        "escape",
        "hasPrefix",
        "hasSuffix",
        "indent",
        "initials",
        "join",
        "nindent",
        "nospace",
        "plural",
        "quote",
        "repeat",
        "replace",
        "seq",
        "shuffle",
        "split",
        "splitn",
        "squote",
        "substr",
        "swapCase",
        "toCamelCase",
        "toConstantCase",
        "toDotCase",
        "toKebabCase",
        "toLower",
        "toPascalCase",
        "toPathCase",
        "toSnakeCase",
        "toTitleCase",
        "toUpper",
        "trim",
        "trimAll",
        "trimPrefix",
        "trimSuffix",
        "trunc",
        "uncapitalize",
        "unescape",
        "untitle",
        "wrap",
        "wrapWith",
    }


def test_strings_registry_basic_operations() -> None:
    functions = _functions()

    assert functions["nospace"](" a\t b\n") == "ab"
    assert functions["trim"]("  foo  ") == "foo"
    assert functions["trimAll"]("-o", "-f--o-o-") == "f"
    assert functions["trimPrefix"]("-f", "-foo-") == "oo-"
    assert functions["trimSuffix"]("o-", "-foo-") == "-fo"
    assert functions["contains"]("oo", "foo") is True
    assert functions["hasPrefix"]("fo", "foo") is True
    assert functions["hasSuffix"]("oo", "foo") is True
    assert functions["toLower"]("FOO") == "foo"
    assert functions["toUpper"]("foo") == "FOO"
    assert functions["replace"]("o", "a", "foo") == "faa"
    assert functions["repeat"](3, "foo") == "foofoofoo"
    assert functions["join"]("-", ["a", None, 1, True]) == "a-1-true"
    assert functions["trunc"](-3, "foobar") == "bar"
    assert functions["ellipsis"](6, "foooooo") == "foo..."
    assert functions["ellipsisBoth"](4, 9, "foooboooooo") == "...boo..."
    assert functions["initials"](" Foo  bar") == "Fb"
    assert functions["plural"]("single", "many", 1) == "single"


def test_strings_registry_wrapping_quoting_and_cases() -> None:
    functions = _functions()

    assert functions["wrap"](10, "This is a long string") == "This is a\nlong\nstring"
    assert functions["wrapWith"](4, "|", "abcdefgh x") == "abcd|efgh|x"
    assert functions["quote"]("foo", None, "👍") == '"foo" "👍"'
    assert functions["squote"]("foo", None, "👍") == "'foo' '👍'"
    assert functions["toCamelCase"]("___complex__case_") == "complexCase"
    assert functions["toKebabCase"]("HTTPServer") == "http-server"
    assert functions["toPascalCase"]("foo-bar_baz") == "FooBarBaz"
    assert functions["toDotCase"]("foo-bar_baz") == "foo.bar.baz"
    assert functions["toPathCase"]("foo-bar_baz") == "foo/bar/baz"
    assert functions["toConstantCase"]("HTTP20xOK") == "HTTP_20X_OK"
    assert functions["toSnakeCase"]("Duration2m3s") == "duration_2m_3s"
    assert functions["toTitleCase"]("foo-bar_baz") == "Foo-Bar_baz"
    assert functions["untitle"]("Foo  Bar") == "foo  bar"
    assert functions["swapCase"]("Foo-Bar_baz") == "fOO-bAR_BAZ"
    assert functions["capitalize"]("👍 good") == "👍 Good"
    assert functions["uncapitalize"]("123Boo_bar") == "123boo_bar"


def test_strings_registry_split_substring_indent_sequence_and_escaping() -> None:
    functions = _functions()

    assert functions["split"]("$", "foo$bar$") == {
        "_0": "foo",
        "_1": "bar",
        "_2": "",
    }
    assert functions["splitn"]("$", 2, "foo$bar$baz") == {
        "_0": "foo",
        "_1": "bar$baz",
    }
    assert functions["substr"](-3, -1, "foobar") == "ba"
    assert functions["indent"](3, "foo\n bar") == "   foo\n    bar"
    assert functions["nindent"](3, "foo") == "\n   foo"
    assert functions["seq"]() == ""
    assert functions["seq"](5) == "1 2 3 4 5"
    assert functions["seq"](0, 3, 10) == "0 3 6 9"
    assert functions["escape"](".:", "a.b:c\\d") == "a\\.b\\:c\\\\d"

    success = functions["unescape"](".:", "a\\.b\\:c\\\\d")
    assert success == FunctionResult.success("a.b:c\\d")
    invalid = functions["unescape"](".", "a\\nb")
    assert isinstance(invalid, FunctionResult)
    assert str(invalid.error) == r'invalid escape sequence: \n in "a\\nb"'
    trailing = functions["unescape"](".", "abc\\")
    assert isinstance(trailing, FunctionResult)
    assert str(trailing.error) == (
        'invalid escape sequence: trailing backslash in "abc\\\\"'
    )


def test_shuffle_preserves_unicode_runes() -> None:
    functions = _functions()
    value = "foo 👍 bar"

    for _ in range(20):
        shuffled = functions["shuffle"](value)
        assert isinstance(shuffled, str)
        assert Counter(shuffled) == Counter(value)
