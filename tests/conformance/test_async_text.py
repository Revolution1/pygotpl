from collections.abc import Callable, Mapping
from io import StringIO
from pathlib import Path
from typing import cast

import pytest

import gotpl
from gotpl.runtime import MissingKeyMode

from .support import FIXTURE_ROOT, load_fixture
from .test_text import execution_functions

FIXTURES = sorted((FIXTURE_ROOT / "text").glob("*.json"))


@pytest.mark.asyncio
@pytest.mark.parametrize("fixture_path", FIXTURES, ids=lambda path: path.stem)
async def test_async_vm_matches_sync_conformance_fixture(fixture_path: Path) -> None:
    fixture = load_fixture(fixture_path)
    request = fixture.request
    modes = {
        "missingkey=default": "default",
        "missingkey=zero": "zero",
        "missingkey=error": "error",
    }
    options = request.get("options", [])
    missing_key = modes[options[-1]] if options else "default"
    profile = request.get("function_profile", "none")
    functions: Mapping[str, Callable[..., object]] | None = (
        execution_functions() if profile == "execution-functions" else None
    )
    output = StringIO()
    template = gotpl.Template(
        request["template"],
        name=request["name"],
        missing_key=cast(MissingKeyMode, missing_key),
        functions=functions,
    )
    execute_template = request.get("execute_template")
    expected_error = fixture.expected["error"]

    if expected_error is None:
        if execute_template is None:
            await template.render_async_to(output, request["data"])
        else:
            await template.render_template_async_to(
                execute_template, output, request["data"]
            )
        assert output.getvalue() == fixture.expected["output"]
    else:
        with pytest.raises(gotpl.TemplateExecutionError):
            if execute_template is None:
                await template.render_async_to(output, request["data"])
            else:
                await template.render_template_async_to(
                    execute_template, output, request["data"]
                )
        assert output.getvalue() == fixture.expected["output"]
