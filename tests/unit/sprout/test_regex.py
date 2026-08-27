from __future__ import annotations

from gotpl.funcs.sprout import Handler, registry
from gotpl.runtime import FunctionResult


def _unwrap(result: object) -> object:
    assert isinstance(result, FunctionResult)
    assert result.error is None
    return result.value


def test_regex_registry_exposes_sprout_v111_signatures_and_groups() -> None:
    functions = Handler(registry("regex")).build()
    value = "a=1 b=2"

    assert _unwrap(functions["regexFind"](r"\w+=\w+", value)) == "a=1"
    assert _unwrap(functions["regexFindAll"](r"\w+=\w+", 1, value)) == ["a=1"]
    assert _unwrap(functions["regexMatch"](r"^a", value)) is True
    assert _unwrap(functions["regexSplit"](r"\s+", -1, value)) == ["a=1", "b=2"]
    assert _unwrap(functions["regexReplaceAll"](r"(\w+)=(\w+)", "$2:$1", value)) == (
        "1:a 2:b"
    )
    assert (
        _unwrap(functions["regexReplaceAllLiteral"](r"\w+", "$1", value))
        == "$1=$1 $1=$1"
    )
    assert functions["regexQuoteMeta"]("a+b") == r"a\+b"
    assert _unwrap(functions["regexFindGroups"](r"(\w+)=(\w+)", value)) == [
        "a=1",
        "a",
        "1",
    ]
    assert _unwrap(functions["regexFindAllGroups"](r"(\w+)=(\w+)", -1, value)) == [
        ["a=1", "a", "1"],
        ["b=2", "b", "2"],
    ]
    assert _unwrap(
        functions["regexFindNamed"](r"(?P<key>\w+)=(?P<value>\w+)", value)
    ) == {"key": "a", "value": "1"}
    assert _unwrap(
        functions["regexFindAllNamed"](r"(?P<key>\w+)=(?P<value>\w+)", -1, value)
    ) == [{"key": "a", "value": "1"}, {"key": "b", "value": "2"}]


def test_regex_registry_returns_compile_errors_as_function_results() -> None:
    functions = Handler(registry("regex")).build()

    result = functions["regexFind"]("[", "value")
    assert isinstance(result, FunctionResult)
    assert result.value == ""
    assert result.error is not None


def test_deprecated_regexp_registry_preserves_old_argument_order_and_aliases() -> None:
    functions = Handler(registry("regexp")).build()

    assert _unwrap(functions["regexFindAll"]("a", "banana", 2)) == ["a", "a"]
    assert _unwrap(functions["regexSplit"]("a", "banana", 2)) == ["b", "nana"]
    assert _unwrap(functions["regexReplaceAll"]("a", "banana", "x")) == "bxnxnx"
    assert _unwrap(functions["mustRegexFindAll"]("a", "banana", 2)) == ["a", "a"]
    assert functions["mustRegexFindAll"] is not functions["regexFindAll"]
