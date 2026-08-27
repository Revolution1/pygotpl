from io import StringIO
from pathlib import Path

import pytest

import gotpl
import gotpl.funcs.sprig as sprig

from .support import FIXTURE_ROOT, load_fixture, run_go_oracle

FIXTURES = sorted((FIXTURE_ROOT / "sprig").glob("*.json"))


@pytest.mark.parametrize("fixture_path", FIXTURES, ids=lambda path: path.stem)
def test_sprig_fixture_matches_oracle(fixture_path: Path) -> None:
    fixture = load_fixture(fixture_path)
    assert run_go_oracle(fixture.request) == fixture.expected
    profile = fixture.request.get("function_profile")
    assert profile in {"sprig", "sprig-hermetic"}
    functions = (
        sprig.hermetic_text_func_map()
        if profile == "sprig-hermetic"
        else sprig.text_func_map()
    )
    output = StringIO()
    expected_error = fixture.expected["error"]
    if expected_error is None:
        gotpl.render_to(
            fixture.request["template"],
            output,
            fixture.request["data"],
            name=fixture.request["name"],
            functions=functions,
        )
        assert {"output": output.getvalue(), "error": None} == fixture.expected
    else:
        with pytest.raises(gotpl.TemplateExecutionError):
            gotpl.render_to(
                fixture.request["template"],
                output,
                fixture.request["data"],
                name=fixture.request["name"],
                functions=functions,
            )
        assert output.getvalue() == fixture.expected["output"]
        assert expected_error["phase"] == "execute"
