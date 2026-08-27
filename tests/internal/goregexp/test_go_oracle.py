from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import TypedDict, cast

import pytest

from gotpl._compat.goregexp.go import compile, quote_meta


class Vector(TypedDict):
    name: str
    output: object


_DATA = cast(
    dict[str, object],
    json.loads(Path(__file__).with_name("go-regexp-vectors.json").read_text()),
)
assert _DATA["schema"] == 1
_VECTORS = cast(list[Vector], _DATA["vectors"])

_CASES: dict[str, Callable[[], object]] = {
    "ascii-digit": lambda: compile(r"^\d+$").matches("\N{ARABIC-INDIC DIGIT ONE}"),
    "leftmost-first": lambda: compile("a|aa").find("aa"),
    "find-all-empty": lambda: compile("a*").find_all("baaab"),
    "find-all-zero": lambda: compile("a").find_all("banana", 0),
    "named-replacement": lambda: compile(r"(?P<word>[a-z]+)").replace_all(
        "abc-12", "<${word}>"
    ),
    "literal-replacement": lambda: compile("a").replace_all_literal("banana", "$1"),
    "split-capture": lambda: compile("(a)").split("banana"),
    "split-one": lambda: compile("a").split("banana", 1),
    "quote-meta": lambda: quote_meta("a+b[0]"),
    "unicode-greek": lambda: compile(r"^\p{Greek}+$").matches("Ωβ"),
    "unicode-complement": lambda: compile(r"^\P{ASCII}+$").matches("é"),
    "ungreedy": lambda: compile("(?U)a.+b").find("a1b2b"),
    "octal": lambda: compile(r"\777").matches("ǿ"),
    "empty-split": lambda: compile("").split("éx"),
}


@pytest.mark.parametrize("vector", _VECTORS, ids=lambda vector: vector["name"])
def test_go_127_regexp_oracle(vector: Vector) -> None:
    assert _CASES[vector["name"]]() == vector["output"]
