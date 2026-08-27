from contextlib import suppress

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from gotpl.errors import TemplateSyntaxError
from gotpl.parse import IfNode, parse


@given(st.text(alphabet=st.characters(blacklist_categories=("Cs",)), max_size=300))
@settings(
    max_examples=300,
    deadline=None,
    suppress_health_check=(HealthCheck.too_slow,),
)
def test_arbitrary_unicode_input_parses_or_raises_a_controlled_error(
    source: str,
) -> None:
    with suppress(TemplateSyntaxError):
        parse(source)


@given(st.integers(min_value=0, max_value=40))
@settings(max_examples=41, deadline=None)
def test_valid_nested_if_templates_preserve_their_depth(depth: int) -> None:
    source = "{{if .}}" * depth + "value" + "{{end}}" * depth
    root = parse(source)
    node = root.nodes[0]
    observed = 0
    while isinstance(node, IfNode):
        observed += 1
        node = node.body.nodes[0]
    assert observed == depth


def test_extreme_parenthesis_nesting_raises_a_controlled_error() -> None:
    source = "{{" + "(" * 2_000 + "." + ")" * 2_000 + "}}"
    with pytest.raises(TemplateSyntaxError, match="nesting limit"):
        parse(source)


def test_lone_surrogates_raise_a_controlled_error() -> None:
    with pytest.raises(TemplateSyntaxError, match="invalid Unicode"):
        parse("valid\ud800tail")
