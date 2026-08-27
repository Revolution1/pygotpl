from __future__ import annotations

import json
from io import StringIO

import gotpl
import gotpl.funcs.sprig as sprig

from .support import ExpectedResult, TemplateRequest, run_go_oracle_many

_CONSTRAINT_CASES = (
    ("*", "1.2.3-alpha.1"),
    ("*-0", "1.2.3-alpha.1"),
    ("2", "2.9.9"),
    ("2", "3.0.0"),
    ("2.1", "2.1.9"),
    ("2.1", "2.2.0"),
    ("!=4.1", "4.1.0"),
    ("!=4.1", "4.1.1"),
    ("!=4.1", "5.1.0"),
    ("<11", "11.0.0"),
    ("<11", "10.9.9"),
    ("<=11", "11.9.9"),
    (">11", "11.9.9"),
    (">11", "12.0.0"),
    (">11.1", "11.1.1"),
    (">11.1", "11.2.0"),
    (">=11.1", "11.1.1"),
    ("^1", "1.8.9"),
    ("^1", "2.0.0"),
    ("^0", "0.2.3"),
    ("^0", "1.0.0"),
    ("^0.0", "0.0.3"),
    ("^0.0", "0.1.0"),
    ("^0.2", "0.2.5"),
    ("^0.2", "0.3.0"),
    ("^0.0.3", "0.0.3"),
    ("^0.0.3", "0.0.4"),
    ("~1", "1.9.9"),
    ("~1", "2.0.0"),
    ("~1.2", "1.2.9"),
    ("~1.2", "1.3.0"),
    ("1.2 - 2.3", "2.3.99"),
    ("1.2 - 2.3", "2.4.0"),
    ("1.2.3 - 2.3.4", "2.3.4"),
    ("1.2.3 - 2.3.4", "2.3.5"),
    (">=0", "0.0.1-alpha"),
    (">=0-0", "0.0.1-alpha"),
    (">=0.0.0-0", "3.4.5-beta.1"),
    ("~1.2.3-beta.2", "1.2.4-beta.2"),
    ("~1.2.3-beta.2", "1.3.0-beta.1"),
    ("^0.2.3-beta.2", "0.2.4-beta.2"),
    ("^0.2.3-beta.2", "0.3.0-beta.1"),
    (">= 1.2.3, < 2.0.0", "1.9.9"),
    (">= 1.2.3 < 2.0 || => 3.0 < 4", "3.5.0"),
)


def test_masterminds_constraint_matrix_matches_go() -> None:
    requests = [
        TemplateRequest(
            engine="text",
            name=f"semver-matrix-{index}",
            template=(
                "{{semverCompare "
                + json.dumps(constraint)
                + " "
                + json.dumps(version)
                + "}}"
            ),
            data=None,
            function_profile="sprig-hermetic",
        )
        for index, (constraint, version) in enumerate(_CONSTRAINT_CASES)
    ]
    expected = run_go_oracle_many(requests)
    functions = sprig.hermetic_text_func_map()
    actual: list[ExpectedResult] = []

    for request in requests:
        output = StringIO()
        gotpl.render_to(
            request["template"],
            output,
            name=request["name"],
            functions=functions,
        )
        actual.append({"output": output.getvalue(), "error": None})

    assert actual == expected
