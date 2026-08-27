import json
from pathlib import Path
from typing import TypedDict, cast

import pytest

from gotime.go import UTC, Location, Time


class Instant(TypedDict):
    unix: int
    nanosecond: int
    location: str


class Vector(TypedDict):
    name: str
    value: Instant
    iso_year: int
    iso_week: int
    zone: str
    offset: int
    zone_start: Instant
    zone_end: Instant
    binary_hex: str
    text: str
    json: str
    text_decoded: Instant
    string: str
    go_string: str


_DATA = cast(
    dict[str, object],
    json.loads(Path(__file__).with_name("go-time-vectors.json").read_text()),
)
assert _DATA["schema"] == 1
_VECTORS = cast(list[Vector], _DATA["vectors"])


def _time(value: Instant) -> Time:
    if value["location"] in {"", "UTC"}:
        location = UTC
    elif value["location"] == "LMT":
        location = Location.fixed("LMT", 321)
    else:
        location = Location.load(value["location"])
    return Time.from_unix(value["unix"], value["nanosecond"], location=location)


@pytest.mark.parametrize("vector", _VECTORS, ids=lambda vector: vector["name"])
def test_go_time_oracle(vector: Vector) -> None:
    value = _time(vector["value"])

    assert value.iso_week() == (vector["iso_year"], vector["iso_week"])
    assert value.zone() == (vector["zone"], vector["offset"])
    actual_start, actual_end = value.zone_bounds()
    expected_start, expected_end = (
        _time(vector["zone_start"]),
        _time(vector["zone_end"]),
    )
    assert actual_start.equal(expected_start)
    assert actual_end.equal(expected_end)
    assert value.marshal_binary().hex() == vector["binary_hex"]
    assert Time.unmarshal_binary(bytes.fromhex(vector["binary_hex"])).equal(value)
    assert value.marshal_text().decode() == vector["text"]
    assert value.marshal_json().decode() == vector["json"]
    decoded = _time(vector["text_decoded"])
    assert Time.unmarshal_text(vector["text"].encode()).equal(decoded)
    assert Time.unmarshal_json(vector["json"].encode()).equal(decoded)
    assert str(value) == vector["string"]
    assert value.go_string() == vector["go_string"]
