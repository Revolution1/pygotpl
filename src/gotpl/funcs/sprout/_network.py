"""Sprout network registry built on Python's address primitives."""

from __future__ import annotations

import ipaddress
import re
from collections.abc import Callable
from typing import TypeAlias

from gotpl.runtime import FunctionResult

from .registry import TemplateFunction

_Address: TypeAlias = ipaddress.IPv4Address | ipaddress.IPv6Address
_Network: TypeAlias = ipaddress.IPv4Network | ipaddress.IPv6Network
_PRIVATE_NETWORKS: tuple[_Network, ...] = (
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("fc00::/7"),
)


def _result(operation: Callable[[], object], default: object) -> FunctionResult:
    try:
        return FunctionResult.success(operation())
    except ValueError as error:
        return FunctionResult.failure(error, value=default)


def _address(value: str) -> _Address:
    try:
        return ipaddress.ip_address(value)
    except ValueError as error:
        raise ValueError("invalid IP address") from error


def _network(value: str) -> _Network:
    try:
        return ipaddress.ip_network(value, strict=False)
    except ValueError as error:
        raise ValueError(f"cannot parse CIDR: invalid CIDR address: {value}") from error


def _parse_ip(value: str) -> FunctionResult:
    return _result(lambda: str(_address(value)), None)


def _canonical_mac(value: str) -> str:
    if re.fullmatch(r"[0-9A-Fa-f]{4}(?:\.[0-9A-Fa-f]{4}){2}", value):
        digits = value.replace(".", "")
    elif re.fullmatch(
        r"[0-9A-Fa-f]{2}(?P<separator>[:-])"
        r"(?:[0-9A-Fa-f]{2}(?P=separator)){4}[0-9A-Fa-f]{2}",
        value,
    ):
        digits = value.replace(":", "").replace("-", "")
    else:
        raise ValueError("cannot parse MAC address: invalid MAC address")
    return ":".join(digits[index : index + 2].lower() for index in range(0, 12, 2))


def _parse_mac(value: str) -> FunctionResult:
    return _result(lambda: _canonical_mac(value), None)


def _parse_cidr(value: str) -> FunctionResult:
    return _result(lambda: str(_network(value)), None)


def _ip_version(value: str) -> FunctionResult:
    return _result(lambda: _address(value).version, 0)


def _ip_loopback(value: str) -> FunctionResult:
    return _result(lambda: _address(value).is_loopback, False)


def _global_unicast(address: _Address) -> bool:
    return not (
        address.is_unspecified
        or address.is_loopback
        or address.is_multicast
        or address.is_link_local
        or int(address) == (1 << address.max_prefixlen) - 1
    )


def _ip_global_unicast(value: str) -> FunctionResult:
    return _result(lambda: _global_unicast(_address(value)), False)


def _ip_multicast(value: str) -> FunctionResult:
    return _result(lambda: _address(value).is_multicast, False)


def _private(address: _Address) -> bool:
    return any(
        address.version == network.version and address in network
        for network in _PRIVATE_NETWORKS
    )


def _ip_private(value: str) -> FunctionResult:
    return _result(lambda: _private(_address(value)), False)


def _increment_value(value: str) -> str:
    address = _address(value)
    maximum = (1 << address.max_prefixlen) - 1
    if int(address) == maximum:
        raise ValueError("ip increment overflow")
    return str(ipaddress.ip_address(int(address) + 1))


def _ip_increment(value: str) -> FunctionResult:
    return _result(lambda: _increment_value(value), None)


def _decrement_value(value: str) -> str:
    address = _address(value)
    if int(address) == 0:
        raise ValueError("ip decrement underflow")
    return str(ipaddress.ip_address(int(address) - 1))


def _ip_decrement(value: str) -> FunctionResult:
    return _result(lambda: _decrement_value(value), None)


def _cidr_contains(cidr: str, value: str) -> FunctionResult:
    def contains() -> bool:
        network = _network(cidr)
        address = _address(value)
        return address.version == network.version and address in network

    return _result(contains, False)


def _cidr_size(cidr: str) -> FunctionResult:
    return _result(lambda: _network(cidr).num_addresses, None)


def _cidr_range_list(cidr: str) -> FunctionResult:
    try:
        network = _network(cidr)
    except ValueError as error:
        return FunctionResult.failure(
            ValueError(f"invalid CIDR block: {error}"), value=None
        )
    start = int(network.network_address)
    return FunctionResult.success(
        [
            str(ipaddress.ip_address(start + offset))
            for offset in range(network.num_addresses)
        ]
    )


def _cidr_first(cidr: str) -> FunctionResult:
    return _result(lambda: str(_network(cidr).network_address), "")


def _cidr_last(cidr: str) -> FunctionResult:
    return _result(lambda: str(_network(cidr).broadcast_address), "")


def _overlap(left: str, right: str) -> bool:
    first = _network(left)
    second = _network(right)
    return first.version == second.version and first.overlaps(second)


def _cidr_overlap(left: str, right: str) -> FunctionResult:
    return _result(lambda: _overlap(left, right), False)


def functions() -> dict[str, TemplateFunction]:
    """Return the complete pinned Sprout network function map."""

    return {
        "parseIP": _parse_ip,
        "parseMAC": _parse_mac,
        "parseCIDR": _parse_cidr,
        "ipVersion": _ip_version,
        "ipIsLoopback": _ip_loopback,
        "ipIsGlobalUnicast": _ip_global_unicast,
        "ipIsMulticast": _ip_multicast,
        "ipIsPrivate": _ip_private,
        "ipIncrement": _ip_increment,
        "ipDecrement": _ip_decrement,
        "cidrContains": _cidr_contains,
        "cidrSize": _cidr_size,
        "cidrRangeList": _cidr_range_list,
        "cidrFirst": _cidr_first,
        "cidrLast": _cidr_last,
        "cidrOverlap": _cidr_overlap,
    }
