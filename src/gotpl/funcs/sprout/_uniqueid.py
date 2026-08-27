"""Sprout UUID registry implemented with Python's standard library."""

from __future__ import annotations

import secrets
import threading
import time
import uuid

from gotime.go import Time

from gotpl.runtime import FunctionResult

from .registry import TemplateFunction

_NAMESPACES = {
    "dns": uuid.NAMESPACE_DNS,
    "url": uuid.NAMESPACE_URL,
    "oid": uuid.NAMESPACE_OID,
    "x500": uuid.NAMESPACE_X500,
}
_GREGORIAN_TO_UNIX_100NS = 0x01B21DD213814000
_V7_LOCK = threading.Lock()
_last_v7_time = 0


def _parse(value: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except (AttributeError, ValueError) as error:
        raise ValueError(f"invalid UUID {value!r}") from error


def _namespace(value: str) -> uuid.UUID:
    known = _NAMESPACES.get(value.lower())
    if known is not None:
        return known
    try:
        return uuid.UUID(value)
    except (AttributeError, ValueError) as error:
        raise ValueError(
            f"invalid namespace {value!r}: must be one of dns, url, oid, x500 "
            "or a valid UUID"
        ) from error


def _uuid_v4() -> str:
    return str(uuid.uuid4())


def _uuid_v7_value() -> str:
    global _last_v7_time
    nanoseconds = time.time_ns()
    milliseconds, remainder = divmod(nanoseconds, 1_000_000)
    sequence = remainder >> 8
    with _V7_LOCK:
        combined = milliseconds << 12 | sequence
        if combined <= _last_v7_time:
            combined = _last_v7_time + 1
            milliseconds = combined >> 12
            sequence = combined & 0xFFF
        _last_v7_time = combined

    value = bytearray(secrets.token_bytes(16))
    value[0:6] = milliseconds.to_bytes(6, "big")
    value[6] = 0x70 | ((sequence >> 8) & 0x0F)
    value[7] = sequence & 0xFF
    value[8] = (value[8] & 0x3F) | 0x80
    return str(uuid.UUID(bytes=bytes(value)))


def _uuid_v7() -> FunctionResult:
    try:
        return FunctionResult.success(_uuid_v7_value())
    except OSError as error:
        return FunctionResult.failure(error, value="")


def _uuid_v5(namespace: str, name: str) -> FunctionResult:
    try:
        return FunctionResult.success(str(uuid.uuid5(_namespace(namespace), name)))
    except ValueError as error:
        return FunctionResult.failure(error, value="")


def _uuid_v3(namespace: str, name: str) -> FunctionResult:
    try:
        return FunctionResult.success(str(uuid.uuid3(_namespace(namespace), name)))
    except ValueError as error:
        return FunctionResult.failure(error, value="")


def _uuid_nil() -> str:
    return str(uuid.UUID(int=0))


def _is_uuid(value: str) -> bool:
    try:
        _parse(value)
    except ValueError:
        return False
    return True


def _uuid_version(value: str) -> FunctionResult:
    try:
        parsed = _parse(value)
        return FunctionResult.success(parsed.version or 0)
    except ValueError as error:
        return FunctionResult.failure(error, value=0)


def _timestamp_100ns(parsed: uuid.UUID) -> int:
    if parsed.version in {1, 2}:
        return parsed.time
    if parsed.version == 6:
        data = parsed.bytes
        high = int.from_bytes(data[0:6], "big")
        low = (data[6] & 0x0F) << 8 | data[7]
        return high << 12 | low
    raise ValueError(f"uuid version {parsed.version or 0} does not embed a time")


def _uuid_time(value: str) -> FunctionResult:
    try:
        parsed = _parse(value)
        if parsed.version == 7:
            milliseconds = int.from_bytes(parsed.bytes[:6], "big")
            return FunctionResult.success(Time.from_unix_milliseconds(milliseconds))
        timestamp = _timestamp_100ns(parsed) - _GREGORIAN_TO_UNIX_100NS
        seconds, remainder = divmod(timestamp, 10_000_000)
        return FunctionResult.success(Time.from_unix(seconds, remainder * 100))
    except ValueError as error:
        return FunctionResult.failure(error, value=Time.zero())


def functions() -> dict[str, TemplateFunction]:
    """Return the complete pinned Sprout unique-ID function map."""

    return {
        "uuidv4": _uuid_v4,
        "uuidv7": _uuid_v7,
        "uuidv5": _uuid_v5,
        "uuidv3": _uuid_v3,
        "uuidNil": _uuid_nil,
        "isUUID": _is_uuid,
        "uuidVersion": _uuid_version,
        "uuidTime": _uuid_time,
    }
