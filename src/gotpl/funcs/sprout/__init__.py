"""Opt-in Sprout compatibility for gotpl."""

from .errors import MissingOptionalDependencyError
from .inventory import (
    INVENTORY,
    GroupInventory,
    Notice,
    NoticeKind,
    RegistryInventory,
    SproutInventory,
)
from .registry import (
    FunctionRegistry,
    Handler,
    RegistryGroup,
    TemplateFunction,
    group,
    registry,
)

__all__ = [
    "INVENTORY",
    "FunctionRegistry",
    "GroupInventory",
    "Handler",
    "MissingOptionalDependencyError",
    "Notice",
    "NoticeKind",
    "RegistryGroup",
    "RegistryInventory",
    "SproutInventory",
    "TemplateFunction",
    "__version__",
    "group",
    "registry",
]

__version__ = "0.0.0"
