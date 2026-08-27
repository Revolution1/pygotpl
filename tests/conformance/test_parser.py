import json
from typing import NotRequired, TypedDict, cast

import pytest

from gotpl.errors import TemplateSyntaxError
from gotpl.parse import parse_template

from .support import FIXTURE_ROOT, TemplateRequest, run_go_oracle


class ParserCase(TypedDict):
    id: str
    template: str
    data: object
    accepted: bool
    delimiters: NotRequired[dict[str, str]]
    function_profile: NotRequired[str]
    functions: NotRequired[list[str]]


def load_cases() -> list[ParserCase]:
    cases: list[ParserCase] = []
    for fixture in sorted((FIXTURE_ROOT / "parser").glob("*.json")):
        raw: object = json.loads(fixture.read_text(encoding="utf-8"))
        assert isinstance(raw, dict)
        cases.extend(cast(list[ParserCase], raw["cases"]))
    return cases


CASES = load_cases()


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["id"])
def test_parser_case_matches_go(case: ParserCase) -> None:
    request: TemplateRequest = {
        "engine": "text",
        "name": case["id"],
        "template": case["template"],
        "data": case["data"],
        "function_profile": case.get("function_profile", "none"),
    }
    delimiters = case.get("delimiters")
    if delimiters is not None:
        request["delimiters"] = delimiters

    go_result = run_go_oracle(request)
    go_accepted = go_result["error"] is None or go_result["error"]["phase"] != "parse"
    assert go_accepted is case["accepted"]

    if case["accepted"]:
        parse_python_case(case)
    else:
        with pytest.raises(TemplateSyntaxError):
            parse_python_case(case)


def parse_python_case(case: ParserCase) -> None:
    delimiters = case.get("delimiters")
    functions = case.get("functions", [])
    if delimiters is None:
        parse_template(case["template"], functions=functions)
    else:
        parse_template(
            case["template"],
            left_delimiter=delimiters["left"],
            right_delimiter=delimiters["right"],
            functions=functions,
        )
