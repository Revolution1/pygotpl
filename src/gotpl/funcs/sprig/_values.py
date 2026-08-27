"""Internal value adaptations needed to preserve observable Go distinctions."""

from gotpl.runtime import INVALID, UNTYPED_NIL, GoPointer


class NilSlice(list[object]):
    """Represent a typed nil Go slice while retaining normal list behavior."""


def go_kind_of(value: object) -> str:
    """Return the Go reflection kind used by Sprig's Python value adaptation."""

    if value is INVALID or value is UNTYPED_NIL or value is None:
        return "invalid"
    if isinstance(value, GoPointer):
        return "ptr"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float64"
    if isinstance(value, complex):
        return "complex128"
    if isinstance(value, str):
        return "string"
    if isinstance(value, (bytes, bytearray, list, tuple)):
        return "slice"
    if isinstance(value, dict):
        return "map"
    if callable(value):
        return "func"
    return "struct"
