"""Owned parser for Go reference-time layouts."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC

from ._civil import civil_from_unix, days_from_civil
from ._layout import _layout_token  # pyright: ignore[reportPrivateUsage]

_MONTHS = (
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
_WEEKDAYS = (
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
)


@dataclass(frozen=True, slots=True)
class ParsedLayout:
    year: int
    month: int
    day: int
    hour: int
    minute: int
    second: int
    nanosecond: int
    zone_name: str | None
    zone_offset: int | None


class LayoutParseFailure(ValueError):
    def __init__(
        self,
        layout_element: str,
        value_element: str,
        message: str = "",
    ) -> None:
        self.layout_element = layout_element
        self.value_element = value_element
        self.message = message
        super().__init__(message or "layout mismatch")


@dataclass(slots=True)
class _Fields:
    year: int = 0
    month: int = 1
    day: int = 1
    hour: int = 0
    minute: int = 0
    second: int = 0
    nanosecond: int = 0
    year_day: int | None = None
    hour12: bool = False
    meridiem: str | None = None
    zone_name: str | None = None
    zone_offset: int | None = None


def parse_layout(layout: str, value: str) -> ParsedLayout:
    pattern, captures, matchers = _compile_layout(layout)
    match = pattern.fullmatch(value)
    if match is None:
        raise _locate_mismatch(value, matchers)

    fields = _Fields()
    for group, token in captures:
        text = match.group(group)
        if text is not None:
            _apply(fields, token, text)
    _finish(fields)
    return ParsedLayout(
        fields.year,
        fields.month,
        fields.day,
        fields.hour,
        fields.minute,
        fields.second,
        fields.nanosecond,
        fields.zone_name,
        fields.zone_offset,
    )


def _compile_layout(
    layout: str,
) -> tuple[
    re.Pattern[str],
    list[tuple[str, str]],
    list[tuple[str, str]],
]:
    pieces: list[str] = []
    captures: list[tuple[str, str]] = []
    matchers: list[tuple[str, str]] = []
    index = 0
    capture_index = 0
    while index < len(layout):
        fraction = re.match(r"[.,]([09]+)(?!\d)", layout[index:])
        if fraction is not None:
            token = fraction.group(0)
            group = f"v{capture_index}"
            capture_index += 1
            digits = len(fraction.group(1))
            if fraction.group(1)[0] == "9":
                token_pattern = r"[.,]\d+"
                pieces.append(rf"(?P<{group}>{token_pattern})?")
                matchers.append((rf"(?:{token_pattern})?", token))
            else:
                token_pattern = rf"[.,]\d{{{digits}}}"
                pieces.append(rf"(?P<{group}>{token_pattern})")
                matchers.append((token_pattern, token))
            captures.append((group, token))
            index += len(token)
            continue

        token = _layout_token(layout, index)
        if token is not None:
            group = f"v{capture_index}"
            capture_index += 1
            token_pattern = _token_pattern(token)
            pieces.append(rf"(?P<{group}>{token_pattern})")
            matchers.append((token_pattern, token))
            captures.append((group, token))
            index += len(token)
            if token in {"05", "5"} and not _fraction_follows(layout, index):
                fraction_group = f"v{capture_index}"
                capture_index += 1
                pieces.append(rf"(?P<{fraction_group}>[.,]\d+)?")
                captures.append((fraction_group, ".999999999"))
                matchers.append((r"(?:[.,]\d+)?", ".999999999"))
            continue

        if layout[index].isspace():
            while index < len(layout) and layout[index].isspace():
                index += 1
            pieces.append(r"\s+")
            matchers.append((r"\s+", " "))
            continue
        literal = layout[index]
        pieces.append(re.escape(literal))
        matchers.append((re.escape(literal), literal))
        index += 1
    return re.compile("".join(pieces)), captures, matchers


def _locate_mismatch(value: str, matchers: list[tuple[str, str]]) -> LayoutParseFailure:
    position = 0
    for pattern, layout_element in matchers:
        match = re.compile(pattern).match(value, position)
        if match is None:
            return LayoutParseFailure(layout_element, value[position:])
        position = match.end()
    if position < len(value):
        extra = value[position:]
        escaped = extra.replace("\\", "\\\\").replace('"', '\\"')
        return LayoutParseFailure("", extra, f': extra text: "{escaped}"')
    return LayoutParseFailure("", "")


def _fraction_follows(layout: str, index: int) -> bool:
    return re.match(r"[.,][09]+(?!\d)", layout[index:]) is not None


def _token_pattern(token: str) -> str:
    short_months = "|".join(month[:3] for month in _MONTHS)
    short_weekdays = "|".join(day[:3] for day in _WEEKDAYS)
    patterns = {
        "January": rf"(?i:{'|'.join(_MONTHS)})",
        "Jan": rf"(?i:{short_months})",
        "Monday": rf"(?i:{'|'.join(_WEEKDAYS)})",
        "Mon": rf"(?i:{short_weekdays})",
        "2006": r"\d{4}",
        "_2006": r"_\d{4}",
        "06": r"\d{2}",
        "01": r"\d{2}",
        "1": r"\d{1,2}",
        "02": r"\d{2}",
        "_2": r" {0,2}\d{1,2}",
        "2": r"\d{1,2}",
        "__2": r" {0,2}\d{1,3}",
        "002": r"\d{3}",
        "15": r"\d{1,2}",
        "03": r"\d{2}",
        "3": r"\d{1,2}",
        "04": r"\d{2}",
        "4": r"\d{1,2}",
        "05": r"\d{2}",
        "5": r"\d{1,2}",
        "PM": r"AM|PM",
        "pm": r"am|pm",
        "MST": (
            r"(?:UTC|GMT(?:[+-]\d+)?|ChST|MeST|WITA|"
            r"[A-Z]{3}|[A-Z]{2,4}T|[+-](?:[1-9]|0[1-9]|1\d|2[0-3]))"
        ),
        "-07": r"[+-]\d{2}",
        "Z07": r"Z|[+-]\d{2}",
        "-0700": r"[+-]\d{4}",
        "Z0700": r"Z|[+-]\d{4}",
        "-07:00": r"[+-]\d{2}:\d{2}",
        "Z07:00": r"Z|[+-]\d{2}:\d{2}",
        "-070000": r"[+-]\d{6}",
        "Z070000": r"Z|[+-]\d{6}",
        "-07:00:00": r"[+-]\d{2}:\d{2}:\d{2}",
        "Z07:00:00": r"Z|[+-]\d{2}:\d{2}:\d{2}",
    }
    return patterns[token]


def _apply(fields: _Fields, token: str, text: str) -> None:
    if token == "2006":
        fields.year = int(text)
    elif token == "_2006":
        fields.year = int(text[1:])
    elif token == "06":
        short_year = int(text)
        fields.year = 1900 + short_year if short_year >= 69 else 2000 + short_year
    elif token in {"January", "Jan"}:
        lowered = text.lower()
        fields.month = next(
            index
            for index, month in enumerate(_MONTHS, 1)
            if month.lower().startswith(lowered)
        )
    elif token in {"01", "1"}:
        fields.month = int(text)
    elif token in {"02", "_2", "2"}:
        fields.day = int(text)
    elif token in {"002", "__2"}:
        fields.year_day = int(text)
    elif token == "15":
        fields.hour = int(text)
    elif token in {"03", "3"}:
        fields.hour = int(text)
        fields.hour12 = True
    elif token in {"04", "4"}:
        fields.minute = int(text)
    elif token in {"05", "5"}:
        fields.second = int(text)
    elif token in {"PM", "pm"}:
        fields.meridiem = text.lower()
    elif token == "MST":
        fields.zone_name = text
    elif token.startswith(("-07", "Z07")):
        fields.zone_offset = _zone_offset(text)
        fields.zone_name = "UTC" if text == "Z" else None
    elif token.startswith((".", ",")) and text:
        digits = text[1:]
        fields.nanosecond = int(digits[:9].ljust(9, "0"))


def _finish(fields: _Fields) -> None:
    if fields.hour12:
        if not 1 <= fields.hour <= 12:
            raise LayoutParseFailure("hour", str(fields.hour), ": hour out of range")
        if fields.meridiem == "pm" and fields.hour < 12:
            fields.hour += 12
        elif fields.meridiem == "am" and fields.hour == 12:
            fields.hour = 0
    if not 1 <= fields.month <= 12:
        raise LayoutParseFailure("month", str(fields.month), ": month out of range")
    if fields.hour >= 24:
        raise LayoutParseFailure("hour", str(fields.hour), ": hour out of range")
    if fields.minute >= 60:
        raise LayoutParseFailure("minute", str(fields.minute), ": minute out of range")
    if fields.second >= 60:
        raise LayoutParseFailure("second", str(fields.second), ": second out of range")
    if fields.year_day is not None:
        maximum = 366 if _leap(fields.year) else 365
        if not 1 <= fields.year_day <= maximum:
            raise LayoutParseFailure("", "", ": day-of-year out of range")
        civil = civil_from_unix(
            (days_from_civil(fields.year, 1, 1) + fields.year_day - 1) * 86_400,
            0,
            UTC,
        )
        if fields.month != 1 and fields.month != civil.month:
            raise LayoutParseFailure("", "", ": day-of-year does not match month")
        if fields.day != 1 and fields.day != civil.day:
            raise LayoutParseFailure("", "", ": day-of-year does not match day")
        fields.month, fields.day = civil.month, civil.day
    if not 1 <= fields.day <= _days_in_month(fields.year, fields.month):
        raise LayoutParseFailure("", "", ": day out of range")


def _zone_offset(value: str) -> int:
    if value == "Z":
        return 0
    sign = -1 if value[0] == "-" else 1
    digits = value[1:].replace(":", "")
    hour = int(digits[:2])
    minute = int(digits[2:4]) if len(digits) >= 4 else 0
    second = int(digits[4:6]) if len(digits) >= 6 else 0
    if hour > 24:
        raise LayoutParseFailure(value, value, ": time zone offset hour out of range")
    if minute > 60:
        raise LayoutParseFailure(value, value, ": time zone offset minute out of range")
    if second > 60:
        raise LayoutParseFailure(value, value, ": time zone offset second out of range")
    return sign * ((hour * 60 + minute) * 60 + second)


def _days_in_month(year: int, month: int) -> int:
    if month == 2:
        return 29 if _leap(year) else 28
    return 30 if month in {4, 6, 9, 11} else 31


def _leap(year: int) -> bool:
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)
