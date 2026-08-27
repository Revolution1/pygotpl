from __future__ import annotations

from inspect import signature

import gotpl
import gotpl.funcs.helm as helm
import gotpl.funcs.slim_sprig as slim_sprig
import gotpl.funcs.sprig as sprig
import gotpl.funcs.sprout as sprout
import gotpl.pythonic as pythonic

ROOT_API = {
    "CSS",
    "HTML",
    "JS",
    "URL",
    "AsyncRequiredError",
    "AsyncTextWriter",
    "BudgetExceededError",
    "ExecutionBudget",
    "FormatMode",
    "FunctionResult",
    "GoFormatSpec",
    "GoFormatter",
    "GoPointer",
    "GoSeq",
    "GoSeq2",
    "HTMLAttr",
    "HTMLTemplate",
    "JSStr",
    "MissingKeyMode",
    "PythonExtensions",
    "SandboxPolicy",
    "SandboxViolationError",
    "Srcset",
    "Template",
    "TemplateEngine",
    "TemplateError",
    "TemplateExecutionError",
    "TemplateSyntaxError",
    "TypedMap",
    "__version__",
    "render",
    "render_async",
    "render_async_to",
    "render_html",
    "render_html_async",
    "render_html_async_to",
    "render_html_to",
    "render_to",
}

FUNCTION_MAP_API = {
    "generic_func_map",
    "hermetic_html_func_map",
    "hermetic_text_func_map",
    "html_func_map",
    "text_func_map",
}


def test_root_public_api_is_frozen() -> None:
    assert set(gotpl.__all__) == ROOT_API
    assert all(hasattr(gotpl, name) for name in ROOT_API)


def test_exception_hierarchy_is_frozen() -> None:
    assert issubclass(gotpl.TemplateSyntaxError, gotpl.TemplateError)
    assert issubclass(gotpl.TemplateExecutionError, gotpl.TemplateError)
    assert issubclass(gotpl.AsyncRequiredError, gotpl.TemplateExecutionError)
    assert issubclass(gotpl.SandboxViolationError, gotpl.TemplateExecutionError)
    assert issubclass(gotpl.BudgetExceededError, gotpl.TemplateExecutionError)


def test_reusable_template_method_surfaces_are_frozen() -> None:
    shared = {
        "from_sources",
        "render",
        "render_async",
        "render_async_to",
        "render_source",
        "render_source_async",
        "render_template",
        "render_template_async",
        "render_template_async_to",
        "render_template_to",
        "render_to",
        "with_source",
    }
    assert all(callable(getattr(gotpl.Template, name)) for name in shared)
    assert all(callable(getattr(gotpl.HTMLTemplate, name)) for name in shared)


def test_text_and_html_convenience_functions_expose_matching_options() -> None:
    pairs = (
        (gotpl.render, gotpl.render_html),
        (gotpl.render_to, gotpl.render_html_to),
        (gotpl.render_async, gotpl.render_html_async),
        (gotpl.render_async_to, gotpl.render_html_async_to),
    )
    for text_function, html_function in pairs:
        text_parameters = signature(text_function).parameters
        html_parameters = signature(html_function).parameters
        assert tuple(html_parameters) == tuple(text_parameters)
        assert tuple(
            (parameter.kind, parameter.default)
            for parameter in html_parameters.values()
        ) == tuple(
            (parameter.kind, parameter.default)
            for parameter in text_parameters.values()
        )


def test_function_library_public_apis_are_frozen() -> None:
    assert set(sprig.__all__) == FUNCTION_MAP_API
    assert set(slim_sprig.__all__) == FUNCTION_MAP_API
    assert set(helm.__all__) == {"MissingOptionalDependencyError", "function_map"}
    assert set(pythonic.__all__) == {"PythonExtensions"}
    assert set(sprout.__all__) == {
        "INVENTORY",
        "FunctionRegistry",
        "GroupInventory",
        "Handler",
        "MissingOptionalDependencyError",
        "Notice",
        "NoticeKind",
        "RegistryGroup",
        "RegistryInventory",
        "SproutInventory",
        "TemplateFunction",
        "__version__",
        "group",
        "registry",
    }
