from __future__ import annotations

from gotime.go import UTC, Time

from gotpl.funcs.sprout import Handler, registry
from gotpl.runtime import FunctionResult


def _unwrap(result: object) -> object:
    assert isinstance(result, FunctionResult)
    assert result.error is None
    return result.value


def test_time_registry_formats_converts_and_modifies_go_time_values() -> None:
    functions = Handler(registry("time")).build()
    value = Time.from_unix(1_715_094_245, 123_456_789, location=UTC)

    assert _unwrap(functions["date"]("02 Jan 06 15:04 -0700", value)) == (
        "07 May 24 15:04 +0000"
    )
    assert (
        _unwrap(functions["dateInZone"]("02 Jan 06 15:04 -0700", value, "UTC"))
        == "07 May 24 15:04 +0000"
    )
    assert functions["duration"]("93784") == "26h3m4s"
    assert functions["unixEpoch"](value) == "1715094245"
    assert functions["toUnixMilli"](value) == "1715094245123"
    assert functions["toUnixMicro"](value) == "1715094245123456"
    assert _unwrap(functions["fromUnix"]("1715094245")) == Time.from_unix(1_715_094_245)
    assert _unwrap(functions["fromUnixMilli"]("1715094245123")) == (
        Time.from_unix_milliseconds(1_715_094_245_123)
    )
    assert _unwrap(functions["fromUnixMicro"]("1715094245123456")) == (
        Time.from_unix_microseconds(1_715_094_245_123_456)
    )
    modified = _unwrap(functions["dateModify"]("1h", value))
    assert isinstance(modified, Time)
    assert modified.unix() == value.unix() + 3_600
    assert functions["durationRound"]("2400h5s") == "3mo"
    assert _unwrap(functions["htmlDate"](value)) == "2024-05-07"
    assert _unwrap(functions["htmlDateInZone"](value, "UTC")) == "2024-05-07"


def test_time_registry_aliases_and_failures_follow_sprout() -> None:
    functions = Handler(registry("time")).build()
    value = Time.from_unix(1_715_094_245, location=UTC)

    assert functions["toUnix"](value) == "1715094245"
    modified = functions["mustDateModify"]("zz", value)
    assert isinstance(modified, FunctionResult)
    assert modified.error is not None
    assert "invalid duration" in str(modified.error)
    invalid = functions["fromUnix"]("invalid")
    assert isinstance(invalid, FunctionResult)
    assert invalid.error is not None
    invalid_zone = functions["dateInZone"]("2006", value, "invalid")
    assert isinstance(invalid_zone, FunctionResult)
    assert invalid_zone.error is not None


def test_time_registry_now_and_date_ago_use_current_wall_time() -> None:
    functions = Handler(registry("time")).build()

    now = functions["now"]()
    assert isinstance(now, Time)
    assert functions["dateAgo"](now) in {"0s", "1s"}
