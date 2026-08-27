"""Minimal TZif metadata reader for Go-compatible zone lookup."""

from __future__ import annotations

import os
import struct
import zoneinfo
from bisect import bisect_right
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta, tzinfo
from functools import lru_cache
from importlib.resources import files
from pathlib import Path
from zoneinfo import ZoneInfo

_HEADER_SIZE = 44
_COUNTS = struct.Struct(">6I")
_TTINFO = struct.Struct(">lBB")


@dataclass(frozen=True, slots=True)
class _ZoneType:
    name: str
    offset: int
    is_dst: bool


@dataclass(frozen=True, slots=True)
class _ZoneMetadata:
    transitions: tuple[int, ...]
    transition_types: tuple[int, ...]
    zone_types: tuple[_ZoneType, ...]


def abbreviation_offset(
    location: tzinfo, name: str, local_time: datetime
) -> int | None:
    """Return the offset Go would associate with a zone abbreviation."""

    key = location.key if isinstance(location, ZoneInfo) else None
    zone_types = _zone_types(key) if key is not None else ()
    pseudo_utc = local_time.replace(tzinfo=UTC)
    for zone_name, offset in zone_types:
        if zone_name != name:
            continue
        instant = (pseudo_utc - timedelta(seconds=offset)).astimezone(location)
        active_offset = int((instant.utcoffset() or timedelta(0)).total_seconds())
        if instant.tzname() == name and active_offset == offset:
            return offset
    for zone_name, offset in zone_types:
        if zone_name == name:
            return offset

    localized = local_time.replace(tzinfo=location)
    if localized.tzname() == name:
        return int((localized.utcoffset() or timedelta(0)).total_seconds())
    return None


def zone_before_first_transition(
    location: tzinfo, unix_seconds: int
) -> tuple[str, int] | None:
    """Return Go's pre-transition zone, or None after the first transition."""

    if not isinstance(location, ZoneInfo):
        return None
    metadata = _zone_metadata(location.key)
    if metadata is None:
        return None
    if metadata.transitions and unix_seconds >= metadata.transitions[0]:
        return None
    zone_index = _first_zone_index(metadata)
    zone_type = metadata.zone_types[zone_index]
    return zone_type.name, zone_type.offset


def transition_bounds(
    location: tzinfo,
    unix_seconds: int,
    *,
    transitions: tuple[int, ...] | None = None,
) -> tuple[int | None, int | None]:
    """Return the recorded TZif transition interval containing an instant."""

    if transitions is None:
        if not isinstance(location, ZoneInfo):
            return None, None
        metadata = _zone_metadata(location.key)
        if metadata is None:
            return None, None
        transitions = metadata.transitions
    if not transitions:
        return None, None
    position = bisect_right(transitions, unix_seconds)
    if position == len(transitions) and isinstance(location, ZoneInfo):
        return _extension_transition_bounds(
            location,
            unix_seconds,
            recorded_start=transitions[-1],
        )
    start = transitions[position - 1] if position else None
    end = transitions[position] if position < len(transitions) else None
    return start, end


def _extension_transition_bounds(
    location: ZoneInfo,
    unix_seconds: int,
    *,
    recorded_start: int,
) -> tuple[int | None, int | None]:
    current = _zone_state(location, unix_seconds)
    step = 6 * 60 * 60
    horizon = 370 * 24 * 60 * 60

    previous = unix_seconds
    start: int | None = None
    while previous > unix_seconds - horizon:
        candidate = max(unix_seconds - horizon, previous - step)
        if _zone_state(location, candidate) != current:
            start = _first_second_with_state(location, candidate, previous, current)
            break
        previous = candidate
    if start is None:
        start = recorded_start

    following = unix_seconds
    end: int | None = None
    while following < unix_seconds + horizon:
        candidate = min(unix_seconds + horizon, following + step)
        if _zone_state(location, candidate) != current:
            end = _first_second_without_state(location, following, candidate, current)
            break
        following = candidate
    return start, end


def _first_second_with_state(
    location: ZoneInfo,
    low: int,
    high: int,
    state: tuple[str, int, bool],
) -> int:
    while low + 1 < high:
        middle = (low + high) // 2
        if _zone_state(location, middle) == state:
            high = middle
        else:
            low = middle
    return high


def _first_second_without_state(
    location: ZoneInfo,
    low: int,
    high: int,
    state: tuple[str, int, bool],
) -> int:
    while low + 1 < high:
        middle = (low + high) // 2
        if _zone_state(location, middle) == state:
            low = middle
        else:
            high = middle
    return high


def _zone_state(location: ZoneInfo, unix_seconds: int) -> tuple[str, int, bool]:
    value = datetime.fromtimestamp(unix_seconds, UTC).astimezone(location)
    offset = int((value.utcoffset() or timedelta(0)).total_seconds())
    return value.tzname() or "UTC", offset, bool(value.dst())


def transitions_from_data(data: bytes) -> tuple[int, ...]:
    """Validate TZif data and return its explicit transition instants."""

    return _parse_zone_metadata(data).transitions


@lru_cache(maxsize=128)
def _zone_types(key: str) -> tuple[tuple[str, int], ...]:
    metadata = _zone_metadata(key)
    if metadata is None:
        return ()
    return tuple((item.name, item.offset) for item in metadata.zone_types)


@lru_cache(maxsize=128)
def _zone_metadata(key: str) -> _ZoneMetadata | None:
    data = _read_zone_data(key)
    if data is None:
        return None
    try:
        return _parse_zone_metadata(data)
    except (IndexError, struct.error, UnicodeDecodeError, ValueError):
        return None


def _read_zone_data(key: str) -> bytes | None:
    if os.path.isabs(key):
        try:
            return Path(key).read_bytes()
        except OSError:
            return None
    for root in zoneinfo.TZPATH:
        try:
            return (Path(root) / key).read_bytes()
        except OSError:
            continue
    try:
        resource = files("tzdata.zoneinfo")
        for component in key.split("/"):
            resource = resource.joinpath(component)
        return resource.read_bytes()
    except (FileNotFoundError, ModuleNotFoundError, OSError):
        return None


def _parse_zone_metadata(data: bytes) -> _ZoneMetadata:
    version, counts = _header(data, 0)
    data_offset = _HEADER_SIZE
    time_size = 4
    if version in {b"2", b"3", b"4"}:
        second_header = data_offset + _block_size(counts, time_size)
        _, counts = _header(data, second_header)
        data_offset = second_header + _HEADER_SIZE
        time_size = 8

    _, _, _, time_count, type_count, character_count = counts
    transition_offset = data_offset
    transition_format = "q" if time_size == 8 else "l"
    transitions = (
        struct.unpack_from(f">{time_count}{transition_format}", data, transition_offset)
        if time_count
        else ()
    )
    index_offset = transition_offset + time_count * time_size
    transition_types = tuple(data[index_offset : index_offset + time_count])
    type_offset = index_offset + time_count
    abbreviation_offset = type_offset + type_count * _TTINFO.size
    abbreviations = data[abbreviation_offset : abbreviation_offset + character_count]
    result: list[_ZoneType] = []
    for index in range(type_count):
        utc_offset, is_dst, name_index = _TTINFO.unpack_from(
            data, type_offset + index * _TTINFO.size
        )
        if name_index >= len(abbreviations):
            raise ValueError("invalid TZif abbreviation index")
        name_end = abbreviations.find(b"\0", name_index)
        if name_end < 0:
            name_end = len(abbreviations)
        result.append(
            _ZoneType(
                abbreviations[name_index:name_end].decode("ascii"),
                utc_offset,
                bool(is_dst),
            )
        )
    if any(index >= len(result) for index in transition_types):
        raise ValueError("invalid TZif transition type")
    return _ZoneMetadata(tuple(transitions), transition_types, tuple(result))


def _first_zone_index(metadata: _ZoneMetadata) -> int:
    if 0 not in metadata.transition_types:
        return 0
    first_index = metadata.transition_types[0]
    if metadata.zone_types[first_index].is_dst:
        for index in range(first_index - 1, -1, -1):
            if not metadata.zone_types[index].is_dst:
                return index
    for index, zone_type in enumerate(metadata.zone_types):
        if not zone_type.is_dst:
            return index
    return 0


def _header(data: bytes, offset: int) -> tuple[bytes, tuple[int, ...]]:
    if data[offset : offset + 4] != b"TZif":
        raise ValueError("invalid TZif header")
    version = data[offset + 4 : offset + 5]
    counts = _COUNTS.unpack_from(data, offset + 20)
    return version, counts


def _block_size(counts: tuple[int, ...], time_size: int) -> int:
    standard_count, utc_count, leap_count, time_count, type_count, char_count = counts
    return (
        time_count * time_size
        + time_count
        + type_count * _TTINFO.size
        + char_count
        + leap_count * (time_size + 4)
        + standard_count
        + utc_count
    )
