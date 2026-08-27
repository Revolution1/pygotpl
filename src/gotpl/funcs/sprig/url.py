"""Sprig URL parsing and joining helpers."""

from __future__ import annotations

import re
from urllib.parse import quote, unquote, urlsplit, urlunsplit

from .reflect import kind_of


def url_parse(value: str) -> dict[str, object]:
    _validate_percent_encoding(value)
    parsed = urlsplit(value)
    opaque = ""
    path = unquote(parsed.path)
    if parsed.scheme and not value[len(parsed.scheme) + 1 :].startswith("/"):
        opaque = path
        path = ""
    raw_authority = parsed.netloc
    userinfo, separator, host = raw_authority.rpartition("@")
    if not separator:
        userinfo, host = "", raw_authority
    host = _decode_host(host)
    return {
        "scheme": parsed.scheme,
        "host": host,
        "hostname": _hostname(host),
        "path": path,
        "query": parsed.query,
        "opaque": opaque,
        "fragment": unquote(parsed.fragment),
        "userinfo": userinfo,
    }


def url_join(value: dict[str, object]) -> str:
    components = {
        key: _string_component(value, key)
        for key in ("scheme", "host", "path", "query", "opaque", "fragment")
    }
    userinfo = _string_component(value, "userinfo")
    authority = _encode_host(components["host"])
    if userinfo:
        encoded_userinfo = _encode_userinfo(userinfo)
        if encoded_userinfo:
            authority = f"{encoded_userinfo}@{authority}"
    if components["opaque"]:
        result = components["opaque"]
        if components["scheme"]:
            result = f"{components['scheme']}:{result}"
        if components["query"]:
            result += "?" + components["query"]
        if components["fragment"]:
            result += "#" + _encode_fragment(components["fragment"])
        return result
    encoded_path = quote(components["path"], safe="/;,:@&=+$-_.!~*'()")
    result = urlunsplit(
        (
            components["scheme"],
            authority,
            encoded_path,
            components["query"],
            "",
        )
    )
    if (
        not components["scheme"]
        and not authority
        and ":" in encoded_path.partition("/")[0]
    ):
        result = "./" + result
    if components["fragment"]:
        result += "#" + _encode_fragment(components["fragment"])
    return result


def _string_component(value: dict[str, object], key: str) -> str:
    component = value.get(key, "")
    if not isinstance(component, str):
        raise TypeError(
            f"unable to parse {key} key, must be of type string, "
            f"but {kind_of(component)} found"
        )
    return component


def _encode_userinfo(value: str) -> str:
    invalid = re.search(r"%(?![0-9A-Fa-f]{2})", value)
    temporary = f"proto://{value}@host"
    if invalid is not None:
        escape = value[invalid.start() : invalid.start() + 3]
        raise ValueError(
            f'unable to parse userinfo in dict: parse "{temporary}": '
            f'invalid URL escape "{escape}"'
        )
    parsed = urlsplit(temporary)
    userinfo, separator, _host = parsed.netloc.rpartition("@")
    if not separator:
        return ""
    return quote(unquote(userinfo), safe=":")


def _encode_fragment(value: str) -> str:
    return quote(value, safe="/?:@&=+$-_.!~*'()")


def _decode_host(host: str) -> str:
    if "%" not in host:
        return host
    if host.startswith("[") and "%25" in host:
        return unquote(host)
    raise ValueError("unable to parse url: invalid URL escape in host")


def _encode_host(host: str) -> str:
    return quote(host, safe="!$&'()*+,-.:;=[]_~")


def _hostname(host: str) -> str:
    if host.startswith("["):
        closing = host.find("]")
        return unquote(host[1:closing]) if closing >= 0 else host
    if host.count(":") == 1:
        return host.rsplit(":", 1)[0]
    return host


def _validate_percent_encoding(value: str) -> None:
    if any(ord(character) < 0x20 or ord(character) == 0x7F for character in value):
        raise ValueError("unable to parse url: invalid control character in URL")
    invalid = re.search(r"%(?![0-9A-Fa-f]{2})", value)
    if invalid is not None:
        raise ValueError(
            f"unable to parse url: invalid URL escape at byte {invalid.start()}"
        )
