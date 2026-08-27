"""Go-shaped timer and ticker APIs without pretending Python queues are channels."""

from __future__ import annotations

import threading
import time
from collections import deque
from collections.abc import Callable, Iterator

from goduration.go import Duration

from .clock import SYSTEM_CLOCK, Clock
from .go import LOCAL, Time


def _duration(value: Duration) -> int:
    if not isinstance(  # pyright: ignore[reportUnnecessaryIsInstance]
        value, Duration
    ):
        raise TypeError("duration must be goduration.go.Duration")
    return value.nanoseconds


def _clock_time(clock: Clock) -> Time:
    seconds, nanosecond = divmod(clock.wall_time_ns(), 1_000_000_000)
    return Time(
        seconds,
        nanosecond,
        LOCAL,
        clock.monotonic_ns(),  # pyright: ignore[reportPrivateUsage]
    )


def sleep(
    duration: Duration,
    *,
    sleeper: Callable[[float], None] = time.sleep,
) -> None:
    nanoseconds = _duration(duration)
    if nanoseconds > 0:
        sleeper(nanoseconds / 1_000_000_000)


class Timer:
    """A resettable one-shot timer with explicit receive instead of a Go channel."""

    def __init__(
        self,
        duration: Duration,
        *,
        clock: Clock = SYSTEM_CLOCK,
        callback: Callable[[], None] | None = None,
    ) -> None:
        self._clock = clock
        self._callback = callback
        self._condition = threading.Condition()
        self._events: deque[Time] = deque(maxlen=1)
        self._active = True
        self._handle = clock.call_later(_duration(duration), self._fire)

    def _fire(self) -> None:
        with self._condition:
            if not self._active:
                return
            self._active = False
            if self._callback is None:
                self._events.append(_clock_time(self._clock))
                self._condition.notify_all()
        if self._callback is not None:
            self._callback()

    def stop(self) -> bool:
        with self._condition:
            active = self._active
            self._active = False
            self._handle.cancel()
            return active

    def reset(self, duration: Duration) -> bool:
        nanoseconds = _duration(duration)
        with self._condition:
            active = self._active
            self._active = True
            self._handle.cancel()
            self._handle = self._clock.call_later(nanoseconds, self._fire)
            return active

    def receive(self, timeout: float | None = None) -> Time:
        with self._condition:
            ready = self._condition.wait_for(lambda: bool(self._events), timeout)
            if not ready:
                raise TimeoutError("timer receive timed out")
            return self._events.popleft()


class Ticker(Iterator[Time]):
    """A periodic timer whose pending event queue has Go's capacity of one."""

    def __init__(
        self,
        duration: Duration,
        *,
        clock: Clock = SYSTEM_CLOCK,
    ) -> None:
        nanoseconds = _duration(duration)
        if nanoseconds <= 0:
            raise ValueError("non-positive interval for new ticker")
        self._clock = clock
        self._period = nanoseconds
        self._condition = threading.Condition()
        self._events: deque[Time] = deque(maxlen=1)
        self._active = True
        self._handle = clock.call_later(nanoseconds, self._fire)

    def _fire(self) -> None:
        with self._condition:
            if not self._active:
                return
            if not self._events:
                self._events.append(_clock_time(self._clock))
                self._condition.notify_all()
            self._handle = self._clock.call_later(self._period, self._fire)

    def stop(self) -> None:
        with self._condition:
            self._active = False
            self._handle.cancel()

    def reset(self, duration: Duration) -> None:
        nanoseconds = _duration(duration)
        if nanoseconds <= 0:
            raise ValueError("non-positive interval for ticker reset")
        with self._condition:
            self._period = nanoseconds
            self._active = True
            self._handle.cancel()
            self._handle = self._clock.call_later(nanoseconds, self._fire)

    def receive(self, timeout: float | None = None) -> Time:
        with self._condition:
            ready = self._condition.wait_for(lambda: bool(self._events), timeout)
            if not ready:
                raise TimeoutError("ticker receive timed out")
            return self._events.popleft()

    def __next__(self) -> Time:
        return self.receive()


def new_timer(
    duration: Duration,
    *,
    clock: Clock = SYSTEM_CLOCK,
) -> Timer:
    return Timer(duration, clock=clock)


def after(
    duration: Duration,
    *,
    clock: Clock = SYSTEM_CLOCK,
) -> Timer:
    return new_timer(duration, clock=clock)


def after_func(
    duration: Duration,
    callback: Callable[[], None],
    *,
    clock: Clock = SYSTEM_CLOCK,
) -> Timer:
    if not callable(callback):
        raise TypeError("callback must be callable")
    return Timer(duration, clock=clock, callback=callback)


def new_ticker(
    duration: Duration,
    *,
    clock: Clock = SYSTEM_CLOCK,
) -> Ticker:
    return Ticker(duration, clock=clock)


def tick(
    duration: Duration,
    *,
    clock: Clock = SYSTEM_CLOCK,
) -> Ticker | None:
    return None if _duration(duration) <= 0 else Ticker(duration, clock=clock)


__all__ = [
    "Ticker",
    "Timer",
    "after",
    "after_func",
    "new_ticker",
    "new_timer",
    "sleep",
    "tick",
]
