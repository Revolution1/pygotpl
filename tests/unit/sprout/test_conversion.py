from __future__ import annotations

from collections.abc import Callable, Mapping

import pytest
from goduration.go import Duration

from gotpl import Template
from gotpl.funcs.sprout import Handler, registry
from gotpl.runtime import FunctionResult


def _functions() -> Mapping[str, Callable[..., object]]:
    return Handler(registry("conversion")).build()


def _failure(value: object, message: str) -> None:
    assert isinstance(value, FunctionResult)
    assert value.error is not None
    assert message in str(value.error)


def test_conversion_registry_matches_sprout_scalar_and_value_objects() -> None:
    functions = _functions()
    source = (
        '{{toBool "true"}}|{{toBool 0}}|{{toInt "42"}}|{{toInt64 3.9}}|'
        '{{toUint 7}}|{{toUint64 8}}|{{toFloat64 "1.25"}}|'
        '{{toOctal "755"}}|{{toString 12.5}}|{{toDuration "1h2m3s"}}|'
        "{{toDuration 1000}}|"
        '{{toLocalDate "2006-01-02 15:04" "UTC" "2024-03-02 04:05"}}'
    )

    assert Template(source, functions=functions).render() == (
        "true|false|42|3|7|8|1.25|493|12.5|1h2m3s|1µs|2024-03-02 04:05:00 +0000 UTC"
    )


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (True, True),
        (2, True),
        (0.0, False),
        (" T ", True),
        ("FALSE", False),
    ],
)
def test_to_bool_accepts_sprout_scalar_forms(value: object, expected: bool) -> None:
    assert _functions()["toBool"](value) is expected


def test_conversion_failures_are_explicit_function_results() -> None:
    functions = _functions()

    _failure(functions["toBool"]("yes"), "failed to convert")
    _failure(functions["toInt"](object()), "unable to cast object")
    _failure(functions["toInt64"](1 << 63), "signed 64-bit")
    _failure(functions["toUint64"](1 << 64), "unsigned 64-bit")
    _failure(functions["toFloat64"](object()), "unable to cast object")
    _failure(functions["toOctal"]("8"), "failed to parse octal")
    _failure(functions["toDate"]("2006-01-02", "not-a-date"), "cannot parse")
    _failure(
        functions["toLocalDate"]("2006-01-02", "Not/AZone", "2024-01-01"),
        "unknown time zone",
    )
    _failure(functions["toDuration"](object()), "unable to cast object")
    _failure(functions["toDuration"](1 << 63), "signed 64-bit nanosecond range")


def test_integer_and_float_conversions_cover_go_casting_edges() -> None:
    functions = _functions()

    assert functions["toInt"](True) == 1
    assert functions["toInt"](4) == 4
    assert functions["toInt"](4.9) == 4
    assert functions["toInt"](b"0x10") == 16
    assert functions["toInt"]("08") == 8
    assert functions["toUint"](-1) == (1 << 64) - 1
    assert functions["toFloat64"](True) == 1.0
    assert functions["toFloat64"](False) == 0.0
    assert functions["toFloat64"](bytearray(b"1.25")) == 1.25


def test_string_and_duration_conversions_preserve_special_values() -> None:
    functions = _functions()
    duration = Duration.parse("2s")

    assert functions["toString"](bytearray(b"a\xff")) == "a�"
    assert functions["toString"](ValueError("broken")) == "broken"
    assert functions["toDuration"](duration) is duration
