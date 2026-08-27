from __future__ import annotations

import random
from io import StringIO

import pytest

import gotpl
import gotpl.funcs.sprig as sprig

from .support import ExpectedResult, TemplateRequest, run_go_oracle_many

_GO_ABSOLUTE_TO_UNIX = -9_223_372_028_741_760_000
_BOUNDARY_SECONDS = (
    -(1 << 63),
    -(1 << 63) + 1,
    _GO_ABSOLUTE_TO_UNIX - 1,
    _GO_ABSOLUTE_TO_UNIX,
    _GO_ABSOLUTE_TO_UNIX + 1,
    -1_000_000_000_000_000_000,
    -62_167_219_200,
    -62_135_596_801,
    -62_135_596_800,
    -1,
    0,
    253_402_300_799,
    253_402_300_800,
    1_000_000_000_000_000_000,
    (1 << 63) - 2,
    (1 << 63) - 1,
)
_RANDOM = random.Random(0xC1A11)
_UNIX_SECONDS = _BOUNDARY_SECONDS + tuple(
    _RANDOM.randrange(-(1 << 63), 1 << 63) for _ in range(32)
)
_LAYOUT = "Monday 2006 06-01-02 002 15:04:05 MST -07:00:00"


@pytest.mark.parametrize("zone", ["UTC", "America/New_York"])
def test_unix_int64_civil_matrix_matches_go(zone: str) -> None:
    requests: list[TemplateRequest] = [
        {
            "engine": "text",
            "name": f"date-unix-{index}",
            "template": f'{{{{dateInZone "{_LAYOUT}" {seconds} "{zone}"}}}}',
            "data": None,
            "function_profile": "sprig",
        }
        for index, seconds in enumerate(_UNIX_SECONDS)
    ]
    expected_results = run_go_oracle_many(requests)
    functions = sprig.text_func_map()

    actual_results: list[ExpectedResult] = []
    for request in requests:
        output = StringIO()
        gotpl.render_to(
            request["template"],
            output,
            name=request["name"],
            functions=functions,
        )
        actual_results.append({"output": output.getvalue(), "error": None})

    assert actual_results == expected_results
