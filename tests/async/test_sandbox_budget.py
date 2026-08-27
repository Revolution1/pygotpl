from __future__ import annotations

import pytest

from gotpl import BudgetExceededError, ExecutionBudget, SandboxPolicy, Template


@pytest.mark.asyncio
async def test_async_runtime_enforces_output_iteration_and_function_budgets() -> None:
    calls = 0

    async def identify(value: object) -> object:
        nonlocal calls
        calls += 1
        return value

    template = Template(
        "{{range .}}{{identify .}}{{end}}",
        functions={"identify": identify},
        sandbox=SandboxPolicy.strict(allow_functions={"identify"}),
        budget=ExecutionBudget(
            max_output_chars=10,
            max_iterations=2,
            max_function_calls=2,
        ),
    )

    assert await template.render_async([1, 2]) == "12"
    with pytest.raises(BudgetExceededError, match="iteration budget"):
        await template.render_async([1, 2, 3])
    assert calls == 4


@pytest.mark.asyncio
async def test_async_template_depth_budget_matches_sync_runtime() -> None:
    template = Template(
        '{{template "recurse" .}}'
        '{{define "recurse"}}{{if .}}{{template "recurse" false}}{{end}}{{end}}',
        budget=ExecutionBudget(max_template_depth=1),
    )

    with pytest.raises(BudgetExceededError, match="template-depth budget"):
        await template.render_async(True)
