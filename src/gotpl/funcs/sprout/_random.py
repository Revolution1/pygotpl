"""Sprout random registry using the matching Python entropy sources."""

from __future__ import annotations

import base64
import random
import secrets
import string

from gotpl.runtime import FunctionResult

from .registry import TemplateFunction

_ALPHABETIC = string.ascii_lowercase + string.ascii_uppercase
_ALPHANUMERIC = _ALPHABETIC + string.digits
_ASCII = "".join(chr(value) for value in range(32, 127))


def _random_string(size: int, alphabet: str) -> str:
    if size <= 0:
        return ""
    return "".join(secrets.choice(alphabet) for _ in range(size))


def _alpha_numeric(size: int) -> str:
    return _random_string(size, _ALPHANUMERIC)


def _alpha(size: int) -> str:
    return _random_string(size, _ALPHABETIC)


def _ascii(size: int) -> str:
    return _random_string(size, _ASCII)


def _numeric(size: int) -> str:
    return _random_string(size, string.digits)


def _bytes(size: int) -> FunctionResult:
    if size <= 0:
        return FunctionResult.success("")
    return FunctionResult.success(base64.b64encode(secrets.token_bytes(size)).decode())


def _integer(minimum: int, maximum: int) -> int:
    return random.randrange(minimum, maximum)


def functions() -> dict[str, TemplateFunction]:
    """Return the complete pinned Sprout random function map."""

    return {
        "randAlphaNum": _alpha_numeric,
        "randAlpha": _alpha,
        "randAscii": _ascii,
        "randNumeric": _numeric,
        "randBytes": _bytes,
        "randInt": _integer,
    }
