from __future__ import annotations

from dataclasses import FrozenInstanceError, dataclass
from io import StringIO

import pytest

from gotpl import (
    BudgetExceededError,
    ExecutionBudget,
    HTMLTemplate,
    SandboxPolicy,
    SandboxViolationError,
    Template,
    TemplateExecutionError,
)
from gotpl.funcs.helm import function_map as helm_function_map
from gotpl.funcs.slim_sprig import text_func_map as slim_sprig_text_func_map
from gotpl.funcs.sprig import text_func_map
from gotpl.funcs.sprout import Handler, group


@dataclass
class _Record:
    name: str

    @property
    def computed(self) -> str:
        return f"property:{self.name}"

    def greet(self) -> str:
        return f"hello:{self.name}"


class _CustomLookup:
    def __gotemplate_lookup__(self, field: str) -> str:
        return f"lookup:{field}"


def _late(*_arguments: object) -> str:
    return ""


def test_strict_sandbox_is_immutable_and_defaults_to_mapping_data_only() -> None:
    policy = SandboxPolicy.strict()

    assert Template("{{.name}}", sandbox=policy).render({"name": "mapping"}) == (
        "mapping"
    )
    with pytest.raises(SandboxViolationError, match="attribute 'name'"):
        Template("{{.name}}", sandbox=policy).render(_Record("object"))
    with pytest.raises(FrozenInstanceError):
        policy.allow_attributes = frozenset({"name"})  # type: ignore[misc]


def test_strict_sandbox_separates_data_properties_and_methods() -> None:
    record = _Record("Ada")
    attributes = SandboxPolicy.strict(allow_attributes={"name"})
    properties = SandboxPolicy.strict(allow_properties={"computed"})
    methods = SandboxPolicy.strict(allow_methods={"greet"})

    assert Template("{{.name}}", sandbox=attributes).render(record) == "Ada"
    with pytest.raises(SandboxViolationError, match="property 'computed'"):
        Template("{{.computed}}", sandbox=attributes).render(record)
    assert Template("{{.computed}}", sandbox=properties).render(record) == (
        "property:Ada"
    )
    with pytest.raises(SandboxViolationError, match="method 'greet'"):
        Template("{{.greet}}", sandbox=attributes).render(record)
    assert Template("{{.greet}}", sandbox=methods).render(record) == "hello:Ada"


def test_strict_sandbox_denies_custom_lookup_and_data_callables() -> None:
    policy = SandboxPolicy.strict()

    with pytest.raises(SandboxViolationError, match="custom template lookup"):
        Template("{{.secret}}", sandbox=policy).render(_CustomLookup())
    with pytest.raises(TemplateExecutionError, match="function 'call' is not defined"):
        Template("{{call .fn}}", sandbox=policy).render({"fn": lambda: "secret"})


def test_strict_sandbox_requires_explicit_registered_function_allowlist() -> None:
    def safe_function() -> str:
        return "safe"

    with pytest.raises(SandboxViolationError, match=r"registered functions.*safe"):
        Template(
            "{{safe}}",
            functions={"safe": safe_function},
            sandbox=SandboxPolicy.strict(),
        )

    policy = SandboxPolicy.strict(allow_functions={"safe"})
    assert (
        Template(
            "{{safe}}",
            functions={"safe": safe_function},
            sandbox=policy,
        ).render()
        == "safe"
    )


def test_strict_sandbox_does_not_admit_sprig_or_sprout_profiles_implicitly() -> None:
    policy = SandboxPolicy.strict()

    with pytest.raises(SandboxViolationError, match="registered functions"):
        Template("ok", functions=text_func_map(), sandbox=policy)
    with pytest.raises(SandboxViolationError, match="registered functions"):
        Template(
            "ok",
            functions=Handler(*group("all").registries).build(),
            sandbox=policy,
        )
    with pytest.raises(SandboxViolationError, match="registered functions"):
        Template("ok", functions=slim_sprig_text_func_map(), sandbox=policy)
    with pytest.raises(SandboxViolationError, match="registered functions"):
        Template(
            "ok",
            functions=helm_function_map(
                include=_late,
                tpl=_late,
                required=_late,
                fail=_late,
            ),
            sandbox=policy,
        )


def test_strict_sandbox_denies_mutation_and_resource_amplification_by_default() -> None:
    functions = text_func_map()
    for name in ("set", "unset", "merge", "bcrypt"):
        with pytest.raises(SandboxViolationError, match=name):
            Template(
                "ok",
                functions={name: functions[name]},
                sandbox=SandboxPolicy.strict(),
            )

    sprout = Handler(*group("all").registries).build()
    with pytest.raises(SandboxViolationError, match="cidrRangeList"):
        Template(
            "ok",
            functions={"cidrRangeList": sprout["cidrRangeList"]},
            sandbox=SandboxPolicy.strict(),
        )


def test_output_budget_prevents_over_limit_writer_mutation() -> None:
    budget = ExecutionBudget(max_output_chars=3)
    assert Template("abc", budget=budget).render() == "abc"

    writer = StringIO()
    with pytest.raises(BudgetExceededError, match="output character budget"):
        Template("ab{{.}}", budget=budget).render_to(writer, "cd")
    assert writer.getvalue() == "ab"


def test_iteration_function_call_and_template_depth_budgets_are_per_render() -> None:
    iteration_template = Template(
        "{{range .}}{{.}}{{end}}",
        budget=ExecutionBudget(max_iterations=2),
    )
    with pytest.raises(BudgetExceededError, match="iteration budget"):
        iteration_template.render([1, 2, 3])
    assert iteration_template.render([1, 2]) == "12"

    def identify(value: object) -> object:
        return value

    function_template = Template(
        "{{identify 1}}{{identify 2}}{{identify 3}}",
        functions={"identify": identify},
        budget=ExecutionBudget(max_function_calls=2),
    )
    with pytest.raises(BudgetExceededError, match="function-call budget"):
        function_template.render()

    depth_template = Template(
        '{{template "recurse" .}}'
        '{{define "recurse"}}{{if .}}{{template "recurse" false}}{{end}}{{end}}',
        budget=ExecutionBudget(max_template_depth=1),
    )
    with pytest.raises(BudgetExceededError, match="template-depth budget"):
        depth_template.render(True)


def test_html_template_uses_the_same_policy_and_counts_escaped_output() -> None:
    policy = SandboxPolicy.strict()
    with pytest.raises(SandboxViolationError, match="attribute 'name'"):
        HTMLTemplate("<p>{{.name}}</p>", sandbox=policy).render(_Record("Ada"))

    with pytest.raises(BudgetExceededError, match="output character budget"):
        HTMLTemplate("{{.}}", budget=ExecutionBudget(max_output_chars=3)).render("<")


def test_execution_budget_rejects_invalid_limits() -> None:
    with pytest.raises(ValueError, match="max_output_chars"):
        ExecutionBudget(max_output_chars=-1)
    with pytest.raises(ValueError, match="max_template_depth"):
        ExecutionBudget(max_template_depth=0)


def test_strict_sandbox_bounds_source_size_and_uses_fresh_default_budgets() -> None:
    policy = SandboxPolicy.strict(
        max_template_chars=3,
        default_budget=ExecutionBudget(max_output_chars=1),
    )
    with pytest.raises(SandboxViolationError, match="source exceeds"):
        Template("four", sandbox=policy)

    template = Template("x", sandbox=policy)
    assert template.render() == "x"
    assert template.render() == "x"
