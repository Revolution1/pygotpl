from __future__ import annotations

import json
import random
from io import StringIO

import gotpl
import gotpl.funcs.sprig as sprig

from .support import ExpectedResult, TemplateRequest, run_go_oracle_many

_CASE_INPUTS = (
    "",
    "HTTPServer",
    "_camelCase",
    "NoHTTPS",
    "Wi_thF",
    "_AnotherTES_TCaseP",
    "ALL",
    "_HELLO_WORLD_",
    "HELLO____WORLD",
    "http2xx",
    "HTTP2XX",
    "HTTP20xOK",
    "Duration2m3s",
    "Bld4Floor3rd",
    " _-_ ",
    "a1b2c3d",
    "A//B%%2c",
    "  sentence case  ",
    " Mixed-hyphen case _and SENTENCE_case and UPPER-case",
    "FROM CamelCase to snake/kebab-case",
    "_complex__case_",
    "GOLANG_IS_GREAT",
    "a",
    "HTTP状态码404/502Error",
    "中文(字符)",
    "混合ABCWords与123数字456",
    "Abc\ufffdE\ufffdf\ufffdd\ufffd2\ufffd00z\ufffdZZ\ufffdZZ",
    "1a中",
    "a1b中",
    "1a-",
    "a1b-",
    "\ufffd",
)
_CASE_EXPRESSIONS = tuple(
    f"{name} {json.dumps(value)}"
    for value in _CASE_INPUTS
    for name in ("snakecase", "kebabcase", "camelcase")
)
_TEXT_EXPRESSIONS = (
    'wrap 5 "Hello World"',
    'wrap 5 "  Hello   World  "',
    'wrap 5 "HelloWorld"',
    'wrap 5 "Hello\\tWorld Again"',
    'wrap 0 "abc"',
    'wrapWith 5 "|" "Hello World"',
    'wrapWith 5 "|" "HelloWorld"',
    'wrapWith 0 "|" "abc"',
    'wrapWith 5 "" "Hello World"',
    'wrapWith 3 "|" "éééé"',
    'abbrev 4 "abcdef"',
    'abbrev 6 "abcdef"',
    'abbrev 5 "ééé"',
    'abbrevboth 5 10 "1234 5678 9123"',
    'abbrevboth 20 10 "abcdefghijklmnop"',
    'trunc 3 "éé"',
    'trunc -3 "éé"',
    'substr 0 3 "éé"',
    'splitList "" "é中" | toJson',
)
_ENCODING_EXPRESSIONS = tuple(
    f"{name} {json.dumps(value)}"
    for name, values in (
        (
            "b64dec",
            (
                "",
                "Y29mZmVl",
                "Y29m\nZmVl",
                "A",
                "AA",
                "AAA",
                "AAAA=",
                "====",
                "Zm=v",
                "Zm9v====",
                "AA=\n=",
                "AA=\n",
                "AA==\n!",
                "é",
            ),
        ),
        (
            "b32dec",
            (
                "",
                "MNXWIZLFMU======",
                "MNXW\nIZLFMU======",
                "A",
                "MY",
                "MY======",
                "MY=======",
                "========",
                "my======",
                "AAA=====",
                "AAAAAA==",
                "é",
            ),
        ),
    )
    for value in values
)
_RANDOM = random.Random(0x57A1)
_SEEDED_ENCODING_EXPRESSIONS = tuple(
    f"{name} {json.dumps(value)}"
    for name, alphabet in (
        ("b64dec", "ABab01+/=!?\n"),
        ("b32dec", "ABYZ27=ab!?\n"),
    )
    for value in (
        "".join(_RANDOM.choice(alphabet) for _ in range(_RANDOM.randrange(13)))
        for _ in range(128)
    )
)
_PATH_VALUES = (
    "",
    ".",
    "..",
    "/",
    "//",
    "///",
    "foo",
    "foo/",
    "foo//bar",
    "a//b/../c",
    "//host/file",
    "//a///b/../c",
    ".profile",
    "dir/.profile",
    "dir/name.",
    "dir/a.tar.gz",
    "a/../../b",
)
_PATH_EXPRESSIONS = tuple(
    f"{name} {json.dumps(value)}"
    for value in _PATH_VALUES
    for name in (
        "base",
        "dir",
        "clean",
        "ext",
        "isAbs",
        "osBase",
        "osDir",
        "osClean",
        "osExt",
        "osIsAbs",
    )
)
_BASIC_EXPRESSIONS = (
    'trim "\\t \\nvalue\\r \\t"',
    'trim "\\u001c value \\u001c"',
    'trimAll "éx" "xévalueéx"',
    'trimPrefix "" "value"',
    'trimSuffix "" "value"',
    'contains "" "value"',
    'hasPrefix "" "value"',
    'hasSuffix "" "value"',
    'repeat 0 "value"',
    'repeat 3 "é"',
    'replace "" "-" "ab"',
    'indent 2 "a\\nb\\n"',
    'nindent 0 ""',
    'plural "one" "many" -1',
    "toString 1000000.0",
    "toString (list 1 nil 2)",
    "toStrings (list 1 nil 2) | toJson",
    "toStrings nil | toJson",
    'join "-" 123',
    'sortAlpha (list "é" "z" "a") | toJson',
    "sortAlpha nil | toJson",
    'substr -1 0 "abc"',
    'substr -1 3 "abc"',
    'substr 1 99 "abc"',
    'substr 3 -1 "abc"',
    'trunc 0 "abc"',
    'trunc -3 "abc"',
    'trunc -4 "abc"',
    'quote "a\\nb" "é" 1 nil',
    'squote "a\\nb" "é" 1 nil',
    'cat "  a" "b  " nil',
    'split "," "a,,b," | toJson',
    'split "" "é中" | toJson',
    'splitn "," -1 "a,b,c" | toJson',
    'splitn "," 0 "a,b,c" | toJson',
    'splitn "," 1 "a,b,c" | toJson',
    'splitn "," 2 "a,b,c" | toJson',
    'splitList "," "a,,b," | toJson',
    'nospace "a\\tb\\nc"',
    'initials " First  Try "',
    'title "hello.foo_bar-baz"',
    'untitle "First\\tTry"',
    'swapcase "Θ~λa云Ξπ"',
    'sha1sum ""',
    'sha256sum "é"',
    'sha512sum "é"',
    'adler32sum "é"',
)


def _assert_expressions_match_go(expressions: tuple[str, ...], prefix: str) -> None:
    requests = [
        TemplateRequest(
            engine="text",
            name=f"{prefix}-{index}",
            template="{{" + expression + "}}",
            data=None,
            function_profile="sprig-hermetic",
        )
        for index, expression in enumerate(expressions)
    ]
    expected = run_go_oracle_many(requests)
    functions = sprig.hermetic_text_func_map()
    actual: list[ExpectedResult] = []

    for request in requests:
        output = StringIO()
        gotpl.render_to(
            request["template"],
            output,
            name=request["name"],
            functions=functions,
        )
        actual.append({"output": output.getvalue(), "error": None})

    assert actual == expected


def test_xstrings_case_conversion_matrix_matches_go() -> None:
    _assert_expressions_match_go(_CASE_EXPRESSIONS, "string-case-matrix")


def test_wrapping_abbreviation_and_byte_slicing_matrix_matches_go() -> None:
    _assert_expressions_match_go(_TEXT_EXPRESSIONS, "string-text-matrix")


def test_encoding_decoder_boundary_matrix_matches_go() -> None:
    _assert_expressions_match_go(
        _ENCODING_EXPRESSIONS + _SEEDED_ENCODING_EXPRESSIONS,
        "string-encoding-matrix",
    )


def test_slash_and_host_path_matrix_matches_go() -> None:
    _assert_expressions_match_go(_PATH_EXPRESSIONS, "string-path-matrix")


def test_basic_string_conversion_and_digest_matrix_matches_go() -> None:
    _assert_expressions_match_go(_BASIC_EXPRESSIONS, "string-basic-matrix")
