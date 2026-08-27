"""Explicit trusted content types compatible with Go html/template."""

from __future__ import annotations

from enum import Enum, auto


class ContentKind(Enum):
    """Internal trusted-content classification."""

    PLAIN = auto()
    CSS = auto()
    HTML = auto()
    HTML_ATTR = auto()
    JS = auto()
    JS_STRING = auto()
    URL = auto()
    SRCSET = auto()


class CSS(str):
    """A trusted CSS production supplied by the application."""

    __slots__ = ()


class HTML(str):
    """A trusted HTML fragment supplied by the application."""

    __slots__ = ()


class HTMLAttr(str):
    """A trusted HTML attribute fragment supplied by the application."""

    __slots__ = ()


class JS(str):
    """A trusted JavaScript expression supplied by the application."""

    __slots__ = ()


class JSStr(str):
    """Trusted JavaScript string characters supplied by the application."""

    __slots__ = ()


class URL(str):
    """A trusted URL or URL substring supplied by the application."""

    __slots__ = ()


class Srcset(str):
    """A trusted complete srcset value supplied by the application."""

    __slots__ = ()


def classify(value: object) -> ContentKind:
    """Return the exact trusted type without allowing cross-type bypasses."""

    if isinstance(value, CSS):
        return ContentKind.CSS
    if isinstance(value, HTML):
        return ContentKind.HTML
    if isinstance(value, HTMLAttr):
        return ContentKind.HTML_ATTR
    if isinstance(value, JS):
        return ContentKind.JS
    if isinstance(value, JSStr):
        return ContentKind.JS_STRING
    if isinstance(value, URL):
        return ContentKind.URL
    if isinstance(value, Srcset):
        return ContentKind.SRCSET
    return ContentKind.PLAIN
