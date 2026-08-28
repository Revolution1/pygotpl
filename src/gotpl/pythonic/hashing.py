"""Python-native cryptographic digest helpers."""

from __future__ import annotations

import hashlib

from .encoding import BytesInput, as_bytes


def hash_digest(algorithm: str, value: BytesInput) -> str:
    """Return a hexadecimal digest using a named ``hashlib`` algorithm."""

    return hashlib.new(algorithm, as_bytes(value)).hexdigest()


def md5(value: BytesInput) -> str:
    return hash_digest("md5", value)


def sha1(value: BytesInput) -> str:
    return hash_digest("sha1", value)


def sha256(value: BytesInput) -> str:
    return hash_digest("sha256", value)


def sha512(value: BytesInput) -> str:
    return hash_digest("sha512", value)


__all__: list[str] = []
