from __future__ import annotations

import base64

from gotpl.funcs.sprout import Handler, registry
from gotpl.runtime import FunctionResult


def test_random_registry_preserves_lengths_and_character_sets() -> None:
    functions = Handler(registry("random")).build()

    assert functions["randAlphaNum"](0) == ""
    assert functions["randAlpha"](-1) == ""
    assert functions["randNumeric"](0) == ""
    assert functions["randAscii"](0) == ""

    alphanumeric = functions["randAlphaNum"](100)
    alphabetic = functions["randAlpha"](100)
    numeric = functions["randNumeric"](100)
    ascii_value = functions["randAscii"](100)
    assert isinstance(alphanumeric, str) and alphanumeric.isalnum()
    assert isinstance(alphabetic, str) and alphabetic.isalpha()
    assert isinstance(numeric, str) and numeric.isdigit()
    assert isinstance(ascii_value, str)
    assert all(32 <= ord(character) <= 126 for character in ascii_value)
    assert (
        len(alphanumeric) == len(alphabetic) == len(numeric) == len(ascii_value) == 100
    )


def test_random_registry_bytes_and_half_open_integer_range() -> None:
    functions = Handler(registry("random")).build()

    encoded = functions["randBytes"](32)
    assert isinstance(encoded, FunctionResult)
    assert encoded.error is None
    assert isinstance(encoded.value, str)
    assert len(base64.b64decode(encoded.value)) == 32
    assert functions["randBytes"](0) == FunctionResult.success("")

    for _ in range(100):
        value = functions["randInt"](-10, 20)
        assert isinstance(value, int)
        assert -10 <= value < 20
