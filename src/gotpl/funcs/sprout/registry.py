"""Sprout registry and handler primitives."""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

from .inventory import INVENTORY, Notice

TemplateFunction = Callable[..., object]


def _empty_aliases() -> Mapping[str, tuple[str, ...]]:
    return MappingProxyType({})


@dataclass(frozen=True, slots=True)
class FunctionRegistry:
    """An immutable collection of functions and Sprout metadata."""

    name: str
    uid: str
    functions: Mapping[str, TemplateFunction]
    aliases: Mapping[str, tuple[str, ...]] = field(default_factory=_empty_aliases)
    notices: tuple[Notice, ...] = ()

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("registry name must not be empty")
        if not self.uid:
            raise ValueError("registry UID must not be empty")
        object.__setattr__(self, "functions", MappingProxyType(dict(self.functions)))
        object.__setattr__(
            self,
            "aliases",
            MappingProxyType(
                {name: tuple(aliases) for name, aliases in self.aliases.items()}
            ),
        )
        object.__setattr__(self, "notices", tuple(self.notices))


@dataclass(frozen=True, slots=True)
class RegistryGroup:
    """An immutable, ordered Sprout registry group."""

    name: str
    registries: tuple[FunctionRegistry, ...]
    function_names: tuple[str, ...]


class Handler:
    """Build an immutable function map from ordered Sprout registries."""

    __slots__ = ("_built", "_logger", "_registries", "_uids")

    def __init__(
        self,
        *registries: FunctionRegistry,
        logger: logging.Logger | None = None,
    ) -> None:
        self._registries: list[FunctionRegistry] = []
        self._uids: set[str] = set()
        self._logger = logger or logging.getLogger("gotpl.funcs.sprout")
        self._built: Mapping[str, TemplateFunction] | None = None
        for item in registries:
            self.add_registry(item)

    def add_registry(self, item: FunctionRegistry) -> None:
        """Add a registry once by UID, preserving registration order."""

        if self._built is not None:
            raise RuntimeError("cannot add a registry after build()")
        if item.uid in self._uids:
            return
        self._uids.add(item.uid)
        self._registries.append(item)

    def add_group(self, item: RegistryGroup) -> None:
        """Add every registry in a group, preserving its pinned order."""

        for registry_item in item.registries:
            self.add_registry(registry_item)

    def build(self) -> Mapping[str, TemplateFunction]:
        """Return a cached immutable map with aliases and notices assigned."""

        if self._built is not None:
            return self._built

        functions: dict[str, TemplateFunction] = {}
        aliases: dict[str, list[str]] = {}
        notices: list[Notice] = []
        for item in self._registries:
            for name, function in item.functions.items():
                functions.setdefault(name, function)
            for original, names in item.aliases.items():
                aliases.setdefault(original, []).extend(names)
            notices.extend(item.notices)

        for original, names in aliases.items():
            function = functions.get(original)
            if function is None:
                continue
            for name in names:
                functions[name] = function

        for notice in notices:
            for name in notice.functions:
                function = functions.get(name)
                if function is not None:
                    functions[name] = self._notice_wrapper(name, function, notice)

        self._built = MappingProxyType(functions)
        return self._built

    def _notice_wrapper(
        self, name: str, function: TemplateFunction, notice: Notice
    ) -> TemplateFunction:
        def wrapped(*args: object, **kwargs: object) -> object:
            if notice.kind.value == "deprecated":
                self._logger.warning(
                    "Template function `%s` is deprecated: %s",
                    name,
                    notice.message,
                )
            elif notice.kind.value == "info":
                self._logger.info("%s", notice.message)
            else:
                self._logger.debug("%s", notice.message)
            return function(*args, **kwargs)

        return wrapped


def registry(name: str) -> FunctionRegistry:
    """Return an implemented registry from the pinned Sprout release."""

    try:
        factory = _IMPLEMENTED_REGISTRIES[name]
    except KeyError:
        if name in INVENTORY.registries:
            raise NotImplementedError(
                f"Sprout registry {name!r} is inventoried but not implemented"
            ) from None
        raise KeyError(f"unknown Sprout registry {name!r}") from None
    return factory()


def group(name: str) -> RegistryGroup:
    """Return an implemented group from the pinned Sprout release."""

    try:
        inventory = INVENTORY.groups[name]
    except KeyError:
        raise KeyError(f"unknown Sprout group {name!r}") from None
    names_by_uid = {
        item.uid: registry_name for registry_name, item in INVENTORY.registries.items()
    }
    registries = tuple(registry(names_by_uid[uid]) for uid in inventory.registries)
    built = Handler(*registries).build()
    if set(built) != set(inventory.functions):
        raise RuntimeError(f"implemented {name} group differs from inventory")
    return RegistryGroup(name, registries, inventory.functions)


def _load_registry_factories() -> dict[str, Callable[[], FunctionRegistry]]:
    from . import _registries

    return {
        "backward": _registries.backward_registry,
        "checksum": _registries.checksum_registry,
        "conversion": _registries.conversion_registry,
        "crypto": _registries.crypto_registry,
        "encoding": _registries.encoding_registry,
        "env": _registries.environment_registry,
        "filesystem": _registries.filesystem_registry,
        "maps": _registries.maps_registry,
        "network": _registries.network_registry,
        "numeric": _registries.numeric_registry,
        "random": _registries.random_registry,
        "reflect": _registries.reflect_registry,
        "regex": _registries.regex_registry,
        "regexp": _registries.regexp_registry,
        "semver": _registries.semver_registry,
        "slices": _registries.slices_registry,
        "std": _registries.std_registry,
        "strings": _registries.strings_registry,
        "time": _registries.time_registry,
        "uniqueid": _registries.uniqueid_registry,
    }


_IMPLEMENTED_REGISTRIES = MappingProxyType(_load_registry_factories())
