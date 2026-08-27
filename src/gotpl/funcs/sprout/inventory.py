"""Typed, immutable metadata for the pinned Sprout reference."""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from importlib.resources import files
from types import MappingProxyType
from typing import TypedDict, cast


class NoticeKind(StrEnum):
    """Kinds emitted by Sprout function notices."""

    DEPRECATED = "deprecated"
    INFO = "info"
    DEBUG = "debug"


@dataclass(frozen=True, slots=True)
class Notice:
    """A notice attached to one or more function names."""

    functions: tuple[str, ...]
    kind: NoticeKind
    message: str


@dataclass(frozen=True, slots=True)
class RegistryInventory:
    """The raw functions, aliases, and notices owned by one registry."""

    uid: str
    functions: tuple[str, ...]
    aliases: MappingProxyType[str, tuple[str, ...]]
    notices: tuple[Notice, ...]


@dataclass(frozen=True, slots=True)
class GroupInventory:
    """The ordered registry membership and built function names of a group."""

    registries: tuple[str, ...]
    functions: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SproutInventory:
    """The complete versioned metadata snapshot used for conformance."""

    schema_version: int
    reference: str
    version: str
    registries: MappingProxyType[str, RegistryInventory]
    groups: MappingProxyType[str, GroupInventory]


class _NoticeData(TypedDict):
    functions: list[str]
    kind: str
    message: str


class _RegistryData(TypedDict):
    uid: str
    functions: list[str]
    aliases: dict[str, list[str]]
    notices: list[_NoticeData]


class _GroupData(TypedDict):
    registries: list[str]
    functions: list[str]


class _InventoryData(TypedDict):
    schema_version: int
    reference: str
    version: str
    registries: dict[str, _RegistryData]
    groups: dict[str, _GroupData]


def _load_inventory() -> SproutInventory:
    resource = files("gotpl.funcs.sprout").joinpath("data/sprout-v1.1.1-inventory.json")
    data = cast(_InventoryData, json.loads(resource.read_text(encoding="utf-8")))
    if data["schema_version"] != 1:
        raise ValueError(
            f"unsupported Sprout inventory schema {data['schema_version']}"
        )
    registries = {
        name: RegistryInventory(
            uid=registry["uid"],
            functions=tuple(registry["functions"]),
            aliases=MappingProxyType(
                {
                    original: tuple(aliases)
                    for original, aliases in registry["aliases"].items()
                }
            ),
            notices=tuple(
                Notice(
                    functions=tuple(notice["functions"]),
                    kind=NoticeKind(notice["kind"]),
                    message=notice["message"],
                )
                for notice in registry["notices"]
            ),
        )
        for name, registry in data["registries"].items()
    }
    groups = {
        name: GroupInventory(
            registries=tuple(group["registries"]),
            functions=tuple(group["functions"]),
        )
        for name, group in data["groups"].items()
    }
    return SproutInventory(
        schema_version=data["schema_version"],
        reference=data["reference"],
        version=data["version"],
        registries=MappingProxyType(registries),
        groups=MappingProxyType(groups),
    )


INVENTORY = _load_inventory()
