"""Sprig reflection helpers adapted to Python values."""

from gotpl.runtime.gofmt import sprintf

from ._values import go_kind_of
from .lists import deep_equal_value


def type_of(value: object) -> str:
    return sprintf("%T", value)


def type_is(target: str, value: object) -> bool:
    return target == type_of(value)


def type_is_like(target: str, value: object) -> bool:
    actual = type_of(value)
    return target == actual or "*" + target == actual


def kind_of(value: object) -> str:
    return go_kind_of(value)


def kind_is(target: str, value: object) -> bool:
    return target == kind_of(value)


def deep_equal(left: object, right: object) -> bool:
    return deep_equal_value(left, right)
