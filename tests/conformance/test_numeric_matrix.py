from __future__ import annotations

import random
from io import StringIO

import gotpl
import gotpl.funcs.sprig as sprig

from .support import ExpectedResult, TemplateRequest, run_go_oracle_many

_EXPRESSIONS = (
    "float64 ` 1.5 `",
    "float64 `1_2.5`",
    "float64 `0x1p2`",
    "float64 `0x_1p2`",
    "float64 `0x1_0p2`",
    "float64 `1_2.3_4e5_6`",
    "float64 `1__2`",
    "float64 `0x1.2`",
    "float64 `0x1p99999`",
    "float64 `-0x1.8p1`",
    "float64 `nan`",
    "float64 `NAN`",
    "float64 `+NaN`",
    "float64 `Infinity`",
    "float64 `-0`",
    "int ` 12 `",
    "int `+012`",
    "int `-012`",
    "int `00.0`",
    "int `1.00`",
    "int `1.0001`",
    "int `0b101`",
    "int `0o17`",
    "int `0x_10`",
    "int `1_000`",
    "int64 `9223372036854775807`",
    "int64 `9223372036854775808`",
    "atoi `+12`",
    "atoi `1_000`",
    "atoi `\uff11\uff12`",
    "toDecimal `+077`",
    "toDecimal `7_7`",
    "toDecimal 7.0",
    "toDecimal -7.0",
    "toDecimal 7.5",
    "add",
    "add 9223372036854775807 1",
    "add1 9223372036854775807",
    "sub -9223372036854775808 1",
    "mul 4611686018427387904 2",
    "mul 7",
    "div -7 3",
    "div -9223372036854775808 -1",
    "mod -7 3",
    "mod -9223372036854775808 -1",
    "max -2 -1 -3",
    "biggest -2 -1 -3",
    "min -2 -1 -3",
    "add1f `3.4`",
    "addf",
    "addf `0.1` `0.2`",
    "subf 5",
    "subf `100000000000000000000` `0.5`",
    "mulf 5",
    "mulf `1.2345678901234567` `9.876543210987654`",
    "divf 2 3",
    "divf `0.00000000000000000001` 3",
    "divf 1 3 3",
    "maxf `NaN` 1",
    "maxf `-0` `0`",
    "maxf `-0` `-0`",
    "minf `Inf` 1",
    "minf `0` `-0`",
    "ceil `-0`",
    "ceil -1.2",
    "floor `-0`",
    "floor -1.2",
    "round 1.25 1",
    # Keep this above the binary half-threshold: Go's math.Pow result differs
    # between amd64 and arm64 for the adjacent 123.5555 boundary case.
    "round 123.5556 3",
    "round -1.24 1",
    "round 123.233 2 0.3",
    "round 1 400",
    "round 1 -400",
    "until 0",
    "until 4",
    "until -4",
    "untilStep 3 0 -1",
    "untilStep 3 0 0",
    "untilStep 0 3 -1",
    "seq",
    "seq 0",
    "seq -3",
    "seq 0 -3",
    "seq 0 3 10",
    "seq 3 -3 2",
    "seq 3 0 3",
    "seq 3 1 3",
    "seq 0 1 2 3",
)
_RANDOM = random.Random(0xA11CE)
_INTEGER_PAIRS = tuple(
    (
        _RANDOM.randrange(-(1 << 63), 1 << 63),
        _RANDOM.choice((-1, 1)) * _RANDOM.randrange(1, 1 << 63),
    )
    for _ in range(32)
)
_FLOAT_PAIRS = tuple(
    (
        _RANDOM.uniform(-1_000_000, 1_000_000),
        _RANDOM.choice((-1.0, 1.0)) * _RANDOM.uniform(0.001, 1_000_000),
        _RANDOM.randrange(-6, 7),
        _RANDOM.choice((0.3, 0.5, 0.7)),
    )
    for _ in range(32)
)
_INTEGER_EXPRESSIONS = tuple(
    expression
    for left, right in _INTEGER_PAIRS
    for expression in (
        f"add {left} {right}",
        f"sub {left} {right}",
        f"mul {left} {right}",
        f"div {left} {right}",
        f"mod {left} {right}",
        f"max {left} {right}",
        f"min {left} {right}",
    )
)
_FLOAT_EXPRESSIONS = tuple(
    expression
    for left, right, places, threshold in _FLOAT_PAIRS
    for left_text, right_text in ((format(left, ".17g"), format(right, ".17g")),)
    for expression in (
        f"addf `{left_text}` `{right_text}`",
        f"subf `{left_text}` `{right_text}`",
        f"mulf `{left_text}` `{right_text}`",
        f"divf `{left_text}` `{right_text}`",
        f"maxf `{left_text}` `{right_text}`",
        f"minf `{left_text}` `{right_text}`",
        f"round `{left_text}` {places} {threshold}",
    )
)


def _assert_expressions_match_go(expressions: tuple[str, ...], prefix: str) -> None:
    requests = [
        TemplateRequest(
            engine="text",
            name=f"{prefix}-{index}",
            template='{{printf "%v" (' + expression + ")}}",
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


def test_numeric_conversion_arithmetic_and_sequence_matrix_matches_go() -> None:
    _assert_expressions_match_go(_EXPRESSIONS, "numeric-matrix")


def test_seeded_integer_arithmetic_matrix_matches_go() -> None:
    _assert_expressions_match_go(_INTEGER_EXPRESSIONS, "numeric-integer-seeded")


def test_seeded_float_arithmetic_and_rounding_matrix_matches_go() -> None:
    _assert_expressions_match_go(_FLOAT_EXPRESSIONS, "numeric-float-seeded")
