import json
from pathlib import Path
from typing import TypedDict, cast

import pytest

from goduration import Duration, DurationParseError

FIXTURE = Path(__file__).with_name("go-duration-vectors.json")


class ParseCase(TypedDict):
    text: str
    nanoseconds: int
    formatted: str


class InvalidCase(TypedDict):
    text: str
    error: str


class OperationCase(TypedDict):
    operation: str
    value: int
    multiple: int
    result: int


class OracleFixture(TypedDict):
    schema_version: int
    go_version: str
    parse: list[ParseCase]
    invalid: list[InvalidCase]
    operations: list[OperationCase]


def load_fixture() -> OracleFixture:
    raw: object = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert isinstance(raw, dict)
    return cast(OracleFixture, raw)


def test_go_duration_parse_and_string_vectors() -> None:
    fixture = load_fixture()

    assert fixture["schema_version"] == 2
    assert fixture["go_version"] == "go1.27.0"
    for case in fixture["parse"]:
        duration = Duration.parse(case["text"])
        assert duration.nanoseconds == case["nanoseconds"]
        assert str(duration) == case["formatted"]


def test_go_duration_invalid_vectors() -> None:
    for case in load_fixture()["invalid"]:
        with pytest.raises(DurationParseError) as captured:
            Duration.parse(case["text"])
        assert str(captured.value) == case["error"]


def test_go_duration_operation_vectors() -> None:
    for case in load_fixture()["operations"]:
        duration = Duration(case["value"])
        multiple = Duration(case["multiple"])
        if case["operation"] == "negate":
            result = -duration
        else:
            operation = {
                "add": duration.__add__,
                "divide": duration.__truediv__,
                "modulo": duration.__mod__,
                "multiply": duration.__mul__,
                "round": duration.round,
                "subtract": duration.__sub__,
                "truncate": duration.truncate,
            }[case["operation"]]
            result = operation(multiple)
        assert isinstance(result, Duration)
        assert result.nanoseconds == case["result"]
