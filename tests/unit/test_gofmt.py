import math
from concurrent.futures import ThreadPoolExecutor

import pytest

from gotpl._compat.gofmt import _core as gofmt_core
from gotpl.runtime import INVALID, UNTYPED_NIL, GoFormatSpec, GoPointer
from gotpl.runtime.gofmt import sprintf


def test_sprintf_handles_plain_text_percent_missing_and_extra_values() -> None:
    assert sprintf("plain") == "plain"
    assert sprintf("plain", 1) == "plain%!(EXTRA int=1)"
    assert sprintf("%%/%s", "value") == "%/value"
    assert sprintf("%s/%d", "only") == "only/%!d(MISSING)"
    assert sprintf("trailing %") == "trailing %!(NOVERB)"
    assert sprintf("trailing %.") == "trailing %!(NOVERB)"


def test_sprintf_reuses_a_bounded_directive_cache() -> None:
    gofmt_core._parse_directive.cache_clear()  # pyright: ignore[reportPrivateUsage]

    assert sprintf("%04d/%q", 7, "x") == '0007/"x"'
    first = gofmt_core._parse_directive.cache_info()  # pyright: ignore[reportPrivateUsage]
    assert sprintf("%04d/%q", 8, "y") == '0008/"y"'
    second = gofmt_core._parse_directive.cache_info()  # pyright: ignore[reportPrivateUsage]

    assert first.misses == 2
    assert second.hits == 2
    for index in range(4_200):
        sprintf(f"prefix-{index}:%d", index)
    bounded = gofmt_core._parse_directive.cache_info()  # pyright: ignore[reportPrivateUsage]
    assert bounded.maxsize == 4_096
    assert bounded.currsize == 4_096


def test_sprintf_directive_cache_is_safe_across_threads() -> None:
    gofmt_core._parse_directive.cache_clear()  # pyright: ignore[reportPrivateUsage]

    def render(value: int) -> str:
        return sprintf("%04d", value)

    with ThreadPoolExecutor(max_workers=8) as executor:
        outputs = list(executor.map(render, range(100)))

    assert outputs == [f"{value:04d}" for value in range(100)]
    info = gofmt_core._parse_directive.cache_info()  # pyright: ignore[reportPrivateUsage]
    assert info.currsize == 1


@pytest.mark.parametrize(
    ("format_string", "value", "expected"),
    [
        ("%t", 1, "%!t(int=1)"),
        ("%s", 1, "%!s(int=1)"),
        ("%f", 1, "%!f(int=1)"),
        ("%z", "x", "%!z(string=x)"),
    ],
)
def test_sprintf_reports_bad_verbs_in_band(
    format_string: str, value: object, expected: str
) -> None:
    assert sprintf(format_string, value) == expected


def test_sprintf_formats_integer_verbs_flags_and_alignment() -> None:
    assert sprintf("%c|%.6U|%.4d|% d|%#x|%O|%-5d", 65, 65, 7, 7, 31, 8, -2) == (
        "A|U+000041|0007| 7|0x1f|0o10|-2   "
    )
    assert sprintf("%5s|%5d", "x", 2) == "    x|    2"


def test_sprintf_formats_floats_complex_values_and_special_values() -> None:
    assert sprintf("%+.1f|% .1f", 2.0, 2.0) == "+2.0| 2.0"
    assert sprintf("%g/%g", 1 + 2j, 1 - 2j) == "(1+2i)/(1-2i)"
    assert sprintf("%g/%g/%g", math.nan, math.inf, -math.inf) == "NaN/+Inf/-Inf"
    assert sprintf("%v/%v/%v", math.nan, math.inf, -math.inf) == "NaN/+Inf/-Inf"
    assert sprintf("%v|%v|%v|%v", 12.193263113702178, 1e6, 1e-5, -0.0) == (
        "12.193263113702178|1e+06|1e-05|-0"
    )


def test_sprintf_supports_reordered_and_dynamic_operands() -> None:
    assert sprintf("%[2]d/%[1]d/%d", 11, 22, 33) == "22/11/22"
    assert sprintf("%[2]d", 11, 22, 33) == "22"
    assert sprintf("%[3]*.[2]*[1]f", 3.14159, 2, 8) == "    3.14"
    assert sprintf("%*s", -5, "go") == "go   "


def test_sprintf_reports_dynamic_operand_errors_like_go() -> None:
    assert sprintf("%[3]d", 1) == "%!d(BADINDEX)"
    assert sprintf("%[3]*d", 1) == "%!d(BADINDEX)"
    assert sprintf("%[x]d", 1) == "%!d(BADINDEX)"
    assert sprintf("%[", 1) == "%!(NOVERB)"
    assert sprintf("%*d") == "%!(BADWIDTH)%!d(MISSING)"
    assert sprintf("%.[3]*f", 1.0) == "%!(BADPREC)%!f(BADINDEX)"
    assert sprintf("%*d|%.*f", "x", 1, "y", 2.0) == (
        "%!(BADWIDTH)1|%!(BADPREC)2.000000"
    )
    assert sprintf("%.*f", -1, 2.0) == "2.000000"


def test_sprintf_supports_go_string_integer_and_float_extensions() -> None:
    assert sprintf("%x|%X|%q", "Go!", "Go!", 65) == "476f21|476F21|'A'"
    assert sprintf("%+q|%#q", "caf\N{LATIN SMALL LETTER E WITH ACUTE}", "raw") == (
        '"caf\\u00e9"|`raw`'
    )
    assert sprintf("%b|%x|%X", 3.5, 3.5, 3.5) == (
        "7881299347898368p-51|0x1.cp+01|0X1.CP+01"
    )
    assert sprintf("%b|%x|%X", 1 + 2j, 1 + 2j, 1 + 2j) == (
        "(4503599627370496p-52+4503599627370496p-51i)|"
        "(0x1p+00+0x1p+01i)|(0X1P+00+0X1P+01i)"
    )


def test_sprintf_formats_byte_slices_and_bytearrays() -> None:
    assert sprintf("%s|%q|%x|%X", b"Go!\n", b"Go!\n", b"Go!\n", b"Go!\n") == (
        'Go!\n|"Go!\\n"|476f210a|476F210A'
    )
    assert sprintf("%v|%#v|%T", bytearray([1, 15]), b"A", b"") == (
        "[1 15]|[]byte{0x41}|[]uint8"
    )


def test_sprintf_formats_explicit_go_pointers() -> None:
    target = object()
    pointer = GoPointer(target, target_type="widget")
    address = f"{id(target):x}"

    assert sprintf("%p|%#p|%020p|%v|%#v|%T", *(pointer,) * 6) == (
        f"0x{address}|{address}|0x{address.zfill(18)}|0x{address}|"
        f"(*widget)(0x{address})|*widget"
    )
    nil_pointer = GoPointer[object](None, target_type="widget")
    assert sprintf(
        "%p|%v|%#v|%T", nil_pointer, nil_pointer, nil_pointer, nil_pointer
    ) == ("0x0|<nil>|(*widget)(nil)|*widget")
    python_value = object()
    assert (
        sprintf("%p", python_value, format_mode="python") == f"0x{id(python_value):x}"
    )
    assert (
        sprintf("%p", python_value)
        == "%!p(object=<object object at " + hex(id(python_value)) + ">)"
    )


def test_sprintf_delegates_complete_state_to_go_formatter_protocol() -> None:
    class CustomValue:
        def __go_format__(self, spec: GoFormatSpec) -> str:
            return f"{spec.verb}:{spec.flags}:{spec.width}:{spec.precision}"

    assert sprintf("%#+8.3z", CustomValue()) == "z:#+:8:3"


def test_sprintf_requires_go_formatter_to_return_a_string() -> None:
    class InvalidFormatter:
        def __go_format__(self, spec: GoFormatSpec) -> object:
            return spec.width

    with pytest.raises(TypeError, match="return a string"):
        sprintf("%v", InvalidFormatter())


def test_sprintf_quotes_delimiters_and_non_bmp_control_characters() -> None:
    assert sprintf("%q|%q", 'say "go"', ord("'")) == ('"say \\"go\\""|\'\\\'\'')
    assert sprintf("%q", "\U000e0001") == '"\\U000e0001"'


def test_sprintf_formats_default_go_syntax_and_type_names() -> None:
    def function() -> None:
        return None

    assert sprintf("%v|%v|%v", UNTYPED_NIL, INVALID, 1 + 2j) == (
        "<nil>|<no value>|(1+2i)"
    )
    assert sprintf("%#v", ["x", 1]) == '[]interface {}{"x", 1}'
    assert sprintf("%v|%v", False, {"b": 2, "a": 1}) == "false|map[a:1 b:2]"
    assert sprintf("%v", {2 - 1j: "later", 2 - 2j: "first"}) == (
        "map[(2-2i):first (2-1i):later]"
    )
    assert sprintf("%v", {2: "integer", "1": "string"}) == ("map[2:integer 1:string]")
    assert sprintf(
        "%T|%T|%T|%T|%T|%T|%T|%T|%T|%T",
        None,
        True,
        1,
        1.0,
        1j,
        "x",
        {},
        [],
        function,
        object(),
    ) == (
        "<nil>|bool|int|float64|complex128|string|map[string]interface {}|"
        "[]interface {}|func|object"
    )


def test_python_mode_preserves_missing_and_nil_diagnostics() -> None:
    assert (
        sprintf(
            "%#v|%#v|%T|%T",
            INVALID,
            UNTYPED_NIL,
            INVALID,
            UNTYPED_NIL,
            format_mode="python",
        )
        == "<no value>|<nil>|invalid|nil"
    )
