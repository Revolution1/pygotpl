from __future__ import annotations

from gotpl.funcs.sprout import Handler, registry
from gotpl.runtime import FunctionResult


def _unwrap(result: object) -> object:
    assert isinstance(result, FunctionResult)
    assert result.error is None
    return result.value


def test_network_registry_covers_ip_mac_and_cidr_operations() -> None:
    functions = Handler(registry("network")).build()

    assert _unwrap(functions["parseIP"]("10.42.0.1")) == "10.42.0.1"
    assert _unwrap(functions["parseIP"]("2001:0db8::1")) == "2001:db8::1"
    assert _unwrap(functions["parseMAC"]("01-23-45-67-89-AB")) == ("01:23:45:67:89:ab")
    assert _unwrap(functions["parseCIDR"]("10.42.1.2/16")) == "10.42.0.0/16"
    assert _unwrap(functions["ipVersion"]("10.42.0.1")) == 4
    assert _unwrap(functions["ipVersion"]("2001:db8::1")) == 6
    assert _unwrap(functions["ipIsLoopback"]("127.0.0.1")) is True
    assert _unwrap(functions["ipIsGlobalUnicast"]("8.8.8.8")) is True
    assert _unwrap(functions["ipIsMulticast"]("ff02::1")) is True
    assert _unwrap(functions["ipIsPrivate"]("fd00::1")) is True
    assert _unwrap(functions["ipIncrement"]("10.42.0.255")) == "10.42.1.0"
    assert _unwrap(functions["ipDecrement"]("2001:db8::1:0")) == "2001:db8::ffff"
    assert _unwrap(functions["cidrContains"]("10.42.0.0/16", "10.42.1.1")) is True
    assert _unwrap(functions["cidrSize"]("2001:db8::/120")) == 256
    assert _unwrap(functions["cidrRangeList"]("10.42.0.1/30")) == [
        "10.42.0.0",
        "10.42.0.1",
        "10.42.0.2",
        "10.42.0.3",
    ]
    assert _unwrap(functions["cidrFirst"]("10.42.1.1/16")) == "10.42.0.0"
    assert _unwrap(functions["cidrLast"]("2001:db8::1/120")) == "2001:db8::ff"
    assert _unwrap(functions["cidrOverlap"]("10.42.1.0/24", "10.42.0.0/16")) is True


def test_network_registry_preserves_errors_and_address_bounds() -> None:
    functions = Handler(registry("network")).build()

    for name, arguments, message in (
        ("parseIP", ("invalid",), "invalid IP address"),
        ("parseMAC", ("invalid",), "cannot parse MAC address"),
        ("parseCIDR", ("invalid",), "cannot parse CIDR"),
        ("ipIncrement", ("255.255.255.255",), "ip increment overflow"),
        ("ipDecrement", ("::",), "ip decrement underflow"),
    ):
        result = functions[name](*arguments)
        assert isinstance(result, FunctionResult)
        assert result.error is not None
        assert message in str(result.error)
