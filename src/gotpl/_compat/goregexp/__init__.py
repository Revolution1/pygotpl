"""Private narrow Go-compatible regular-expression support."""

from .go import Pattern, RegexpError, compile, quote_meta
from .types import DEFAULT_LIMITS, Limits

__all__ = [
    "DEFAULT_LIMITS",
    "Limits",
    "Pattern",
    "RegexpError",
    "compile",
    "quote_meta",
]
