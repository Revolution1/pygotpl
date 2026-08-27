"""Injectable wall and monotonic clocks for scheduling APIs."""

from __future__ import annotations

import heapq
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Protocol


class ScheduledHandle(Protocol):
    def cancel(self) -> bool:
        """Cancel a pending callback and report whether it was active."""

        ...


class Clock(Protocol):
    def wall_time_ns(self) -> int: ...

    def monotonic_ns(self) -> int: ...

    def call_later(
        self, delay_nanoseconds: int, callback: Callable[[], None]
    ) -> ScheduledHandle: ...


class _SystemHandle:
    __slots__ = ("_active", "_lock", "_timer")

    def __init__(self, delay: float, callback: Callable[[], None]) -> None:
        self._active = True
        self._lock = threading.Lock()

        def invoke() -> None:
            with self._lock:
                if not self._active:
                    return
                self._active = False
            callback()

        self._timer = threading.Timer(delay, invoke)
        self._timer.daemon = True
        self._timer.start()

    def cancel(self) -> bool:
        with self._lock:
            active = self._active
            self._active = False
        self._timer.cancel()
        return active


class SystemClock:
    """The process wall and monotonic clocks with threaded callbacks."""

    __slots__ = ()

    def wall_time_ns(self) -> int:
        return time.time_ns()

    def monotonic_ns(self) -> int:
        return time.monotonic_ns()

    def call_later(
        self, delay_nanoseconds: int, callback: Callable[[], None]
    ) -> ScheduledHandle:
        return _SystemHandle(max(0, delay_nanoseconds) / 1_000_000_000, callback)


@dataclass(order=True, slots=True)
class _ManualEntry:
    deadline: int
    sequence: int
    handle: _ManualHandle = field(compare=False)
    callback: Callable[[], None] = field(compare=False)


class _ManualHandle:
    __slots__ = ("active",)

    def __init__(self) -> None:
        self.active = True

    def cancel(self) -> bool:
        active = self.active
        self.active = False
        return active


class ManualClock:
    """A deterministic wall/monotonic clock advanced explicitly by tests or apps."""

    __slots__ = ("_entries", "_monotonic", "_sequence", "_wall")

    def __init__(self, *, wall_time_ns: int = 0, monotonic_ns: int = 0) -> None:
        self._wall = wall_time_ns
        self._monotonic = monotonic_ns
        self._sequence = 0
        self._entries: list[_ManualEntry] = []

    def wall_time_ns(self) -> int:
        return self._wall

    def monotonic_ns(self) -> int:
        return self._monotonic

    def call_later(
        self, delay_nanoseconds: int, callback: Callable[[], None]
    ) -> ScheduledHandle:
        handle = _ManualHandle()
        entry = _ManualEntry(
            self._monotonic + max(0, delay_nanoseconds),
            self._sequence,
            handle,
            callback,
        )
        self._sequence += 1
        heapq.heappush(self._entries, entry)
        return handle

    def advance(self, nanoseconds: int) -> None:
        if isinstance(nanoseconds, bool) or not isinstance(  # pyright: ignore[reportUnnecessaryIsInstance]
            nanoseconds, int
        ):
            raise TypeError("nanoseconds must be an integer")
        if nanoseconds < 0:
            raise ValueError("nanoseconds must not be negative")
        target = self._monotonic + nanoseconds
        while self._entries and self._entries[0].deadline <= target:
            entry = heapq.heappop(self._entries)
            elapsed = entry.deadline - self._monotonic
            self._monotonic = entry.deadline
            self._wall += elapsed
            if entry.handle.active:
                entry.handle.active = False
                entry.callback()
        elapsed = target - self._monotonic
        self._monotonic = target
        self._wall += elapsed


SYSTEM_CLOCK = SystemClock()

__all__ = ["SYSTEM_CLOCK", "Clock", "ManualClock", "ScheduledHandle", "SystemClock"]
