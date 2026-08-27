"""Python-native synchronous and asyncio scheduling APIs."""

from __future__ import annotations

import asyncio
import threading
import time
from collections import deque
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Self

from goduration.python import Duration

from .clock import SYSTEM_CLOCK, Clock
from .python import Time

Delay = Duration | timedelta | int | float
AsyncSleeper = Callable[[float], Awaitable[None]]


def _delay_nanoseconds(value: Delay) -> int:
    if isinstance(value, Duration):
        return value.nanoseconds
    if isinstance(value, timedelta):
        return (
            value.days * 86_400_000_000_000
            + value.seconds * 1_000_000_000
            + value.microseconds * 1_000
        )
    if isinstance(value, bool) or not isinstance(  # pyright: ignore[reportUnnecessaryIsInstance]
        value, (int, float)
    ):
        raise TypeError("delay must be a Duration, timedelta, or number of seconds")
    return int(value * 1_000_000_000)


def _clock_time(clock: Clock) -> Time:
    seconds, nanosecond = divmod(clock.wall_time_ns(), 1_000_000_000)
    value = datetime.fromtimestamp(seconds, UTC).replace(
        microsecond=nanosecond // 1_000
    )
    return Time(value, nanosecond % 1_000)


def sleep(
    delay: Delay,
    *,
    sleeper: Callable[[float], None] = time.sleep,
) -> None:
    nanoseconds = _delay_nanoseconds(delay)
    if nanoseconds > 0:
        sleeper(nanoseconds / 1_000_000_000)


async def sleep_async(
    delay: Delay,
    *,
    sleeper: AsyncSleeper = asyncio.sleep,
) -> None:
    nanoseconds = _delay_nanoseconds(delay)
    if nanoseconds > 0:
        await sleeper(nanoseconds / 1_000_000_000)


class Timer:
    """A Python-native resettable synchronous timer."""

    def __init__(self, delay: Delay, *, clock: Clock = SYSTEM_CLOCK) -> None:
        self._clock = clock
        self._condition = threading.Condition()
        self._events: deque[Time] = deque(maxlen=1)
        self._active = True
        self._handle = clock.call_later(_delay_nanoseconds(delay), self._fire)

    def _fire(self) -> None:
        with self._condition:
            if not self._active:
                return
            self._active = False
            self._events.append(_clock_time(self._clock))
            self._condition.notify_all()

    def stop(self) -> bool:
        with self._condition:
            active = self._active
            self._active = False
            self._handle.cancel()
            return active

    def reset(self, delay: Delay) -> bool:
        nanoseconds = _delay_nanoseconds(delay)
        with self._condition:
            active = self._active
            self._active = True
            self._handle.cancel()
            self._handle = self._clock.call_later(nanoseconds, self._fire)
            return active

    def wait(self, timeout: float | None = None) -> Time:
        with self._condition:
            ready = self._condition.wait_for(lambda: bool(self._events), timeout)
            if not ready:
                raise TimeoutError("timer wait timed out")
            return self._events.popleft()


class Ticker:
    """A Python iterator over periodic clock readings."""

    def __init__(self, delay: Delay, *, clock: Clock = SYSTEM_CLOCK) -> None:
        period = _delay_nanoseconds(delay)
        if period <= 0:
            raise ValueError("ticker interval must be positive")
        self._clock = clock
        self._period = period
        self._condition = threading.Condition()
        self._events: deque[Time] = deque(maxlen=1)
        self._active = True
        self._handle = clock.call_later(period, self._fire)

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

    def reset(self, delay: Delay) -> None:
        period = _delay_nanoseconds(delay)
        if period <= 0:
            raise ValueError("ticker interval must be positive")
        with self._condition:
            self._period = period
            self._active = True
            self._handle.cancel()
            self._handle = self._clock.call_later(period, self._fire)

    def wait(self, timeout: float | None = None) -> Time:
        with self._condition:
            ready = self._condition.wait_for(lambda: bool(self._events), timeout)
            if not ready:
                raise TimeoutError("ticker wait timed out")
            return self._events.popleft()

    def __iter__(self) -> Self:
        return self

    def __next__(self) -> Time:
        return self.wait()


class AsyncTimer:
    """An awaitable one-shot timer with cancellation-safe reset semantics."""

    def __init__(
        self,
        delay: Delay,
        *,
        sleeper: AsyncSleeper = asyncio.sleep,
        now: Callable[[], Time] | None = None,
    ) -> None:
        self._sleeper = sleeper
        self._now = now or (lambda: Time.now(UTC))
        self._generation = 0
        self._result: asyncio.Future[Time]
        self._task: asyncio.Task[None]
        self._start(delay)

    def _start(self, delay: Delay) -> None:
        loop = asyncio.get_running_loop()
        self._generation += 1
        generation = self._generation
        self._result = loop.create_future()

        async def run() -> None:
            try:
                await sleep_async(delay, sleeper=self._sleeper)
                if generation == self._generation and not self._result.done():
                    self._result.set_result(self._now())
            except asyncio.CancelledError:
                return

        self._task = loop.create_task(run())

    def stop(self) -> bool:
        active = not self._task.done() and not self._result.done()
        self._generation += 1
        self._task.cancel()
        if not self._result.done():
            self._result.cancel()
        return active

    def reset(self, delay: Delay) -> bool:
        active = self.stop()
        self._start(delay)
        return active

    async def wait(self) -> Time:
        return await self._result


class AsyncTicker:
    """A native async iterator with a resettable period."""

    def __init__(
        self,
        delay: Delay,
        *,
        sleeper: AsyncSleeper = asyncio.sleep,
        now: Callable[[], Time] | None = None,
    ) -> None:
        period = _delay_nanoseconds(delay)
        if period <= 0:
            raise ValueError("ticker interval must be positive")
        self._period = period
        self._sleeper = sleeper
        self._now = now or (lambda: Time.now(UTC))
        self._active = True

    def reset(self, delay: Delay) -> None:
        period = _delay_nanoseconds(delay)
        if period <= 0:
            raise ValueError("ticker interval must be positive")
        self._period = period
        self._active = True

    def stop(self) -> None:
        self._active = False

    def __aiter__(self) -> Self:
        return self

    async def __anext__(self) -> Time:
        if not self._active:
            raise StopAsyncIteration
        await self._sleeper(self._period / 1_000_000_000)
        if not self._active:
            raise StopAsyncIteration
        return self._now()


async def wait_until(
    deadline: Time,
    *,
    now: Callable[[], Time] | None = None,
    sleeper: AsyncSleeper = asyncio.sleep,
) -> None:
    if not isinstance(  # pyright: ignore[reportUnnecessaryIsInstance]
        deadline, Time
    ):
        raise TypeError("deadline must be gotime.python.Time")
    current = (now or (lambda: Time.now(deadline.datetime.tzinfo)))()
    await sleep_async(deadline.subtract(current), sleeper=sleeper)


def timeout_at(
    deadline: Time,
    *,
    now: Callable[[], Time] | None = None,
) -> asyncio.Timeout:
    if not isinstance(  # pyright: ignore[reportUnnecessaryIsInstance]
        deadline, Time
    ):
        raise TypeError("deadline must be gotime.python.Time")
    current = (now or (lambda: Time.now(deadline.datetime.tzinfo)))()
    delay = max(0, deadline.subtract(current).nanoseconds) / 1_000_000_000
    return asyncio.timeout(delay)


__all__ = [
    "AsyncTicker",
    "AsyncTimer",
    "Delay",
    "Ticker",
    "Timer",
    "sleep",
    "sleep_async",
    "timeout_at",
    "wait_until",
]
