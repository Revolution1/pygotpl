import pytest

import gotpl


def test_function_result_success_unwraps_to_its_value() -> None:
    def load() -> gotpl.FunctionResult:
        return gotpl.FunctionResult.success("loaded")

    assert gotpl.render("{{load}}", functions={"load": load}) == "loaded"


def test_function_result_failure_uses_the_normal_exception_chain() -> None:
    failure = RuntimeError("load failed")

    def load() -> gotpl.FunctionResult:
        return gotpl.FunctionResult.failure(failure)

    with pytest.raises(gotpl.TemplateExecutionError, match="load failed") as captured:
        gotpl.render("before/{{load}}/after", functions={"load": load})

    assert captured.value.__cause__ is failure


def test_call_builtin_and_bound_methods_unwrap_function_results() -> None:
    def load() -> gotpl.FunctionResult:
        return gotpl.FunctionResult.success("function")

    class Subject:
        def load(self) -> gotpl.FunctionResult:
            return gotpl.FunctionResult.success("method")

    assert gotpl.render("{{call .}}", load) == "function"
    assert gotpl.render("{{.load}}", Subject()) == "method"


def test_ordinary_tuples_remain_ordinary_template_values() -> None:
    def pair() -> tuple[str, str]:
        return "left", "right"

    assert gotpl.render("{{pair}}", functions={"pair": pair}) == "[left right]"


def test_function_result_rejects_non_exception_errors() -> None:
    with pytest.raises(TypeError, match="exception"):
        gotpl.FunctionResult("value", "error")  # type: ignore[arg-type]
