"""Awaitable handling shared by template runtimes."""

from collections.abc import Awaitable, Coroutine
from inspect import isawaitable
from typing import Any, TypeGuard, cast

from gotpl.errors import AsyncRequiredError

_COMMON_NON_AWAITABLE_TYPES = frozenset(
    {
        bool,
        bytearray,
        bytes,
        complex,
        dict,
        float,
        frozenset,
        int,
        list,
        set,
        str,
        tuple,
        type(None),
    }
)


def is_awaitable(value: object) -> TypeGuard[Awaitable[object]]:
    """Return whether a runtime value implements the await protocol."""

    if type(value) in _COMMON_NON_AWAITABLE_TYPES:
        return False
    return isawaitable(value)


def reject_awaitable(value: object) -> object:
    """Reject an awaitable on the synchronous path and close coroutines safely."""

    if not is_awaitable(value):
        return value
    if isinstance(value, Coroutine):
        cast(Coroutine[Any, Any, object], value).close()
    raise AsyncRequiredError(
        "an awaitable was produced during synchronous rendering; use render_async"
    )
