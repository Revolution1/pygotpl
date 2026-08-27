from __future__ import annotations

import json
import math
from pathlib import Path
from typing import TypedDict, cast

import pytest

from gotpl._compat.gofmt.go import sprintf


class Vector(TypedDict):
    name: str
    format: str
    output: str


_DATA = cast(
    dict[str, object],
    json.loads(Path(__file__).with_name("go-fmt-vectors.json").read_text()),
)
assert _DATA["schema"] == 1
_VECTORS = cast(list[Vector], _DATA["vectors"])

_VALUES: dict[str, tuple[object, ...]] = {
    "plain-percent": (),
    "integer-flags": (65, 65, 7, 7, 31, 8, -2),
    "width": ("x", 2),
    "float": (2.0, 2.0, 12.193263113702178),
    "special-float": (math.nan, math.inf, -math.inf),
    "complex": (1 + 2j, 1 + 2j),
    "string": ("Go!", "Go!\n", "Go!", "café", "raw"),
    "unicode-precision": ("日本語abc", "日本語abc"),
    "bytes": (b"Go!\n", b"Go!\n", b"Go!\n", bytes([1, 15]), b"A", b""),
    "reordered": (11, 22, 33),
    "dynamic": (3.14159, 2, 8),
    "negative-width": (-5, "go"),
    "missing": ("only",),
    "bad-index": (1,),
    "bad-width": ("x", 1),
    "extra": (1,),
    "nil": (None, None, None),
    "slice": (["x", 1], ["x", 1], []),
    "map": ({"b": 2, "a": 1},),
}


@pytest.mark.parametrize("vector", _VECTORS, ids=lambda vector: vector["name"])
def test_go_127_sprintf_oracle(vector: Vector) -> None:
    assert sprintf(vector["format"], *_VALUES[vector["name"]]) == vector["output"]
