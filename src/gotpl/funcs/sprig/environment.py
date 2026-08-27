"""Sprig-compatible environment helpers."""

from __future__ import annotations

import os
from collections.abc import Mapping


def env(name: str, *, environ: Mapping[str, str] | None = None) -> str:
    source = os.environ if environ is None else environ
    return source.get(name, "")


def expand_env(value: str, *, environ: Mapping[str, str] | None = None) -> str:
    source = os.environ if environ is None else environ
    output: list[str] = []
    index = 0
    while index < len(value):
        if value[index] != "$" or index + 1 >= len(value):
            output.append(value[index])
            index += 1
            continue
        name, width = _shell_name(value[index + 1 :])
        if name:
            output.append(source.get(name, ""))
        elif width == 0:
            output.append("$")
        index += width + 1
    return "".join(output)


def _shell_name(value: str) -> tuple[str, int]:
    if value[0] == "{":
        if len(value) > 2 and _is_special(value[1]) and value[2] == "}":
            return value[1], 3
        closing = value.find("}", 1)
        if closing == 1:
            return "", 2
        if closing > 1:
            return value[1:closing], closing + 1
        return "", 1
    if _is_special(value[0]):
        return value[0], 1
    width = 0
    while width < len(value) and (
        value[width] == "_" or (value[width].isascii() and value[width].isalnum())
    ):
        width += 1
    return value[:width], width


def _is_special(value: str) -> bool:
    return value in "*#$@!?-0123456789"
