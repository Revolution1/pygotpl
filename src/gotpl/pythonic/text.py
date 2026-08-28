"""Python-native text formatting helpers."""

from __future__ import annotations

from pprint import pformat as _pformat


def py_print(*values: object) -> str:
    """Return values joined with Python's ``str`` conversion."""

    return " ".join(str(value) for value in values)


def pformat(value: object) -> str:
    """Return a deterministic, width-aware pretty representation."""

    return _pformat(value, sort_dicts=False)


__all__: list[str] = []
