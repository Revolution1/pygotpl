"""Immutable chart files used by the example Helm runtime."""

from __future__ import annotations

import base64
import fnmatch
import posixpath
from collections.abc import Iterator, Mapping
from types import MappingProxyType


class HelmFiles(Mapping[str, bytes]):
    """An immutable chart-file mapping with Helm's template methods."""

    __slots__ = ("_files",)

    def __init__(self, files: Mapping[str, str | bytes] | None = None) -> None:
        self._files = MappingProxyType(
            {
                name: value.encode() if isinstance(value, str) else bytes(value)
                for name, value in (files or {}).items()
            }
        )

    def __getitem__(self, name: str) -> bytes:
        return self._files[name]

    def __iter__(self) -> Iterator[str]:
        return iter(self._files)

    def __len__(self) -> int:
        return len(self._files)

    def __gotemplate_lookup__(self, field: str) -> object:
        """Resolve Helm's map keys and exported methods without ambiguity."""

        if field in self._files:
            return self._files[field]
        if not field.startswith("_"):
            try:
                return getattr(self, field)
            except AttributeError:
                pass
        raise KeyError(field)

    def GetBytes(self, name: str) -> bytes:
        """Return raw bytes, or empty bytes for a missing file."""

        return self._files.get(name, b"")

    def Get(self, name: str) -> str:
        """Decode a file as UTF-8, matching Go's byte-to-string conversion."""

        return self.GetBytes(name).decode("utf-8", errors="replace")

    def Glob(self, pattern: str) -> HelmFiles:
        """Return files matching a slash-separated Helm glob."""

        return HelmFiles(
            {
                name: value
                for name, value in self._files.items()
                if fnmatch.fnmatchcase(name, pattern)
            }
        )

    def AsConfig(self) -> str:
        """Serialize basename-to-text entries as a YAML mapping."""

        return _yaml_mapping(
            {
                posixpath.basename(name): value.decode("utf-8", errors="replace")
                for name, value in self._files.items()
            }
        )

    def AsSecrets(self) -> str:
        """Serialize basename-to-base64 entries as a YAML mapping."""

        return _yaml_mapping(
            {
                posixpath.basename(name): base64.b64encode(value).decode()
                for name, value in self._files.items()
            }
        )

    def Lines(self, name: str) -> tuple[str, ...]:
        """Return lines with one final newline removed, like Helm."""

        value = self._files.get(name)
        if value is None:
            return ()
        text = value.decode("utf-8", errors="replace")
        if text.endswith("\n"):
            text = text[:-1]
        return tuple(text.split("\n"))

    get_bytes = GetBytes
    get_text = Get
    glob = Glob
    as_config = AsConfig
    as_secrets = AsSecrets
    lines = Lines


def _yaml_mapping(values: Mapping[str, str]) -> str:
    return "\n".join(f"{key}: {values[key]}" for key in sorted(values))
