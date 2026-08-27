from __future__ import annotations

import pytest

from gotpl import Template, TemplateExecutionError
from gotpl.funcs.sprout import Handler, registry

_SOURCE = (
    '{{$d := dict "a" 1 "nested" (dict "x" 2) "a.b" 3}}'
    '{{$d | get "a"}}|{{$d | hasKey "missing"}}|{{$d | pick "a"}}|'
    '{{$d | omit "nested"}}|{{$d | dig "nested.x"}}|{{$d | dig `a\\.b`}}|'
    '{{$d | set "z" 9}}|{{$d | unset "a"}}|'
    '{{merge (dict "a" 1) (dict "a" 2 "b" 3)}}|'
    '{{mergeOverwrite (dict "a" 1) (dict "a" 2 "b" 3)}}'
)


def test_maps_registry_uses_sprout_pipeline_signatures_and_dotted_dig() -> None:
    functions = Handler(registry("maps")).build()

    assert Template(_SOURCE, functions=functions).render() == (
        "1|false|map[a:1]|map[a:1 a.b:3]|2|3|"
        "map[a:1 a.b:3 nested:map[x:2] z:9]|"
        "map[a.b:3 nested:map[x:2] z:9]|map[a:1 b:3]|map[a:2 b:3]"
    )


@pytest.mark.parametrize(
    ("expression", "message"),
    [
        ('pick "a" "not a map"', "last argument must be a map"),
        ('dig "a..b" (dict "a" 1)', "empty key segment"),
        ('dig 1 (dict "a" 1)', "all keys must be strings"),
    ],
)
def test_maps_registry_reports_sprout_argument_errors(
    expression: str, message: str
) -> None:
    functions = Handler(registry("maps")).build()
    with pytest.raises(TemplateExecutionError, match=message):
        Template("{{" + expression + "}}", functions=functions).render()
