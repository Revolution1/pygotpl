"""Opt-in extensions backed by Python standard-library behavior."""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from functools import lru_cache
from types import MappingProxyType


@lru_cache(maxsize=256)
def _compile_pattern(pattern: str) -> re.Pattern[str]:
    return re.compile(pattern)


def _re_match(pattern: str, value: str) -> bool:
    return _compile_pattern(pattern).search(value) is not None


@dataclass(frozen=True, slots=True)
class PythonExtensions:
    """Immutable selection of Python-native template functions."""

    re_match: bool = False

    def function_map(self) -> Mapping[str, Callable[..., object]]:
        """Build an immutable function map for the selected extensions."""

        functions: dict[str, Callable[..., object]] = {}
        if self.re_match:
            functions["reMatch"] = _re_match
        return MappingProxyType(functions)


__all__ = ["PythonExtensions"]
