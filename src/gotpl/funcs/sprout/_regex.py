"""Sprout regex and deprecated regexp registries."""

from __future__ import annotations

from collections.abc import Callable

from gotpl._compat.goregexp.go import Pattern, RegexpError, compile, quote_meta
from gotpl.runtime import FunctionResult

from .registry import TemplateFunction


def _result(operation: Callable[[], object], default: object) -> FunctionResult:
    try:
        return FunctionResult.success(operation())
    except RegexpError as error:
        return FunctionResult.failure(
            ValueError(f"error parsing regexp: {error}"), value=default
        )


def _pattern(source: str) -> Pattern:
    return compile(source)


def _find(source: str, value: str) -> FunctionResult:
    return _result(lambda: _pattern(source).find(value), "")


def _find_all(source: str, count: int, value: str) -> FunctionResult:
    return _result(lambda: _pattern(source).find_all(value, count) or [], [])


def _match(source: str, value: str) -> FunctionResult:
    return _result(lambda: _pattern(source).matches(value), False)


def _split(source: str, count: int, value: str) -> FunctionResult:
    return _result(lambda: _pattern(source).split(value, count), [])


def _replace(source: str, replacement: str, value: str) -> FunctionResult:
    return _result(lambda: _pattern(source).replace_all(value, replacement), "")


def _replace_literal(source: str, replacement: str, value: str) -> FunctionResult:
    return _result(lambda: _pattern(source).replace_all_literal(value, replacement), "")


def _find_groups(source: str, value: str) -> FunctionResult:
    return _result(lambda: _pattern(source).find_groups(value), [])


def _find_all_groups(source: str, count: int, value: str) -> FunctionResult:
    return _result(lambda: _pattern(source).find_all_groups(value, count), [])


def _find_named(source: str, value: str) -> FunctionResult:
    return _result(lambda: _pattern(source).find_named(value), {})


def _find_all_named(source: str, count: int, value: str) -> FunctionResult:
    return _result(lambda: _pattern(source).find_all_named(value, count), [])


def regex_functions() -> dict[str, TemplateFunction]:
    """Return the current Sprout regex registry with v1.1.1 argument order."""

    return {
        "regexFind": _find,
        "regexFindAll": _find_all,
        "regexMatch": _match,
        "regexSplit": _split,
        "regexReplaceAll": _replace,
        "regexReplaceAllLiteral": _replace_literal,
        "regexQuoteMeta": quote_meta,
        "regexFindGroups": _find_groups,
        "regexFindAllGroups": _find_all_groups,
        "regexFindNamed": _find_named,
        "regexFindAllNamed": _find_all_named,
    }


def _old_find_all(source: str, value: str, count: int) -> FunctionResult:
    return _find_all(source, count, value)


def _old_split(source: str, value: str, count: int) -> FunctionResult:
    return _split(source, count, value)


def _old_replace(source: str, value: str, replacement: str) -> FunctionResult:
    return _replace(source, replacement, value)


def _old_replace_literal(source: str, value: str, replacement: str) -> FunctionResult:
    return _replace_literal(source, replacement, value)


def regexp_functions() -> dict[str, TemplateFunction]:
    """Return the deprecated registry with its pre-v1.2 argument order."""

    functions = regex_functions()
    functions.update(
        {
            "regexFindAll": _old_find_all,
            "regexSplit": _old_split,
            "regexReplaceAll": _old_replace,
            "regexReplaceAllLiteral": _old_replace_literal,
        }
    )
    return functions
