from collections.abc import Callable, Mapping
from io import StringIO
from pathlib import Path
from typing import cast

import pytest

import gotpl
from gotpl.runtime import MissingKeyMode

from .support import FIXTURE_ROOT, load_fixture, run_go_oracle

FIXTURES = sorted((FIXTURE_ROOT / "text").glob("*.json"))


def execution_functions() -> Mapping[str, Callable[..., object]]:
    def fail() -> gotpl.FunctionResult:
        return gotpl.FunctionResult.failure(RuntimeError("oracle failure"))

    def join(left: str, right: str) -> str:
        return f"{left}+{right}"

    def stringmap() -> gotpl.TypedMap[str, str]:
        return gotpl.TypedMap({"present": "value"}, zero="")

    def intmap() -> gotpl.TypedMap[str, int]:
        return gotpl.TypedMap({"present": 7}, zero=0)

    def intkeymap() -> gotpl.TypedMap[int, str]:
        return gotpl.TypedMap(
            {10: "ten", 2: "two", 1: "one"},
            zero="",
            key_type="int",
            value_type="string",
        )

    def seq() -> gotpl.GoSeq[int]:
        return gotpl.GoSeq([0, 1])

    def seq2() -> gotpl.GoSeq2[int, int]:
        return gotpl.GoSeq2([(0, 10), (1, 11)])

    def complexmap() -> dict[complex, str]:
        return {
            complex(2, -1): "two-minus-one",
            complex(-1, 3): "minus-one-three",
            complex(2, -2): "two-minus-two",
            complex(0, 4): "zero-four",
        }

    def bytes_value() -> bytes:
        return b"Go!\n"

    def ok() -> gotpl.FunctionResult:
        return gotpl.FunctionResult.success("ok")

    def variadic(prefix: str, *values: str) -> str:
        return f"{prefix}:{','.join(values)}"

    return {
        "complexmap": complexmap,
        "bytes": bytes_value,
        "fail": fail,
        "join": join,
        "intmap": intmap,
        "intkeymap": intkeymap,
        "ok": ok,
        "seq": seq,
        "seq2": seq2,
        "stringmap": stringmap,
        "variadic": variadic,
    }


@pytest.mark.parametrize("fixture_path", FIXTURES, ids=lambda path: path.stem)
def test_text_fixture_matches_go_and_python(fixture_path: Path) -> None:
    fixture = load_fixture(fixture_path)
    assert run_go_oracle(fixture.request) == fixture.expected

    request = fixture.request
    assert request["engine"] == "text"
    modes = {
        "missingkey=default": "default",
        "missingkey=zero": "zero",
        "missingkey=error": "error",
    }
    options = request.get("options", [])
    assert all(option in modes for option in options)
    missing_key = modes[options[-1]] if options else "default"
    profile = request.get("function_profile", "none")
    assert profile in {"none", "execution-functions"}
    functions = execution_functions() if profile == "execution-functions" else None
    output = StringIO()
    template = gotpl.Template(
        request["template"],
        name=request["name"],
        missing_key=cast(MissingKeyMode, missing_key),
        functions=functions,
    )
    expected_error = fixture.expected["error"]
    execute_template = request.get("execute_template")
    if expected_error is None:
        if execute_template is None:
            template.render_to(output, request["data"])
        else:
            template.render_template_to(execute_template, output, request["data"])
        assert {"output": output.getvalue(), "error": None} == fixture.expected
    else:
        with pytest.raises(gotpl.TemplateExecutionError) as captured:
            if execute_template is None:
                template.render_to(output, request["data"])
            else:
                template.render_template_to(execute_template, output, request["data"])
        assert output.getvalue() == fixture.expected["output"]
        assert expected_error["phase"] == "execute"
        assert str(captured.value)
