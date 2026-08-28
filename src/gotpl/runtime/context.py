"""Explicit render context for runtime-aware template functions."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Literal, Protocol, TypeVar

from gotpl.errors import AsyncRequiredError, TemplateExecutionError

from .policy import ExecutionBudget, ExecutionBudgetState

T = TypeVar("T")


def _empty_dynamic_cache() -> dict[tuple[int, str, str], _RenderableAssociation]:
    return {}


def _empty_associations() -> list[_RenderableAssociation]:
    return []


def _empty_extension_state() -> dict[object, object]:
    return {}


class _RenderableAssociation(Protocol):
    def _render_template_in_session(
        self, name: str, data: object, session: RenderSession
    ) -> str: ...

    async def _render_template_async_in_session(
        self, name: str, data: object, session: RenderSession
    ) -> str: ...

    def _render_source_in_session(
        self,
        source: str,
        data: object,
        *,
        name: str,
        session: RenderSession,
    ) -> str: ...

    async def _render_source_async_in_session(
        self,
        source: str,
        data: object,
        *,
        name: str,
        session: RenderSession,
    ) -> str: ...


@dataclass(frozen=True, slots=True)
class ContextFunction:
    """A template function whose first argument is supplied by the runtime."""

    sync: Callable[..., object] | None = None
    async_: Callable[..., Awaitable[object]] | None = None
    capabilities: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        if self.sync is None and self.async_ is None:
            raise ValueError("ContextFunction requires a sync or async implementation")
        if self.sync is not None and not callable(self.sync):
            raise TypeError("ContextFunction sync implementation must be callable")
        if self.async_ is not None and not callable(self.async_):
            raise TypeError("ContextFunction async implementation must be callable")
        object.__setattr__(self, "capabilities", frozenset(self.capabilities))

    def __call__(self, *arguments: object) -> object:
        """Reject direct invocation; the VM must inject a render context."""

        del arguments
        raise RuntimeError("ContextFunction must be called by a gotpl render")


class Extension(Protocol):
    """An immutable provider of explicitly selected template functions."""

    @property
    def functions(self) -> Mapping[str, Callable[..., object]]: ...

    @property
    def template_kinds(self) -> frozenset[Literal["text", "html"]]: ...


@dataclass(slots=True)
class RenderSession:
    """Private mutable state shared by one top-level render and its children."""

    association: _RenderableAssociation
    budget_state: ExecutionBudgetState | None
    depth: int = 0
    dynamic_cache: dict[tuple[int, str, str], _RenderableAssociation] = field(
        default_factory=_empty_dynamic_cache
    )
    _associations: list[_RenderableAssociation] = field(
        default_factory=_empty_associations
    )
    extension_state: dict[object, object] = field(
        default_factory=_empty_extension_state
    )

    @classmethod
    def create(
        cls,
        association: _RenderableAssociation,
        budget: ExecutionBudget | None,
    ) -> RenderSession:
        return cls(
            association,
            None if budget is None else ExecutionBudgetState(budget),
        )

    @property
    def current(self) -> _RenderableAssociation:
        return self.association if not self._associations else self._associations[-1]

    @contextmanager
    def nested(self, association: _RenderableAssociation | None = None):  # type: ignore[no-untyped-def]
        self.depth += 1
        if self.budget_state is not None:
            self.budget_state.check_template_depth(self.depth)
        if association is not None:
            self._associations.append(association)
        try:
            yield
        finally:
            if association is not None:
                self._associations.pop()
            self.depth -= 1


class RenderContext:
    """Read-only synchronous services for a :class:`ContextFunction`."""

    __slots__ = (
        "_dot",
        "_root",
        "_session",
        "_source_name",
        "_template_name",
    )

    def __init__(
        self,
        session: RenderSession,
        *,
        root: object,
        dot: object,
        source_name: str,
        template_name: str,
    ) -> None:
        self._session = session
        self._root = root
        self._dot = dot
        self._source_name = source_name
        self._template_name = template_name

    @property
    def root(self) -> object:
        """The root value of the currently executing template frame."""

        return self._root

    @property
    def dot(self) -> object:
        """The current pipeline dot value."""

        return self._dot

    @property
    def source_name(self) -> str:
        """The source file currently being executed."""

        return self._source_name

    @property
    def template_name(self) -> str:
        """The associated template currently being executed."""

        return self._template_name

    def render_template(self, name: str, data: object = None) -> str:
        """Capture one associated template in the current render session."""

        return self._session.current._render_template_in_session(  # pyright: ignore[reportPrivateUsage]
            name, data, self._session
        )

    def render_source(
        self,
        source: str,
        data: object = None,
        *,
        name: str = "dynamic",
    ) -> str:
        """Compile and capture a dynamic source in the current association."""

        return self._session.current._render_source_in_session(  # pyright: ignore[reportPrivateUsage]
            source,
            data,
            name=name,
            session=self._session,
        )

    def state(self, key: object, factory: Callable[[], T]) -> T:
        """Return extension-local state scoped to this top-level render."""

        value = self._session.extension_state.get(key)
        if value is None:
            value = factory()
            self._session.extension_state[key] = value
        return value  # type: ignore[return-value]


class AsyncRenderContext:
    """Read-only asynchronous services for a :class:`ContextFunction`."""

    __slots__ = (
        "_dot",
        "_root",
        "_session",
        "_source_name",
        "_template_name",
    )

    def __init__(
        self,
        session: RenderSession,
        *,
        root: object,
        dot: object,
        source_name: str,
        template_name: str,
    ) -> None:
        self._session = session
        self._root = root
        self._dot = dot
        self._source_name = source_name
        self._template_name = template_name

    @property
    def root(self) -> object:
        return self._root

    @property
    def dot(self) -> object:
        return self._dot

    @property
    def source_name(self) -> str:
        return self._source_name

    @property
    def template_name(self) -> str:
        return self._template_name

    async def render_template(self, name: str, data: object = None) -> str:
        """Capture one associated template asynchronously."""

        return await self._session.current._render_template_async_in_session(  # pyright: ignore[reportPrivateUsage]
            name, data, self._session
        )

    async def render_source(
        self,
        source: str,
        data: object = None,
        *,
        name: str = "dynamic",
    ) -> str:
        """Compile and capture a dynamic source asynchronously."""

        return await self._session.current._render_source_async_in_session(  # pyright: ignore[reportPrivateUsage]
            source,
            data,
            name=name,
            session=self._session,
        )

    def state(self, key: object, factory: Callable[[], T]) -> T:
        """Return extension-local state scoped to this top-level render."""

        value = self._session.extension_state.get(key)
        if value is None:
            value = factory()
            self._session.extension_state[key] = value
        return value  # type: ignore[return-value]


def require_sync_implementation(function: ContextFunction) -> Callable[..., object]:
    implementation = function.sync
    if implementation is None:
        raise AsyncRequiredError(
            "a context function requires asynchronous rendering; use render_async"
        )
    return implementation


def require_render_session(session: RenderSession | None) -> RenderSession:
    if session is None:
        raise TemplateExecutionError(
            "a context function requires a reusable Template or TemplateEngine render"
        )
    return session


__all__ = [
    "AsyncRenderContext",
    "ContextFunction",
    "Extension",
    "RenderContext",
]
