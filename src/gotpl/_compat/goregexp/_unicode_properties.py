"""Go 1.27 Unicode property lookup for the RE2 compatibility layer."""

from __future__ import annotations

from functools import lru_cache

from ._unicode_tables import CATEGORY_ALIASES, PROPERTY_RANGES, UNICODE_VERSION

_MAX_RUNE = 0x10FFFF


@lru_cache(maxsize=256)
def property_class_contents(name: str, *, negate: bool = False) -> str:
    """Return a Python character-class body for a Go Unicode property."""

    intervals = _property_intervals(name)
    if negate:
        intervals = _complement(intervals)
    return "".join(_format_interval(lower, upper) for lower, upper in intervals)


@lru_cache(maxsize=256)
def _property_intervals(name: str) -> tuple[tuple[int, int], ...]:
    canonical = _canonical_name(name)
    if canonical == "Any":
        return ((0, _MAX_RUNE),)
    if canonical == "Assigned":
        return _complement(_table_intervals("Cn"))
    if canonical == "Ascii":
        return ((0, 0x7F),)
    if canonical == "Lc":
        canonical = "LC"
    canonical = CATEGORY_ALIASES.get(canonical, canonical)
    actual = (
        canonical
        if canonical in PROPERTY_RANGES
        else _CANONICAL_PROPERTY_NAMES.get(canonical)
    )
    if actual is None:
        raise ValueError(f"invalid Unicode class: {name}")
    return _table_intervals(actual)


@lru_cache(maxsize=256)
def _table_intervals(name: str) -> tuple[tuple[int, int], ...]:
    intervals: list[tuple[int, int]] = []
    for lower, upper, stride in PROPERTY_RANGES[name]:
        if stride == 1:
            intervals.append((lower, upper))
        else:
            intervals.extend(
                (value, value) for value in range(lower, upper + 1, stride)
            )
    return _merge(intervals)


def _merge(intervals: list[tuple[int, int]]) -> tuple[tuple[int, int], ...]:
    if not intervals:
        return ()
    intervals.sort()
    merged: list[tuple[int, int]] = [intervals[0]]
    for lower, upper in intervals[1:]:
        previous_lower, previous_upper = merged[-1]
        if lower <= previous_upper + 1:
            merged[-1] = (previous_lower, max(previous_upper, upper))
        else:
            merged.append((lower, upper))
    return tuple(merged)


def _complement(
    intervals: tuple[tuple[int, int], ...],
) -> tuple[tuple[int, int], ...]:
    result: list[tuple[int, int]] = []
    beginning = 0
    for lower, upper in intervals:
        if beginning < lower:
            result.append((beginning, lower - 1))
        beginning = upper + 1
    if beginning <= _MAX_RUNE:
        result.append((beginning, _MAX_RUNE))
    return tuple(result)


def _format_interval(lower: int, upper: int) -> str:
    first = _escape_codepoint(lower)
    return first if lower == upper else f"{first}-{_escape_codepoint(upper)}"


def _escape_codepoint(value: int) -> str:
    return f"\\u{value:04x}" if value <= 0xFFFF else f"\\U{value:08x}"


def _canonical_name(name: str) -> str:
    result: list[str] = []
    for character in name:
        if character in {"_", "-", " "}:
            continue
        result.append(character.upper() if not result else character.lower())
    return "".join(result)


_CANONICAL_PROPERTY_NAMES = {_canonical_name(name): name for name in PROPERTY_RANGES}


__all__ = ["UNICODE_VERSION", "property_class_contents"]
