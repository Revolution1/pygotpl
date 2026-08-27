import pytest

from gotime.go import (
    ANSIC,
    DATE_ONLY,
    DATE_TIME,
    KITCHEN,
    LAYOUT,
    RFC3339,
    RFC3339_NANO,
    STAMP_NANO,
    TIME_ONLY,
    UTC,
    Location,
    ParseError,
    Time,
)


def test_layout_constants_match_go_127() -> None:
    assert LAYOUT == "01/02 03:04:05PM '06 -0700"
    assert ANSIC == "Mon Jan _2 15:04:05 2006"
    assert RFC3339 == "2006-01-02T15:04:05Z07:00"
    assert RFC3339_NANO == "2006-01-02T15:04:05.999999999Z07:00"
    assert KITCHEN == "3:04PM"
    assert STAMP_NANO == "Jan _2 15:04:05.000000000"
    assert DATE_TIME == "2006-01-02 15:04:05"
    assert DATE_ONLY == "2006-01-02"
    assert TIME_ONLY == "15:04:05"


def test_format_covers_calendar_fraction_and_zone_tokens() -> None:
    value = Time.from_unix(1_720_530_245, 123_456_789, location=UTC).in_location(
        Location.load("Asia/Kolkata")
    )

    assert (
        value.format("Monday January 2006-01-02 15:04:05.000000000 MST Z07:00")
        == "Tuesday July 2024-07-09 18:34:05.123456789 IST +05:30"
    )
    assert value.format(RFC3339_NANO) == "2024-07-09T18:34:05.123456789+05:30"


def test_parse_and_parse_in_location_preserve_nanoseconds() -> None:
    utc = Time.parse(
        "2006-01-02 15:04:05.999999999 -0700",
        "2024-07-09 13:04:05.123456789 +0000",
    )
    local = Time.parse_in_location(
        DATE_TIME,
        "2024-07-09 13:04:05",
        Location.load("America/New_York"),
    )

    assert (utc.unix_seconds, utc.nanosecond, utc.zone()) == (
        1_720_530_245,
        123_456_789,
        ("UTC", 0),
    )
    assert local.format("MST -0700") == "EDT -0400"
    assert local.utc().clock() == (17, 4, 5)


_UPSTREAM_FORMAT_CASES = [
    (ANSIC, "Wed Feb  4 21:00:57 2009"),
    ("Mon Jan _2 15:04:05 MST 2006", "Wed Feb  4 21:00:57 PST 2009"),
    ("Mon Jan 02 15:04:05 -0700 2006", "Wed Feb 04 21:00:57 -0800 2009"),
    ("02 Jan 06 15:04 MST", "04 Feb 09 21:00 PST"),
    ("Monday, 02-Jan-06 15:04:05 MST", "Wednesday, 04-Feb-09 21:00:57 PST"),
    ("Mon, 02 Jan 2006 15:04:05 MST", "Wed, 04 Feb 2009 21:00:57 PST"),
    ("Mon, 02 Jan 2006 15:04:05 -0700", "Wed, 04 Feb 2009 21:00:57 -0800"),
    (RFC3339, "2009-02-04T21:00:57-08:00"),
    (RFC3339_NANO, "2009-02-04T21:00:57.0123456-08:00"),
    (KITCHEN, "9:00PM"),
    ("3pm", "9pm"),
    ("3PM", "9PM"),
    ("06 01 02", "09 02 04"),
    ("Hi Janet, the Month is January", "Hi Janet, the Month is February"),
    ("Jan _2 15:04:05", "Feb  4 21:00:57"),
    ("Jan _2 15:04:05.000", "Feb  4 21:00:57.012"),
    ("Jan _2 15:04:05.000000", "Feb  4 21:00:57.012345"),
    ("Jan _2 15:04:05.000000000", "Feb  4 21:00:57.012345600"),
    (DATE_TIME, "2009-02-04 21:00:57"),
    (DATE_ONLY, "2009-02-04"),
    (TIME_ONLY, "21:00:57"),
    ("Jan  2 002 __2 2", "Feb  4 035  35 4"),
    ("2006 6 06 _6 __6 ___6", "2009 6 09 _6 __6 ___6"),
    ("Jan January 1 01 _1", "Feb February 2 02 _2"),
    ("2 02 _2 __2", "4 04  4  35"),
    ("Mon Monday", "Wed Wednesday"),
    ("15 3 03 _3", "21 9 09 _9"),
    ("4 04 _4", "0 00 _0"),
    ("5 05 _5", "57 57 _57"),
]


@pytest.mark.parametrize(("layout", "expected"), _UPSTREAM_FORMAT_CASES)
def test_upstream_format_matrix(layout: str, expected: str) -> None:
    value = Time.from_unix(
        1_233_810_057,
        12_345_600,
        location=Location.fixed("PST", -8 * 60 * 60),
    )

    assert value.format(layout) == expected


def test_append_format_preserves_prefix() -> None:
    value = Time.from_components(2024, 1, 2, 3, 4, 5, 0, UTC)

    assert value.append_format(b"prefix:", DATE_TIME) == b"prefix:2024-01-02 03:04:05"


def test_go_string_uses_go_byte_quoting_for_location_names() -> None:
    value = Time.from_components(
        2009,
        2,
        5,
        5,
        0,
        57,
        12_345_600,
        Location.fixed("Non-ASCII character ⏰", 3 * 60 * 60),
    )

    assert value.go_string() == (
        "time.Date(2009, time.February, 5, 5, 0, 57, 12345600, "
        'time.Location("Non-ASCII character \\xe2\\x8f\\xb0"))'
    )


def test_parse_error_has_go_fields_and_error_rendering() -> None:
    error = ParseError(
        ANSIC,
        "Thu Feb  4 21:00:57 @2010",
        "2006",
        "@2010",
    )

    assert error.layout == ANSIC
    assert error.value == "Thu Feb  4 21:00:57 @2010"
    assert error.layout_element == "2006"
    assert error.value_element == "@2010"
    assert str(error).endswith('cannot parse "@2010" as "2006"')


def test_parse_failures_use_structured_parse_error() -> None:
    with pytest.raises(ParseError) as captured:
        Time.parse(ANSIC, "Thu Feb  4 21:61:57 2010")

    assert captured.value.layout == ANSIC
    assert captured.value.value == "Thu Feb  4 21:61:57 2010"
    assert "minute" in str(captured.value).lower()


_UPSTREAM_PARSE_CASES = [
    (ANSIC, "Thu Feb  4 21:00:57 2010", (2010, 2, 4, 21, 0, 57, 0)),
    (
        "Mon Jan _2 15:04:05 MST 2006",
        "Thu Feb  4 21:00:57 PST 2010",
        (2010, 2, 4, 21, 0, 57, 0),
    ),
    (
        "Mon Jan 02 15:04:05 -0700 2006",
        "Thu Feb 04 21:00:57 -0800 2010",
        (2010, 2, 4, 21, 0, 57, 0),
    ),
    (
        "Monday, 02-Jan-06 15:04:05 MST",
        "Thursday, 04-Feb-10 21:00:57 PST",
        (2010, 2, 4, 21, 0, 57, 0),
    ),
    (
        "Mon, 02 Jan 2006 15:04:05 MST",
        "Thu, 04 Feb 2010 22:00:57 PDT",
        (2010, 2, 4, 22, 0, 57, 0),
    ),
    (
        RFC3339,
        "2010-02-04T21:00:57.012345678-08:00",
        (2010, 2, 4, 21, 0, 57, 12_345_678),
    ),
    (ANSIC, "Thu Feb  4 21:00:57.0 2010", (2010, 2, 4, 21, 0, 57, 0)),
    (ANSIC, "Thu      Feb     4     21:00:57     2010", (2010, 2, 4, 21, 0, 57, 0)),
    (ANSIC, "thu feb 4 21:00:57 2010", (2010, 2, 4, 21, 0, 57, 0)),
    (
        "Mon Jan _2 15:04:05.000 2006",
        "Thu Feb  4 21:00:57.012 2010",
        (2010, 2, 4, 21, 0, 57, 12_000_000),
    ),
    (
        "Mon Jan _2 15:04:05,000000 2006",
        "Thu Feb  4 21:00:57.012345 2010",
        (2010, 2, 4, 21, 0, 57, 12_345_000),
    ),
    (
        "Mon Jan _2 15:04:05.000000000 2006",
        "Thu Feb  4 21:00:57.012345678 2010",
        (2010, 2, 4, 21, 0, 57, 12_345_678),
    ),
    (
        "2006-01-02 15:04:05.9999 -0700 MST",
        "2010-02-04 21:00:57 -0800 PST",
        (2010, 2, 4, 21, 0, 57, 0),
    ),
    (
        "2006-01-02 15:04:05.9999 -0700 MST",
        "2010-02-04 21:00:57.012345678 -0800 PST",
        (2010, 2, 4, 21, 0, 57, 12_345_678),
    ),
    (STAMP_NANO, "Feb  4 21:00:57.012345678", (0, 2, 4, 21, 0, 57, 12_345_678)),
    ("2006-002 15:04:05", "2010-035 21:00:57", (2010, 2, 4, 21, 0, 57, 0)),
    ("200600201 15:04:05", "201003502 21:00:57", (2010, 2, 4, 21, 0, 57, 0)),
    ("2006-01-02T15:04:05Z07", "2010-02-04T21:00:57+08", (2010, 2, 4, 21, 0, 57, 0)),
    (
        "2006-01-02T15:04:05Z0700",
        "2010-02-04T21:00:57-0800",
        (2010, 2, 4, 21, 0, 57, 0),
    ),
    (
        "2006-01-02T15:04:05Z070000",
        "2010-02-04T21:00:57+080030",
        (2010, 2, 4, 21, 0, 57, 0),
    ),
    (
        "2006-01-02T15:04:05Z07:00:00",
        "2010-02-04T21:00:57-08:00:30",
        (2010, 2, 4, 21, 0, 57, 0),
    ),
]


@pytest.mark.parametrize(("layout", "text", "expected"), _UPSTREAM_PARSE_CASES)
def test_upstream_parse_matrix(
    layout: str,
    text: str,
    expected: tuple[int, int, int, int, int, int, int],
) -> None:
    value = Time.parse(layout, text)
    civil = value.civil()

    assert (
        civil.year,
        civil.month,
        civil.day,
        civil.hour,
        civil.minute,
        civil.second,
        civil.nanosecond,
    ) == expected


_UPSTREAM_PARSE_ERROR_CASES = [
    (ANSIC, "Feb  4 21:00:60 2010", 'cannot parse "Feb  4 21:00:60 2010" as'),
    (ANSIC, "Thu Feb  4 21:00:57 @2010", 'cannot parse "@2010" as "2006"'),
    (ANSIC, "Thu Feb  4 21:00:60 2010", "second out of range"),
    (ANSIC, "Thu Feb  4 21:61:57 2010", "minute out of range"),
    (ANSIC, "Thu Feb  4 24:00:60 2010", "hour out of range"),
    (STAMP_NANO, "Dec  7 11:22:01.000000", "cannot parse"),
    (STAMP_NANO, "Dec  7 11:22:01.0000000000", 'extra text: "0"'),
    (RFC3339, "2010-02-04T21:00:67.012345678-08:00", "second out of range"),
    ("Jan _2 002 2006", "Feb  4 034 2006", "day-of-year does not match day"),
    ("Jan _2 002 2006", "Feb  4 004 2006", "day-of-year does not match month"),
    ("2006-01-02", "22-10-25", "cannot parse"),
    ("06-01-02", "a2-10-25", "cannot parse"),
    ("03:04PM", "12:03pM", "cannot parse"),
    ("-07", "-25", "time zone offset hour out of range"),
    ("-07:00", "+25:00", "time zone offset hour out of range"),
    ("-07:00", "-23:61", "time zone offset minute out of range"),
    ("-07:00:00", "+23:59:61", "time zone offset second out of range"),
    ("Z07", "-25", "time zone offset hour out of range"),
    ("Z07:00", "+25:00", "time zone offset hour out of range"),
    ("Z07:00", "-23:61", "time zone offset minute out of range"),
    ("Z07:00:00", "+23:59:61", "time zone offset second out of range"),
]


@pytest.mark.parametrize(
    ("layout", "text", "expected"),
    _UPSTREAM_PARSE_ERROR_CASES,
)
def test_upstream_parse_error_matrix(layout: str, text: str, expected: str) -> None:
    with pytest.raises(ParseError) as captured:
        Time.parse(layout, text)

    assert expected in str(captured.value)


def test_remaining_layout_field_and_range_paths() -> None:
    assert Time.parse("_2006", "_2024").year == 2024
    assert Time.parse("03:04PM", "12:03AM").hour == 0
    assert Time.parse("03:04pm", "01:03pm").hour == 13
    assert Time.parse("Z07", "Z").zone() == ("UTC", 0)

    for layout, text, message in (
        ("01", "13", "month out of range"),
        ("2006-01-02", "2024-02-30", "day out of range"),
        ("2006-002", "2023-366", "day-of-year out of range"),
        ("03", "00", "hour out of range"),
    ):
        with pytest.raises(ParseError, match=message):
            Time.parse(layout, text)


@pytest.mark.parametrize(
    "year",
    [
        -100_001,
        -100_000,
        -99_999,
        -10_001,
        -10_000,
        -9_999,
        -1_001,
        -1_000,
        -999,
        -101,
        -100,
        -99,
        -11,
        -10,
        -9,
        -1,
        0,
        1,
        9,
        10,
        11,
        99,
        100,
        101,
        999,
        1_000,
        1_001,
        9_999,
        10_000,
        10_001,
        99_999,
        100_000,
        100_001,
    ],
)
def test_upstream_short_year_format_matrix(year: int) -> None:
    value = Time.from_components(year, 1, 1, 0, 0, 0, 0, UTC)
    expected_year = f"-{abs(year):04d}" if year < 0 else f"{year:04d}"

    assert value.format("2006.01.02") == f"{expected_year}.01.01"


@pytest.mark.parametrize(
    ("text", "valid"),
    [
        ("Thu Jan 99 21:00:57 2010", False),
        ("Thu Jan 31 21:00:57 2010", True),
        ("Thu Jan 32 21:00:57 2010", False),
        ("Thu Feb 28 21:00:57 2012", True),
        ("Thu Feb 29 21:00:57 2012", True),
        ("Thu Feb 29 21:00:57 2010", False),
        ("Thu Apr 30 21:00:57 2010", True),
        ("Thu Apr 31 21:00:57 2010", False),
        ("Thu Dec 31 21:00:57 2010", True),
        ("Thu Dec 32 21:00:57 2010", False),
        ("Thu Dec 00 21:00:57 2010", False),
    ],
)
def test_upstream_day_range_matrix(text: str, valid: bool) -> None:
    if valid:
        Time.parse(ANSIC, text)
    else:
        with pytest.raises(ParseError, match="day out of range"):
            Time.parse(ANSIC, text)


@pytest.mark.parametrize(
    ("layout", "text", "expected_zone"),
    [
        ("2006-01-02T15:04:05Z07", "2010-02-04T21:00:57Z", ("UTC", 0)),
        ("2006-01-02T15:04:05Z0700", "2010-02-04T21:00:57+0800", ("", 28_800)),
        ("2006-01-02T15:04:05Z07:00", "2010-02-04T21:00:57-08:00", ("", -28_800)),
        ("2006-01-02T15:04:05Z070000", "2010-02-04T21:00:57+080030", ("", 28_830)),
        (
            "2006-01-02T15:04:05Z07:00:00",
            "2010-02-04T21:00:57-08:00:30",
            ("", -28_830),
        ),
    ],
)
def test_upstream_numeric_zone_matrix(
    layout: str, text: str, expected_zone: tuple[str, int]
) -> None:
    assert Time.parse(layout, text).zone() == expected_zone


def test_parse_in_location_reuses_matching_zone_offset() -> None:
    new_york = Location.load("America/New_York")
    value = Time.parse_in_location(
        "2006-01-02 15:04:05 -0700",
        "2024-07-09 13:04:05 -0400",
        new_york,
    )

    assert value.location is new_york
    assert value.zone() == ("EDT", -14_400)
