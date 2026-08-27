from __future__ import annotations

from io import StringIO

import pytest

import gotpl
import gotpl.funcs.sprig as sprig

from .support import ExpectedResult, TemplateRequest, run_go_oracle

LOCAL_ZONE_REQUEST: TemplateRequest = {
    "engine": "text",
    "name": "date-local-zone",
    "template": (
        '{{$winter := mustToDate "2006-01-02 15:04" "2024-01-15 12:00"}}'
        '{{$summer := mustToDate "2006-01-02 15:04" "2024-07-15 12:00"}}'
        '{{$beforeDST := mustToDate "2006-01-02 15:04" "2024-03-10 01:30"}}'
        '{{date "MST -0700" $winter}}|{{date "MST -0700" $summer}}|'
        '{{date "2006-01-02 15:04 MST -0700" '
        '(mustDateModify "1h" $beforeDST)}}'
    ),
    "data": None,
    "function_profile": "sprig",
}

ZONE_ABBREVIATION_REQUEST: TemplateRequest = {
    "engine": "text",
    "name": "date-zone-abbreviations",
    "template": (
        '{{$layout := "2006-01-02 15:04 MST"}}'
        '{{$output := "2006-01-02 15:04:05 MST -0700"}}'
        '{{dateInZone $output (mustToDate $layout "2024-01-15 12:00 EST") '
        '"UTC"}}|'
        '{{dateInZone $output (mustToDate $layout "2024-01-15 12:00 EDT") '
        '"UTC"}}|'
        '{{dateInZone $output (mustToDate $layout "2024-01-15 12:00 XYZ") '
        '"UTC"}}|'
        '{{dateInZone $output (mustToDate $layout "2024-01-15 12:00 GMT+3") '
        '"UTC"}}|'
        '{{dateInZone $output (mustToDate $layout "2024-01-15 12:00 ChST") '
        '"UTC"}}|'
        '{{dateInZone $output (mustToDate $layout "2024-01-15 12:00 +03") '
        '"UTC"}}'
    ),
    "data": None,
    "function_profile": "sprig",
}


@pytest.mark.parametrize(
    ("timezone", "expected_output"),
    [
        (
            "America/New_York",
            "EST -0500|EDT -0400|2024-03-10 03:30 EDT -0400",
        ),
        (
            ":America/New_York",
            "EST -0500|EDT -0400|2024-03-10 03:30 EDT -0400",
        ),
        ("", "UTC +0000|UTC +0000|2024-03-10 02:30 UTC +0000"),
        ("Not/AZone", "UTC +0000|UTC +0000|2024-03-10 02:30 UTC +0000"),
    ],
)
def test_local_timezone_matches_go_tz_environment(
    monkeypatch: pytest.MonkeyPatch,
    timezone: str,
    expected_output: str,
) -> None:
    monkeypatch.setenv("TZ", timezone)
    expected: ExpectedResult = {"output": expected_output, "error": None}

    assert run_go_oracle(LOCAL_ZONE_REQUEST) == expected

    output = StringIO()
    gotpl.render_to(
        LOCAL_ZONE_REQUEST["template"],
        output,
        name=LOCAL_ZONE_REQUEST["name"],
        functions=sprig.text_func_map(),
    )
    assert {"output": output.getvalue(), "error": None} == expected


def test_zone_abbreviation_lookup_matches_go_local_location(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TZ", "America/New_York")
    expected: ExpectedResult = {
        "output": (
            "2024-01-15 17:00:00 UTC +0000|"
            "2024-01-15 16:00:00 UTC +0000|"
            "2024-01-15 12:00:00 UTC +0000|"
            "2024-01-15 12:00:00 UTC +0000|"
            "2024-01-15 12:00:00 UTC +0000|"
            "2024-01-15 12:00:00 UTC +0000"
        ),
        "error": None,
    }

    assert run_go_oracle(ZONE_ABBREVIATION_REQUEST) == expected

    output = StringIO()
    gotpl.render_to(
        ZONE_ABBREVIATION_REQUEST["template"],
        output,
        name=ZONE_ABBREVIATION_REQUEST["name"],
        functions=sprig.text_func_map(),
    )
    assert {"output": output.getvalue(), "error": None} == expected
