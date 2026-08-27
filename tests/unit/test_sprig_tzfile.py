# pyright: reportPrivateUsage=false

from __future__ import annotations

import struct
from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from gotime import _tzfile


def _tzif_v1(
    abbreviation: bytes = b"ABC",
    *,
    offset: int = 3_600,
    name_index: int = 0,
    transition_type: int | None = None,
) -> bytes:
    time_count = transition_type is not None
    counts = struct.pack(">6I", 0, 0, 0, int(time_count), 1, len(abbreviation))
    transitions = struct.pack(">lB", 0, transition_type) if time_count else b""
    type_info = struct.pack(">lBB", offset, 0, name_index)
    return b"TZif\0" + bytes(15) + counts + transitions + type_info + abbreviation


def test_tzif_v1_type_metadata_and_unterminated_abbreviation() -> None:
    metadata = _tzfile._parse_zone_metadata(_tzif_v1())

    assert tuple((item.name, item.offset) for item in metadata.zone_types) == (
        ("ABC", 3_600),
    )


def test_tzif_parser_rejects_invalid_headers_and_abbreviation_indexes() -> None:
    with pytest.raises(ValueError, match="header"):
        _tzfile._parse_zone_metadata(b"not a TZif file")
    with pytest.raises(ValueError, match="abbreviation index"):
        _tzfile._parse_zone_metadata(_tzif_v1(name_index=3))
    with pytest.raises(ValueError, match="transition type"):
        _tzfile._parse_zone_metadata(_tzif_v1(transition_type=1))


def test_pre_transition_lookup_handles_missing_metadata() -> None:
    custom = ZoneInfo.from_file(BytesIO(_tzif_v1()), key="Missing/Metadata")

    assert _tzfile.zone_before_first_transition(custom, -1) is None


def test_go_first_zone_selection_rules() -> None:
    zone_type = _tzfile._ZoneType
    metadata_type = _tzfile._ZoneMetadata

    preceding_standard = metadata_type(
        (0, 1),
        (2, 0),
        (zone_type("A", 0, False), zone_type("B", 1, False), zone_type("C", 2, True)),
    )
    later_standard = metadata_type(
        (0, 1),
        (1, 0),
        (zone_type("A", 0, True), zone_type("B", 1, True), zone_type("C", 2, False)),
    )
    initial_standard = metadata_type((0,), (0,), (zone_type("A", 0, False),))
    all_daylight = metadata_type((0,), (0,), (zone_type("A", 0, True),))

    assert _tzfile._first_zone_index(preceding_standard) == 1
    assert _tzfile._first_zone_index(later_standard) == 2
    assert _tzfile._first_zone_index(initial_standard) == 0
    assert _tzfile._first_zone_index(all_daylight) == 0


def test_zone_type_cache_treats_missing_and_malformed_data_as_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def missing_data(key: str) -> None:
        return None

    def malformed_data(key: str) -> bytes:
        return b"broken"

    _tzfile._zone_types.cache_clear()
    monkeypatch.setattr(_tzfile, "_read_zone_data", missing_data)
    assert _tzfile._zone_types("missing") == ()

    _tzfile._zone_types.cache_clear()
    monkeypatch.setattr(_tzfile, "_read_zone_data", malformed_data)
    assert _tzfile._zone_types("broken") == ()


def test_zone_data_loading_supports_absolute_system_and_packaged_paths(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    absolute = tmp_path / "custom-zone"
    absolute.write_bytes(_tzif_v1())
    assert _tzfile._read_zone_data(str(absolute)) == _tzif_v1()
    assert _tzfile._read_zone_data(str(tmp_path / "missing")) is None

    assert (_tzfile._read_zone_data("UTC") or b"").startswith(b"TZif")
    monkeypatch.setattr(
        _tzfile.zoneinfo,  # pyright: ignore[reportPrivateImportUsage]
        "TZPATH",
        (str(tmp_path),),
    )
    assert (_tzfile._read_zone_data("America/New_York") or b"").startswith(b"TZif")
    monkeypatch.setattr(
        _tzfile.zoneinfo,  # pyright: ignore[reportPrivateImportUsage]
        "TZPATH",
        (),
    )
    assert (_tzfile._read_zone_data("America/New_York") or b"").startswith(b"TZif")
    assert _tzfile._read_zone_data("Not/AZone") is None


def test_abbreviation_fallback_supports_non_zoneinfo_tzinfo() -> None:
    location = timezone(timedelta(hours=2), "CUSTOM")
    value = datetime(2024, 1, 1, 12)

    assert _tzfile.abbreviation_offset(location, "CUSTOM", value) == 7_200
    assert _tzfile.abbreviation_offset(location, "UNKNOWN", value) is None
