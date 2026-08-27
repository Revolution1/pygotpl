"""Sprig-compatible network helpers with injectable DNS resolution."""

from __future__ import annotations

import random
import socket
from collections.abc import Callable, Sequence

from .randoms import RandBelow

Resolver = Callable[[str], Sequence[str]]


def get_host_by_name(
    name: str,
    *,
    resolver: Resolver | None = None,
    randbelow: RandBelow | None = None,
) -> str:
    lookup = resolver or _resolve_host
    addresses = lookup(name)
    if not addresses:
        raise ValueError("host lookup returned no addresses")
    chooser = randbelow or random.randrange
    return addresses[chooser(len(addresses))]


def _resolve_host(name: str) -> Sequence[str]:
    return socket.gethostbyname_ex(name)[2]
