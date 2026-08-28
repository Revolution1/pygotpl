"""Python-native byte and text encoding helpers."""

from __future__ import annotations

import base64
import binascii

BytesInput = str | bytes | bytearray | memoryview


def as_bytes(value: BytesInput) -> bytes:
    """Adapt UTF-8 text and Python bytes-like values to immutable bytes."""

    if isinstance(value, str):
        return value.encode()
    return bytes(value)


def utf8_encode(value: str) -> bytes:
    return value.encode()


def utf8_decode(value: BytesInput) -> str:
    if isinstance(value, str):
        return value
    return bytes(value).decode()


def b64encode(value: BytesInput) -> str:
    return base64.b64encode(as_bytes(value)).decode("ascii")


def b64decode(value: BytesInput) -> bytes:
    return base64.b64decode(as_bytes(value), validate=True)


def hex_encode(value: BytesInput) -> str:
    return binascii.hexlify(as_bytes(value)).decode("ascii")


def hex_decode(value: BytesInput) -> bytes:
    return binascii.unhexlify(as_bytes(value))


__all__: list[str] = []
