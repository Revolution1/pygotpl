from __future__ import annotations

from dataclasses import dataclass

import pytest

import gotpl._compat.gofmt as gofmt
from gotpl._compat.gofmt.go import GoFormatSpec, GoPointer
from gotpl._compat.gofmt.go import sprintf as go_sprintf
from gotpl._compat.gofmt.python import sprintf as python_sprintf
from gotpl._compat.gofmt.types import FormatMode, FormatValueKind


def test_top_level_defaults_to_go_surface() -> None:
    assert gofmt.sprintf is go_sprintf
    assert go_sprintf("%v %#v %T", True, "x", b"") == ('true "x" []uint8')
    assert go_sprintf("%v %T", None, None) == "<nil> <nil>"


def test_python_surface_is_explicit_and_uses_python_value_rendering() -> None:
    value = {"ready": True}

    assert python_sprintf("%v %#v %T", value, value, value) == (
        "{'ready': True} {'ready': True} dict"
    )
    assert go_sprintf("%v", value) == "map[ready:true]"


def test_go_surface_formats_adopted_scalar_and_operand_matrix() -> None:
    assert go_sprintf("%c|%.6U|%.4d|%#x", 65, 65, 7, 31) == ("A|U+000041|0007|0x1f")
    assert go_sprintf("%[2]d/%[1]d/%d", 11, 22, 33) == "22/11/22"
    assert go_sprintf("%[3]*.[2]*[1]f", 3.14159, 2, 8) == "    3.14"
    assert go_sprintf("%+q|%#q", "café", "raw") == '"caf\\u00e9"|`raw`'


def test_bytes_and_explicit_pointer_have_go_shapes() -> None:
    target = object()
    pointer = GoPointer(target, target_type="widget")
    address = f"{id(target):x}"

    assert go_sprintf("%v|%#v|%T", b"A", b"A", b"") == ("[65]|[]byte{0x41}|[]uint8")
    assert go_sprintf("%p|%#v|%T", pointer, pointer, pointer) == (
        f"0x{address}|(*widget)(0x{address})|*widget"
    )


def test_go_formatter_receives_immutable_directive_state() -> None:
    class Coordinate:
        def __go_format__(self, spec: GoFormatSpec) -> str:
            return f"{spec.verb}:{spec.flags}:{spec.width}:{spec.precision}"

    assert go_sprintf("%#+8.3v", Coordinate()) == "v:#+:8:3"


def test_integration_value_adapter_does_not_require_gotpl() -> None:
    @dataclass(frozen=True)
    class Missing:
        def __go_format_value__(
            self,
            kind: FormatValueKind,
            mode: FormatMode,
            *,
            nested: bool,
        ) -> str:
            del nested
            if kind == "type":
                return "missing" if mode == "python" else "<nil>"
            return "<missing>"

    value = Missing()
    assert go_sprintf("%v %#v %T", value, value, value) == ("<missing> <missing> <nil>")
    assert python_sprintf("%v %#v %T", value, value, value) == (
        "<missing> <missing> missing"
    )


def test_invalid_public_inputs_are_actionable() -> None:
    with pytest.raises(TypeError, match="format must be a string"):
        go_sprintf(1, "value")

    class InvalidFormatter:
        def __go_format__(self, spec: GoFormatSpec) -> object:
            return spec.width

    with pytest.raises(TypeError, match="return a string"):
        go_sprintf("%v", InvalidFormatter())
