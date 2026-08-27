from __future__ import annotations

import math
from collections.abc import Iterator, Mapping
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

import pytest

from gotpl._compat.gofmt import _core
from gotpl._compat.gofmt.go import GoFormatSpec, GoPointer
from gotpl._compat.gofmt.go import sprintf as go_sprintf
from gotpl._compat.gofmt.python import sprintf as python_sprintf
from gotpl._compat.gofmt.types import FormatMode, FormatValueKind


def test_directive_cache_is_bounded_and_thread_safe() -> None:
    _core._parse_directive.cache_clear()  # pyright: ignore[reportPrivateUsage]

    def render(value: int) -> str:
        return go_sprintf("%04d", value)

    with ThreadPoolExecutor(max_workers=8) as executor:
        outputs = list(executor.map(render, range(64)))

    assert outputs == [f"{value:04d}" for value in range(64)]
    for index in range(4_200):
        go_sprintf(f"prefix-{index}:%d", index)
    info = _core._parse_directive.cache_info()  # pyright: ignore[reportPrivateUsage]
    assert info.maxsize == info.currsize == 4_096


@pytest.mark.parametrize(
    ("format_string", "values", "expected"),
    [
        ("trailing %", (), "trailing %!(NOVERB)"),
        ("%[", (1,), "%!(NOVERB)"),
        ("%[x]d", (1,), "%!d(BADINDEX)"),
        ("%[0]d", (1,), "%!d(BADINDEX)"),
        ("%[3]*d", (1,), "%!d(BADINDEX)"),
        ("%*d", (), "%!(BADWIDTH)%!d(MISSING)"),
        ("%*d", (True, 2), "%!(BADWIDTH)2"),
        ("%.*f", (-1, 2.0), "2.000000"),
        ("%.*f", (True, 2.0), "%!(BADPREC)2.000000"),
        ("%.[3]*f", (1.0,), "%!(BADPREC)%!f(BADINDEX)"),
        ("%[3]d", (1,), "%!d(BADINDEX)"),
        ("%t", (1,), "%!t(int=1)"),
        ("%s", (1,), "%!s(int=1)"),
        ("%z", ("x",), "%!z(string=x)"),
    ],
)
def test_diagnostics_and_dynamic_argument_edges(
    format_string: str, values: tuple[object, ...], expected: str
) -> None:
    assert go_sprintf(format_string, *values) == expected


def test_boolean_rune_string_and_bytes_paths() -> None:
    assert go_sprintf("%t|%t", True, False) == "true|false"
    assert go_sprintf("%q|%+q", 65, 0x1F642) == "'A'|'\\U0001f642'"
    assert go_sprintf("%q", ord("'")) == "'\\''"
    assert go_sprintf("%.2X|%.2s", "Go!", bytearray(b"Go!")) == "476F|Go"
    assert go_sprintf("%q", 'say "go"') == '"say \\"go\\""'
    assert go_sprintf("%q", "\a\b\f\n\r\t\v\\") == ('"\\a\\b\\f\\n\\r\\t\\v\\\\"')
    assert go_sprintf("%q|%q|%q", "\x01", "\u0080", "\U000e0001") == (
        '"\\x01"|"\\u0080"|"\\U000e0001"'
    )
    assert go_sprintf("%#q", "contains`tick") == '"contains`tick"'


def test_integer_float_and_complex_branches() -> None:
    assert go_sprintf("%+d|% d|%#b|%#o|%#X", 2, 2, 3, 8, 31) == ("+2| 2|0b11|010|0X1F")
    assert go_sprintf("%08d|%-5d", -2, 2) == "-0000002|2    "
    assert go_sprintf("%b|%x|%X", 3.5, 3.5, 3.5) == (
        "7881299347898368p-51|0x1.cp+01|0X1.CP+01"
    )
    assert go_sprintf("%e|%E|%F|%G", 2.0, 2.0, 2.0, 1e6) == (
        "2.000000e+00|2.000000E+00|2.000000|1E+06"
    )
    assert go_sprintf("%+g|% g", 2.0, 2.0) == "+2| 2"
    assert go_sprintf("%g|%g|%g", math.nan, math.inf, -math.inf) == ("NaN|+Inf|-Inf")
    assert go_sprintf("%b|%X|%.2f", 1 - 2j, 1 - 2j, 1 - 2j) == (
        "(4503599627370496p-52-4503599627370496p-51i)|(0X1P+00-0X1P+01i)|(1.00-2.00i)"
    )


def test_padding_pointer_and_custom_formatter_edges() -> None:
    target = object()
    pointer = GoPointer(target, "widget")
    nil_pointer = GoPointer[object](None, "widget")
    address = f"{id(target):x}"

    assert go_sprintf("%020p|%#p", pointer, pointer) == (
        f"0x{address.zfill(18)}|{address}"
    )
    assert go_sprintf("%p|%v|%#v", nil_pointer, nil_pointer, nil_pointer) == (
        "0x0|<nil>|(*widget)(nil)"
    )
    assert go_sprintf("%p", target).startswith("%!p(object=<object object at 0x")
    assert python_sprintf("%p", target) == f"0x{id(target):x}"

    class PythonOnly:
        def __str__(self) -> str:
            return "python-value"

        def __go_format__(self, spec: GoFormatSpec) -> str:
            return f"go-{spec.verb}"

    assert go_sprintf("%v", PythonOnly()) == "go-v"
    assert python_sprintf("%v", PythonOnly()) == "python-value"


class _TypedMap(Mapping[str, int]):
    def __init__(self, map_type: object) -> None:
        self._map_type = map_type
        self._data = {"b": 2, "a": 1}

    def __getitem__(self, key: str) -> int:
        return self._data[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._data)

    def __len__(self) -> int:
        return len(self._data)

    def __go_map_type__(self) -> object:
        return self._map_type


def test_default_syntax_types_and_mapping_order() -> None:
    def function() -> None:
        return None

    assert go_sprintf("%v|%v|%v", False, 1 + 2j, bytearray([1, 15])) == (
        "false|(1+2i)|[1 15]"
    )
    assert go_sprintf("%#v", _TypedMap(("string", "int"))) == (
        'map[string]int{"a":1, "b":2}'
    )
    assert go_sprintf("%T", _TypedMap(("string", "int"))) == "map[string]int"
    assert go_sprintf("%v", {2 - 1j: "later", 2 - 2j: "first"}) == (
        "map[(2-2i):first (2-1i):later]"
    )
    assert go_sprintf("%v", {2: "integer", "1": "string"}) == (
        "map[2:integer 1:string]"
    )
    assert go_sprintf(
        "%T|%T|%T|%T|%T|%T|%T|%T|%T",
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
        "bool|int|float64|complex128|string|map[string]interface {}|"
        "[]interface {}|func|object"
    )
    assert go_sprintf("%#v", ("x", 1)) == '[]interface {}{"x", 1}'
    assert python_sprintf("%#v|%T", ["x"], ["x"]) == "['x']|list"


@pytest.mark.parametrize("result", ["bad", (), ("", "int"), ("string", 1)])
def test_invalid_typed_mapping_metadata_is_rejected(result: object) -> None:
    with pytest.raises(TypeError, match="two non-empty strings"):
        go_sprintf("%#v", _TypedMap(result))


def test_none_map_metadata_and_adapter_error_paths() -> None:
    assert go_sprintf("%#v", _TypedMap(None)).startswith("map[string]interface {}")

    @dataclass(frozen=True)
    class InvalidAdapter:
        def __go_format_value__(
            self,
            kind: FormatValueKind,
            mode: FormatMode,
            *,
            nested: bool,
        ) -> object:
            return kind, mode, nested

    with pytest.raises(TypeError, match="must return a string"):
        go_sprintf("%v", InvalidAdapter())
