from dataclasses import dataclass
from typing import Any, Literal

import pytest

import gotpl
from gotpl.runtime import callables, sync_vm


def test_defaulted_positional_parameters_are_a_python_extension() -> None:
    def surround(value: str, left: str = "[", right: str = "]") -> str:
        return f"{left}{value}{right}"

    template = gotpl.Template(
        '{{surround "x"}}|{{surround "x" "("}}|{{surround "x" "(" ")"}}',
        functions={"surround": surround},
    )

    assert template.render() == "[x]|(x]|(x)"


def test_optional_keyword_only_parameters_use_their_python_defaults() -> None:
    def label(value: str, *, prefix: str = "item") -> str:
        return f"{prefix}:{value}"

    assert gotpl.render('{{label "x"}}', functions={"label": label}) == "item:x"


def test_required_keyword_only_parameters_are_rejected_at_registration() -> None:
    def invalid(value: str, *, required: str) -> str:
        return required + value

    with pytest.raises(TypeError, match="required keyword-only parameter 'required'"):
        gotpl.Template("stable", functions={"invalid": invalid})


@pytest.mark.parametrize(
    ("template", "expected"),
    [
        ("{{fixed 1}}", "wrong number of args for fixed: want 2 got 1"),
        ("{{fixed 1 2 3}}", "wrong number of args for fixed: want 2 got 3"),
        ("{{defaulted}}", "wrong number of args for defaulted: want 1 to 2 got 0"),
        ("{{variadic}}", "wrong number of args for variadic: want at least 1 got 0"),
    ],
)
def test_registered_function_arity_errors_are_stable(
    template: str, expected: str
) -> None:
    def fixed(left: object, right: object) -> tuple[object, object]:
        return left, right

    def defaulted(value: object, suffix: object = "") -> tuple[object, object]:
        return value, suffix

    def variadic(first: object, *rest: object) -> tuple[object, ...]:
        return (first, *rest)

    functions = {"fixed": fixed, "defaulted": defaulted, "variadic": variadic}

    with pytest.raises(gotpl.TemplateExecutionError, match=expected):
        gotpl.render(template, functions=functions)


def test_type_error_raised_inside_function_is_not_misclassified_as_arity() -> None:
    failure = TypeError("function body failed")

    def fail() -> None:
        raise failure

    with pytest.raises(
        gotpl.TemplateExecutionError, match="function body failed"
    ) as caught:
        gotpl.render("{{fail}}", functions={"fail": fail})

    assert caught.value.__cause__ is failure


@pytest.mark.parametrize(
    ("template", "expected"),
    [
        ("{{fixed 1}}", "argument 1 to fixed: expected str, got int"),
        ('{{variadic "ok" 1}}', "argument 2 to variadic: expected str, got int"),
        ("{{integer true}}", "argument 1 to integer: expected int, got bool"),
    ],
)
def test_registered_function_annotations_reject_incompatible_arguments(
    template: str, expected: str
) -> None:
    def fixed(value: str) -> str:
        return value

    def variadic(*values: str) -> str:
        return ",".join(values)

    def integer(value: int) -> int:
        return value

    functions = {"fixed": fixed, "integer": integer, "variadic": variadic}

    with pytest.raises(gotpl.TemplateExecutionError, match=expected):
        gotpl.render(template, functions=functions)


def test_supported_annotations_accept_compatible_arguments() -> None:
    def quoted(value: "str") -> str:
        return value

    def optional(value: str | None) -> str:
        return "none" if value is None else value

    def literal(value: Literal["x"]) -> str:
        return value

    def sequence(value: list[int]) -> int:
        return len(value)

    def floating(value: float) -> str:
        return str(value)

    def imaginary(value: complex) -> str:
        return str(value)

    def anything(value: Any) -> str:
        return type(value).__name__

    def opaque(value: object) -> object:
        return value

    opaque.__annotations__["value"] = "UnknownType"

    def null(value: None) -> str:
        return "none" if value is None else "set"

    def unusual(value: object) -> object:
        return value

    unusual.__annotations__["value"] = 42

    functions = {
        "anything": anything,
        "floating": floating,
        "imaginary": imaginary,
        "literal": literal,
        "null": null,
        "opaque": opaque,
        "optional": optional,
        "quoted": quoted,
        "sequence": sequence,
        "unusual": unusual,
    }
    source = (
        '{{quoted "x"}}/{{optional .none}}/{{literal "x"}}/'
        "{{sequence .items}}/{{floating 1.5}}/{{imaginary 1i}}/"
        "{{anything 1}}/{{opaque 1}}/{{null .none}}/{{unusual 2}}"
    )

    assert (
        gotpl.render(
            source,
            {"items": [1], "none": None},
            functions=functions,
        )
        == "x/none/x/1/1.5/1j/int/1/none/2"
    )


@pytest.mark.parametrize(
    ("template", "expected"),
    [
        ("{{optional 1}}", "expected str | NoneType"),
        ('{{literal "y"}}', "expected typing.Literal"),
        ("{{sequence 1}}", "expected list"),
        ("{{floating 1}}", "expected float"),
        ("{{imaginary 1.5}}", "expected complex"),
    ],
)
def test_supported_annotations_report_stable_type_names(
    template: str, expected: str
) -> None:
    def optional(value: str | None) -> object:
        return value

    def literal(value: Literal["x"]) -> object:
        return value

    def sequence(value: list[int]) -> object:
        return value

    def floating(value: float) -> object:
        return value

    def imaginary(value: complex) -> object:
        return value

    functions = {
        "floating": floating,
        "imaginary": imaginary,
        "literal": literal,
        "optional": optional,
        "sequence": sequence,
    }

    with pytest.raises(gotpl.TemplateExecutionError, match=expected):
        gotpl.render(template, functions=functions)


def test_unhashable_callable_objects_use_signature_validation() -> None:
    @dataclass
    class Prefix:
        prefix: str

        def __call__(self, value: str) -> str:
            return self.prefix + value

    assert gotpl.render('{{prefix "x"}}', functions={"prefix": Prefix("p:")}) == ("p:x")


@pytest.mark.asyncio
async def test_reusable_templates_prepare_unhashable_callable_signatures_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    @dataclass
    class Prefix:
        prefix: str

        def __call__(self, value: str) -> str:
            return self.prefix + value

    function = Prefix("p:")
    inspections = 0
    original = callables._inspect_call_spec  # pyright: ignore[reportPrivateUsage]

    def inspect_once(function: object) -> callables.CallSpec | None:
        nonlocal inspections
        if function is target:
            inspections += 1
        return original(function)  # pyright: ignore[reportArgumentType]

    target = function
    monkeypatch.setattr(callables, "_inspect_call_spec", inspect_once)
    template = gotpl.Template(
        '{{prefix "x"}}',
        functions={"prefix": function},
    )

    assert inspections == 1
    assert template.render() == "p:x"
    assert template.render() == "p:x"
    assert await template.render_async() == "p:x"
    assert inspections == 1


def test_prepared_function_registry_is_complete_and_defensive() -> None:
    def function(value: object) -> object:
        return value

    registry = callables.PreparedFunctionRegistry({"identity": function})

    assert len(registry) == 1
    assert list(registry) == ["identity"]
    assert registry["identity"] is function
    assert callables._annotation_is_enforceable(  # pyright: ignore[reportPrivateUsage]
        None
    )

    with pytest.raises(ValueError, match="names do not match"):
        callables.PreparedFunctionRegistry(
            {"identity": function},
            {"different": None},
        )

    runtime_registry = sync_vm._execution_function_registry(  # pyright: ignore[reportPrivateUsage]
        "go",
        {"identity": function},
    )
    assert runtime_registry["identity"] is function
    assert (
        sync_vm._execution_function_registry(  # pyright: ignore[reportPrivateUsage]
            "go", runtime_registry
        )
        is runtime_registry
    )
    assert (
        sync_vm._builtin_functions.cache_info().maxsize  # pyright: ignore[reportPrivateUsage]
        == 2
    )


def test_uninspectable_callable_objects_fall_back_to_direct_invocation() -> None:
    class NativeLikeCallable:
        __signature__ = "unavailable"

        def __call__(self) -> str:
            return "called"

    function = NativeLikeCallable()

    assert gotpl.render("{{native}}", functions={"native": function}) == "called"
