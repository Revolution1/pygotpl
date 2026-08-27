from datetime import UTC, datetime, timedelta, tzinfo
from pathlib import Path
from zoneinfo import TZPATH, ZoneInfo, ZoneInfoNotFoundError, reset_tzpath

import pytest

import gotpl
import gotpl.funcs.sprig as sprig
from gotpl.funcs.sprig import dates

FIXED_NOW = datetime(2024, 7, 9, 13, 4, 5, 500_000, tzinfo=UTC)


def fixed_clock() -> datetime:
    return FIXED_NOW


def test_registry_accepts_an_injected_clock_for_time_dependent_functions() -> None:
    functions = sprig.text_func_map(clock=fixed_clock)

    assert (
        gotpl.render(
            '{{dateInZone "2006-01-02 15:04:05" "unsupported" "UTC"}}|'
            '{{ago 1720530120}}|{{$n := now}}{{dateInZone "15:04:05" $n "UTC"}}',
            functions=functions,
        )
        == "2024-07-09 13:04:05|2m6s|13:04:05"
    )


def test_date_helpers_accept_timestamps_datetimes_and_fallback_values() -> None:
    naive = datetime(2024, 7, 9, 13, 4, 5)

    assert dates.now(clock=fixed_clock) is FIXED_NOW
    assert dates.date_in_zone("2006-01-02", 0, "UTC") == "1970-01-01"
    assert dates.date_in_zone("2006-01-02", False, "UTC", clock=fixed_clock) == (
        "2024-07-09"
    )
    assert dates.date_in_zone("15:04", naive, "Local") == "13:04"
    assert dates.date_in_zone("15:04", FIXED_NOW, "Bad/Zone") == "13:04"
    assert dates.html_date_in_zone(FIXED_NOW, "UTC") == "2024-07-09"
    assert dates.html_date(FIXED_NOW) == "2024-07-09"


def test_named_zones_use_packaged_tzdata_without_system_zoneinfo() -> None:
    try:
        reset_tzpath(())
        ZoneInfo.clear_cache()
        assert dates.date_in_zone("MST -0700", FIXED_NOW, "Asia/Kolkata") == (
            "IST +0530"
        )
    finally:
        reset_tzpath(TZPATH)
        ZoneInfo.clear_cache()


def test_local_zone_uses_platform_discovery_when_tz_is_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected = ZoneInfo("America/New_York")
    monkeypatch.delenv("TZ", raising=False)
    monkeypatch.setattr(dates, "get_localzone", lambda: expected)

    assert dates.date_in_zone("MST -0700", FIXED_NOW, "Local") == "EDT -0400"


def test_local_zone_falls_back_to_utc_when_platform_discovery_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def missing_zone() -> ZoneInfo:
        raise ZoneInfoNotFoundError("missing local zone")

    monkeypatch.delenv("TZ", raising=False)
    monkeypatch.setattr(dates, "get_localzone", missing_zone)

    assert dates.date_in_zone("MST -0700", FIXED_NOW, "Local") == "UTC +0000"


def test_absolute_tz_file_and_invalid_file_follow_go_fallback(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    system_zone = next(
        (root / "America" / "New_York" for root in map(Path, TZPATH) if root.exists()),
        None,
    )
    if system_zone is not None and system_zone.is_file():
        monkeypatch.setenv("TZ", f":{system_zone}")
        winter = datetime(2024, 1, 15, tzinfo=UTC)
        assert dates.date_in_zone("MST -0700", winter, "Local") == "EST -0500"

    invalid_zone = tmp_path / "invalid-zone"
    invalid_zone.write_bytes(b"not a TZif file")
    monkeypatch.setenv("TZ", str(invalid_zone))
    assert dates.date_in_zone("MST -0700", FIXED_NOW, "Local") == "UTC +0000"


def test_date_zone_conversion_has_an_overflow_fallback() -> None:
    class OverflowingDateTime(datetime):
        def astimezone(self, tz: tzinfo | None = None) -> datetime:
            raise OverflowError("outside platform range")

    value = OverflowingDateTime(1, 1, 1, tzinfo=UTC)
    assert dates.date_in_zone("2006-01-02", value, "UTC") == "0001-01-01"


def test_date_modification_has_must_and_non_must_error_paths() -> None:
    assert dates.date_modify("1h30m", FIXED_NOW) == FIXED_NOW + timedelta(minutes=90)
    assert dates.date_modify("0", FIXED_NOW) == FIXED_NOW
    assert dates.date_modify("bad", FIXED_NOW) is FIXED_NOW
    assert dates.must_date_modify("-500ms", FIXED_NOW) == FIXED_NOW - timedelta(
        milliseconds=500
    )
    assert isinstance(
        dates.must_date_modify("-2562047h47m16.854775808s", FIXED_NOW), datetime
    )
    with pytest.raises(ValueError, match="invalid duration"):
        dates.must_date_modify("1h!", FIXED_NOW)
    with pytest.raises(ValueError, match="invalid duration"):
        dates.must_date_modify("1h!2m", FIXED_NOW)
    with pytest.raises(ValueError, match="invalid duration"):
        dates.must_date_modify("2562047h47m16.854775808s", FIXED_NOW)


def test_nanosecond_parsing_formatting_and_naive_arithmetic() -> None:
    parsed = dates.must_to_date(
        "2006.01.02 15:04:05.000000000",
        "2024.07.09 13:04:05.123456789",
    )

    assert dates.date_in_zone("05.000000000", parsed, "UTC") == "05.123456789"
    naive = datetime(2024, 7, 9, 13, 4, 5, 123_456)
    moved = dates.must_date_modify("876544000ns", naive)
    assert dates.date_in_zone("05.000000000", moved, "UTC") == "06.000000000"

    with pytest.raises(ValueError, match="fractional second out of range"):
        dates.must_to_date(
            "2006-01-02 15:04:05.000000000",
            "2024-07-09 13:04:05.1234567890",
        )
    with pytest.raises(ValueError):
        dates.must_to_date(
            "2006-01-02 15:04:05.000000000",
            "2024-07-09 13:04:05",
        )


def test_zone_abbreviation_validation_boundaries() -> None:
    parsed = dates.must_to_date("2006-01-02 15:04 MST", "2024-07-09 13:04 UTC")
    assert dates.unix_epoch(parsed) == "1720530240"

    for value in (
        "2024-07-09 13:04 +00",
        "2024-07-09 13:04 ABCD",
        "2024-07-09 13:04",
    ):
        with pytest.raises(ValueError):
            dates.must_to_date("2006-01-02 15:04 MST", value)


def test_ago_and_duration_round_use_injected_time() -> None:
    assert dates.ago(FIXED_NOW - timedelta(seconds=125), clock=fixed_clock) == "2m5s"
    assert dates.ago(FIXED_NOW + timedelta(seconds=5), clock=fixed_clock) == "-5s"
    assert dates.ago(FIXED_NOW - timedelta(milliseconds=500), clock=fixed_clock) == "1s"
    assert (
        dates.duration_round(FIXED_NOW - timedelta(hours=49), clock=fixed_clock) == "2d"
    )
    assert dates.duration_round("8761h") == "1y"
    assert dates.duration_round(object()) == "0s"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("0", "0s"),
        ("-61", "-1m1s"),
        ("9223372036854775808", "0s"),
        ("20211507185753197", "512ns"),
        ("21971086762712130", "5.12µs"),
        ("18446744074", "290.448384ms"),
        (object(), "0s"),
    ],
)
def test_duration_sprig_input_coercion(value: object, expected: str) -> None:
    assert dates.duration(value) == expected


def test_date_parsing_zero_time_epoch_and_percent_literals() -> None:
    parsed = dates.must_to_date(
        "2006-01-02 15:04:05 -0700", "2024-07-09 13:04:05 +0000"
    )

    assert dates.unix_epoch(parsed) == "1720530245"
    assert dates.unix_epoch(datetime(1969, 12, 31, 23, 59, 59, 500_000, UTC)) == "-1"
    assert dates.date_in_zone("2006 %% 01", parsed, "UTC") == "2024 %% 07"
    assert dates.to_date("2006-01-02", "bad") == datetime(1, 1, 1, tzinfo=UTC)
