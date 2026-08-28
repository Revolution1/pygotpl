"""Opt-in extensions backed by Python standard-library behavior."""

from __future__ import annotations

import re
from functools import lru_cache


@lru_cache(maxsize=256)
def _compile_pattern(pattern: str) -> re.Pattern[str]:
    return re.compile(pattern)


def re_match(pattern: str, value: str) -> bool:
    return _compile_pattern(pattern).search(value) is not None


__all__: list[str] = []
