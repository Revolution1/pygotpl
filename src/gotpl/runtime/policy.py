"""Immutable sandbox policy and per-render execution budgets."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from gotpl.errors import BudgetExceededError, SandboxViolationError


@dataclass(frozen=True, slots=True)
class ExecutionBudget:
    """Optional per-render limits; ``None`` leaves one dimension unbounded."""

    max_output_chars: int | None = None
    max_iterations: int | None = None
    max_template_depth: int | None = None
    max_function_calls: int | None = None

    def __post_init__(self) -> None:
        for name in ("max_output_chars", "max_iterations", "max_function_calls"):
            value = getattr(self, name)
            if value is not None and value < 0:
                raise ValueError(f"{name} must be non-negative or None")
        if self.max_template_depth is not None and self.max_template_depth < 1:
            raise ValueError("max_template_depth must be positive or None")

    @classmethod
    def strict(cls) -> ExecutionBudget:
        """Return conservative in-process defaults for untrusted templates."""

        return cls(
            max_output_chars=1_000_000,
            max_iterations=100_000,
            max_template_depth=100,
            max_function_calls=10_000,
        )


@dataclass(frozen=True, slots=True, init=False)
class SandboxPolicy:
    """An immutable data, attribute, method, and function allowlist."""

    allow_attributes: frozenset[str]
    allow_properties: frozenset[str]
    allow_methods: frozenset[str]
    allow_functions: frozenset[str]
    allow_custom_lookup: bool
    max_template_chars: int
    default_budget: ExecutionBudget

    def __init__(
        self,
        *,
        allow_attributes: Iterable[str] = (),
        allow_properties: Iterable[str] = (),
        allow_methods: Iterable[str] = (),
        allow_functions: Iterable[str] = (),
        allow_custom_lookup: bool = False,
        max_template_chars: int = 1_000_000,
        default_budget: ExecutionBudget | None = None,
    ) -> None:
        if max_template_chars < 0:
            raise ValueError("max_template_chars must be non-negative")
        object.__setattr__(self, "allow_attributes", frozenset(allow_attributes))
        object.__setattr__(self, "allow_properties", frozenset(allow_properties))
        object.__setattr__(self, "allow_methods", frozenset(allow_methods))
        object.__setattr__(self, "allow_functions", frozenset(allow_functions))
        object.__setattr__(self, "allow_custom_lookup", allow_custom_lookup)
        object.__setattr__(self, "max_template_chars", max_template_chars)
        object.__setattr__(
            self,
            "default_budget",
            ExecutionBudget.strict() if default_budget is None else default_budget,
        )

    @classmethod
    def strict(
        cls,
        *,
        allow_attributes: Iterable[str] = (),
        allow_properties: Iterable[str] = (),
        allow_methods: Iterable[str] = (),
        allow_functions: Iterable[str] = (),
        allow_custom_lookup: bool = False,
        max_template_chars: int = 1_000_000,
        default_budget: ExecutionBudget | None = None,
    ) -> SandboxPolicy:
        """Build the explicit strict preset."""

        return cls(
            allow_attributes=allow_attributes,
            allow_properties=allow_properties,
            allow_methods=allow_methods,
            allow_functions=allow_functions,
            allow_custom_lookup=allow_custom_lookup,
            max_template_chars=max_template_chars,
            default_budget=default_budget,
        )

    def validate_functions(self, names: Iterable[str]) -> None:
        """Reject registered functions not explicitly granted by this policy."""

        denied = sorted(set(names) - self.allow_functions)
        if denied:
            rendered = ", ".join(denied)
            raise SandboxViolationError(
                f"registered functions are not allowed by the sandbox: {rendered}"
            )


@dataclass(slots=True)
class ExecutionBudgetState:
    """Mutable counters owned by one render operation."""

    limits: ExecutionBudget
    output_chars: int = 0
    iterations: int = 0
    function_calls: int = 0

    def consume_output(self, amount: int) -> None:
        self.output_chars = self._consume(
            "output character",
            self.output_chars,
            amount,
            self.limits.max_output_chars,
        )

    def consume_iteration(self) -> None:
        self.iterations = self._consume(
            "iteration",
            self.iterations,
            1,
            self.limits.max_iterations,
        )

    def consume_function_call(self) -> None:
        self.function_calls = self._consume(
            "function-call",
            self.function_calls,
            1,
            self.limits.max_function_calls,
        )

    def check_template_depth(self, depth: int) -> None:
        limit = self.limits.max_template_depth
        if limit is not None and depth > limit:
            raise BudgetExceededError(
                f"template-depth budget exceeded: limit {limit}, requested {depth}"
            )

    @staticmethod
    def _consume(
        label: str,
        current: int,
        amount: int,
        limit: int | None,
    ) -> int:
        requested = current + amount
        if limit is not None and requested > limit:
            raise BudgetExceededError(
                f"{label} budget exceeded: limit {limit}, requested {requested}"
            )
        return requested


__all__ = ["ExecutionBudget", "SandboxPolicy"]
