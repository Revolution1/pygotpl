"""Selection and assembly of Python-native function categories."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal, TypeAlias

from .compression import (
    bz2_compress,
    bz2_decompress,
    gzip_compress,
    gzip_decompress,
    lzma_compress,
    lzma_decompress,
    zlib_compress,
    zlib_decompress,
)
from .encoding import (
    b64decode,
    b64encode,
    hex_decode,
    hex_encode,
    utf8_decode,
    utf8_encode,
)
from .hashing import hash_digest, md5, sha1, sha256, sha512
from .regex import re_match
from .text import pformat, py_print

PythonExtensionCategory: TypeAlias = Literal[
    "regex", "text", "encoding", "hashing", "compression"
]
PythonExtensionProfile: TypeAlias = Literal["common", "all"]

_CATEGORY_NAMES = frozenset({"regex", "text", "encoding", "hashing", "compression"})
_COMMON_CATEGORIES: tuple[PythonExtensionCategory, ...] = (
    "text",
    "encoding",
    "hashing",
    "compression",
)


@dataclass(frozen=True, slots=True)
class PythonExtensions:
    """Immutable selection of Python-native template function categories."""

    re_match: bool = False
    text: bool = False
    encoding: bool = False
    hashing: bool = False
    compression: bool = False

    @classmethod
    def from_categories(cls, *categories: PythonExtensionCategory) -> PythonExtensions:
        """Select one or more independent Python standard-library categories."""

        unknown = sorted(set(categories) - _CATEGORY_NAMES)
        if unknown:
            raise ValueError(
                "unknown Python extension category: "
                + ", ".join(unknown)
                + "; expected one of compression, encoding, hashing, regex, text"
            )
        selected = set(categories)
        return cls(
            re_match="regex" in selected,
            text="text" in selected,
            encoding="encoding" in selected,
            hashing="hashing" in selected,
            compression="compression" in selected,
        )

    @classmethod
    def common(cls) -> PythonExtensions:
        """Enable common helpers, excluding Python's backtracking regex."""

        return cls.from_categories(*_COMMON_CATEGORIES)

    @classmethod
    def all(cls) -> PythonExtensions:
        """Enable every category, including Python's backtracking regex."""

        return cls.from_categories(*_COMMON_CATEGORIES, "regex")

    def function_map(self) -> Mapping[str, Callable[..., object]]:
        """Build an immutable function map for the selected extensions."""

        functions: dict[str, Callable[..., object]] = {}
        if self.re_match:
            functions["reMatch"] = re_match
        if self.text:
            functions.update({"pyPrint": py_print, "pformat": pformat})
        if self.encoding:
            functions.update(
                {
                    "utf8Encode": utf8_encode,
                    "utf8Decode": utf8_decode,
                    "b64encode": b64encode,
                    "b64decode": b64decode,
                    "hexEncode": hex_encode,
                    "hexDecode": hex_decode,
                }
            )
        if self.hashing:
            functions.update(
                {
                    "hashDigest": hash_digest,
                    "md5": md5,
                    "sha1": sha1,
                    "sha256": sha256,
                    "sha512": sha512,
                }
            )
        if self.compression:
            functions.update(
                {
                    "gzipCompress": gzip_compress,
                    "gzipDecompress": gzip_decompress,
                    "zlibCompress": zlib_compress,
                    "zlibDecompress": zlib_decompress,
                    "bz2Compress": bz2_compress,
                    "bz2Decompress": bz2_decompress,
                    "lzmaCompress": lzma_compress,
                    "lzmaDecompress": lzma_decompress,
                }
            )
        return MappingProxyType(functions)


def resolve_python_extensions(
    selection: PythonExtensions
    | PythonExtensionProfile
    | tuple[PythonExtensionCategory, ...]
    | None,
) -> PythonExtensions:
    """Normalize the convenient high-level environment selection forms."""

    if selection is None:
        return PythonExtensions()
    if isinstance(selection, PythonExtensions):
        return selection
    if selection == "common":
        return PythonExtensions.common()
    if selection == "all":
        return PythonExtensions.all()
    if isinstance(selection, str):
        return PythonExtensions.from_categories(selection)  # type: ignore[arg-type]
    return PythonExtensions.from_categories(*selection)


__all__ = [
    "PythonExtensionCategory",
    "PythonExtensionProfile",
    "PythonExtensions",
]
