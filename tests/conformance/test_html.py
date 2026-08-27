from collections.abc import Callable
from io import StringIO
from pathlib import Path

import pytest

import gotpl

from .support import FIXTURE_ROOT, Fixture, load_fixture, run_go_oracle

FIXTURES = sorted((FIXTURE_ROOT / "html").glob("*.json"))


@pytest.mark.parametrize("fixture_path", FIXTURES, ids=lambda path: path.stem)
def test_html_fixture_matches_go_and_python(fixture_path: Path) -> None:
    fixture = load_fixture(fixture_path)
    assert run_go_oracle(fixture.request) == fixture.expected

    output = StringIO()
    functions = _fixture_functions(fixture.request.get("function_profile", ""))
    expected_error = fixture.expected["error"]
    execute_template = fixture.request.get("execute_template")
    if expected_error is None:
        template = _fixture_template(fixture, functions)
        if execute_template is None:
            template.render_to(output, fixture.request["data"])
        else:
            template.render_template_to(
                execute_template, output, fixture.request["data"]
            )
        assert {"output": output.getvalue(), "error": None} == fixture.expected
    else:
        with pytest.raises(gotpl.TemplateError):
            template = _fixture_template(fixture, functions)
            if execute_template is None:
                template.render_to(output, fixture.request["data"])
            else:
                template.render_template_to(
                    execute_template, output, fixture.request["data"]
                )
        assert output.getvalue() == fixture.expected["output"]


def _fixture_template(
    fixture: Fixture,
    functions: dict[str, Callable[..., object]] | None,
) -> gotpl.HTMLTemplate:
    request = fixture.request
    return gotpl.HTMLTemplate(
        request["template"],
        name=request["name"],
        functions=functions,
    )


def _fixture_functions(profile: str) -> dict[str, Callable[..., object]] | None:
    if profile != "trusted-content":
        return None
    return {
        "trustedCSS": lambda: gotpl.CSS('a[href="//x"]{color:red}'),
        "trustedHTML": lambda: gotpl.HTML("Hello, <b>World</b> &amp;!"),
        "trustedAttr": lambda: gotpl.HTMLAttr(' dir="ltr"'),
        "trustedJS": lambda: gotpl.JS('x && alert("ok")'),
        "trustedJSStr": lambda: gotpl.JSStr(r"line\u0021"),
        "trustedURL": lambda: gotpl.URL("javascript:trusted()"),
        "trustedSrcset": lambda: gotpl.Srcset("javascript:trusted() 2x, /safe 1x"),
    }
