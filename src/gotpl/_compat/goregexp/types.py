"""Shared immutable configuration for both regex surfaces."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Limits:
    """Bound compilation work for patterns accepted from untrusted callers."""

    max_pattern_length: int = 100_000
    max_program_instructions: int = 100_000
    max_repeat_count: int = 1_000
    max_captures: int = 1_000

    def __post_init__(self) -> None:
        for name in (
            "max_pattern_length",
            "max_program_instructions",
            "max_repeat_count",
            "max_captures",
        ):
            if getattr(self, name) < 1:
                raise ValueError(f"{name} must be positive")


DEFAULT_LIMITS = Limits()
