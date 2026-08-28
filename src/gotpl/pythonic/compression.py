"""Python-native in-memory compression helpers."""

from __future__ import annotations

import bz2
import gzip
import lzma
import zlib

from .encoding import BytesInput, as_bytes


def gzip_compress(value: BytesInput) -> bytes:
    return gzip.compress(as_bytes(value), mtime=0)


def gzip_decompress(value: BytesInput) -> bytes:
    return gzip.decompress(as_bytes(value))


def zlib_compress(value: BytesInput) -> bytes:
    return zlib.compress(as_bytes(value))


def zlib_decompress(value: BytesInput) -> bytes:
    return zlib.decompress(as_bytes(value))


def bz2_compress(value: BytesInput) -> bytes:
    return bz2.compress(as_bytes(value))


def bz2_decompress(value: BytesInput) -> bytes:
    return bz2.decompress(as_bytes(value))


def lzma_compress(value: BytesInput) -> bytes:
    return lzma.compress(as_bytes(value))


def lzma_decompress(value: BytesInput) -> bytes:
    return lzma.decompress(as_bytes(value))


__all__: list[str] = []
