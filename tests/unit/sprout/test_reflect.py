from __future__ import annotations

from dataclasses import dataclass

from gotpl import Template
from gotpl.funcs.sprout import Handler, registry


@dataclass
class Example:
    name: str


def test_reflect_registry_matches_sprout_for_mapping_values() -> None:
    functions = Handler(registry("reflect")).build()
    source = (
        '{{typeOf .}}|{{kindOf .}}|{{typeIs "map[string]interface {}" .}}|'
        '{{typeIsLike "map[string]interface {}" .}}|{{kindIs "map" .}}|'
        "{{deepEqual . .}}|{{deepCopy .}}"
    )

    assert Template(source, functions=functions).render({"a": 1}) == (
        "map[string]interface {}|map|true|true|true|true|map[a:1]"
    )


def test_has_field_adapts_python_objects_without_treating_maps_as_structs() -> None:
    functions = Handler(registry("reflect")).build()
    template = Template(
        '{{hasField "name" .Object}}|{{hasField "missing" .Object}}',
        functions=functions,
    )

    assert template.render({"Object": Example("value")}) == "true|false"
