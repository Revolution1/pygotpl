"""Go reference-time layout formatting and parsing primitives."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal, TypeAlias

from ._civil import CivilTime

LAYOUT = "01/02 03:04:05PM '06 -0700"
ANSIC = "Mon Jan _2 15:04:05 2006"
UNIX_DATE = "Mon Jan _2 15:04:05 MST 2006"
RUBY_DATE = "Mon Jan 02 15:04:05 -0700 2006"
RFC822 = "02 Jan 06 15:04 MST"
RFC822Z = "02 Jan 06 15:04 -0700"
RFC850 = "Monday, 02-Jan-06 15:04:05 MST"
RFC1123 = "Mon, 02 Jan 2006 15:04:05 MST"
RFC1123Z = "Mon, 02 Jan 2006 15:04:05 -0700"
RFC3339 = "2006-01-02T15:04:05Z07:00"
RFC3339_NANO = "2006-01-02T15:04:05.999999999Z07:00"
KITCHEN = "3:04PM"
STAMP = "Jan _2 15:04:05"
STAMP_MILLI = "Jan _2 15:04:05.000"
STAMP_MICRO = "Jan _2 15:04:05.000000"
STAMP_NANO = "Jan _2 15:04:05.000000000"
DATE_TIME = "2006-01-02 15:04:05"
DATE_ONLY = "2006-01-02"
TIME_ONLY = "15:04:05"

_TOKENS = (
    "January",
    "Monday",
    "Z07:00:00",
    "-07:00:00",
    "Z070000",
    "-070000",
    "Z07:00",
    "-07:00",
    "Z0700",
    "-0700",
    "2006",
    "_2006",
    "__2",
    "002",
    "MST",
    "Jan",
    "Mon",
    "Z07",
    "-07",
    "PM",
    "pm",
    "06",
    "01",
    "02",
    "_2",
    "15",
    "03",
    "04",
    "05",
    "1",
    "2",
    "3",
    "4",
    "5",
)


_LayoutPart: TypeAlias = tuple[Literal["literal", "token", "fraction"], str]


def format_civil(civil: CivilTime, layout: str) -> str:
    output: list[str] = []
    for kind, value in _compile_layout(layout):
        if kind == "fraction":
            separator = value[0]
            digits = value[1:]
            nanos = f"{civil.nanosecond:09d}"[: len(digits)]
            if digits[0] == "9":
                nanos = nanos.rstrip("0")
                output.append(separator + nanos if nanos else "")
            else:
                output.append(separator + nanos)
        elif kind == "token":
            output.append(_format_token(civil, value))
        else:
            output.append(value)
    return "".join(output)


@lru_cache(maxsize=512)
def _compile_layout(layout: str) -> tuple[_LayoutPart, ...]:
    parts: list[_LayoutPart] = []
    literal: list[str] = []

    def flush_literal() -> None:
        if literal:
            parts.append(("literal", "".join(literal)))
            literal.clear()

    index = 0
    while index < len(layout):
        fraction_end = _fraction_end(layout, index)
        if fraction_end is not None:
            flush_literal()
            parts.append(("fraction", layout[index:fraction_end]))
            index = fraction_end
            continue
        token = _layout_token(layout, index)
        if token is None:
            literal.append(layout[index])
            index += 1
        else:
            flush_literal()
            parts.append(("token", token))
            index += len(token)
    flush_literal()
    return tuple(parts)


def _fraction_end(layout: str, index: int) -> int | None:
    if layout[index] not in ".," or index + 1 == len(layout):
        return None
    digit = layout[index + 1]
    if digit not in "09":
        return None
    end = index + 2
    while end < len(layout) and layout[end] == digit:
        end += 1
    if end < len(layout) and layout[end].isdigit():
        return None
    return end


def _format_token(value: CivilTime, token: str) -> str:
    month_names = (
        "",
        "January",
        "February",
        "March",
        "April",
        "May",
        "June",
        "July",
        "August",
        "September",
        "October",
        "November",
        "December",
    )
    weekday_names = (
        "Sunday",
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
    )
    if token == "January":
        return month_names[value.month]
    if token == "Monday":
        return weekday_names[value.weekday]
    if token == "2006":
        return _format_signed_decimal(value.year, 4)
    if token == "_2006":
        return f"_{_format_signed_decimal(value.year, 4)}"
    if token == "__2":
        return f"{value.year_day:3d}"
    if token == "002":
        return f"{value.year_day:03d}"
    if token == "MST":
        return value.zone_name
    if token == "Jan":
        return month_names[value.month][:3]
    if token == "Mon":
        return weekday_names[value.weekday][:3]
    if token == "PM":
        return "PM" if value.hour >= 12 else "AM"
    if token == "pm":
        return "pm" if value.hour >= 12 else "am"
    if token == "06":
        return f"{abs(value.year) % 100:02d}"
    if token == "01":
        return f"{value.month:02d}"
    if token == "02":
        return f"{value.day:02d}"
    if token == "_2":
        return f"{value.day:2d}"
    if token == "15":
        return f"{value.hour:02d}"
    if token == "03":
        return f"{value.hour % 12 or 12:02d}"
    if token == "04":
        return f"{value.minute:02d}"
    if token == "05":
        return f"{value.second:02d}"
    if token == "1":
        return str(value.month)
    if token == "2":
        return str(value.day)
    if token == "3":
        return str(value.hour % 12 or 12)
    if token == "4":
        return str(value.minute)
    if token == "5":
        return str(value.second)

    offset_seconds = value.offset_seconds
    sign = "+" if offset_seconds >= 0 else "-"
    zone_hour, remainder = divmod(abs(offset_seconds), 3_600)
    zone_minute, zone_second = divmod(remainder, 60)
    values = {
        "-0700": f"{sign}{zone_hour:02d}{zone_minute:02d}",
        "-07:00": f"{sign}{zone_hour:02d}:{zone_minute:02d}",
        "-07": f"{sign}{zone_hour:02d}",
        "-070000": f"{sign}{zone_hour:02d}{zone_minute:02d}{zone_second:02d}",
        "-07:00:00": f"{sign}{zone_hour:02d}:{zone_minute:02d}:{zone_second:02d}",
    }
    if token.startswith("Z"):
        return "Z" if offset_seconds == 0 else values["-" + token[1:]]
    return values[token]


def _format_signed_decimal(value: int, width: int) -> str:
    sign = "-" if value < 0 else ""
    return f"{sign}{abs(value):0{width}d}"


def _layout_token(layout: str, index: int) -> str | None:
    for token in _TOKENS:
        if not layout.startswith(token, index):
            continue
        end = index + len(token)
        if token in {"Jan", "Mon"} and end < len(layout):
            following = layout[end]
            if "a" <= following <= "z":
                continue
        return token
    return None
