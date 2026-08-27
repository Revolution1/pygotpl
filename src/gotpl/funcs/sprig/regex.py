# pyright: reportPrivateUsage=false
"""Sprig adapters for the private narrow RE2-compatible engine."""

from __future__ import annotations

import re
from collections.abc import Callable

from gotpl._compat.goregexp import go as _go
from gotpl.runtime import FunctionResult

_compile = _go._compile


def regex_match(pattern: str, value: str) -> bool:
    return _go.regex_match(pattern, value)


def must_regex_match(pattern: str, value: str) -> FunctionResult:
    return _must(lambda: _compile(pattern).search(value) is not None)


def regex_find_all(pattern: str, value: str, count: int) -> list[str] | None:
    return _go.regex_find_all(pattern, value, count)


def must_regex_find_all(pattern: str, value: str, count: int) -> FunctionResult:
    return _must(lambda: regex_find_all(pattern, value, count))


def regex_find(pattern: str, value: str) -> str:
    return _go.regex_find(pattern, value)


def must_regex_find(pattern: str, value: str) -> FunctionResult:
    return _must(lambda: regex_find(pattern, value))


def regex_replace_all(pattern: str, value: str, replacement: str) -> str:
    return _go.regex_replace_all(pattern, value, replacement)


def must_regex_replace_all(
    pattern: str, value: str, replacement: str
) -> FunctionResult:
    return _must(lambda: regex_replace_all(pattern, value, replacement))


def regex_replace_all_literal(pattern: str, value: str, replacement: str) -> str:
    return _go.regex_replace_all_literal(pattern, value, replacement)


def must_regex_replace_all_literal(
    pattern: str, value: str, replacement: str
) -> FunctionResult:
    return _must(lambda: regex_replace_all_literal(pattern, value, replacement))


def regex_split(pattern: str, value: str, count: int) -> list[str]:
    return _go.regex_split(pattern, value, count)


def must_regex_split(pattern: str, value: str, count: int) -> FunctionResult:
    return _must(lambda: regex_split(pattern, value, count))


def regex_quote_meta(value: str) -> str:
    return _go.regex_quote_meta(value)


def _must(operation: Callable[[], object]) -> FunctionResult:
    try:
        return FunctionResult.success(operation())
    except re.error as error:
        return FunctionResult.failure(error)
