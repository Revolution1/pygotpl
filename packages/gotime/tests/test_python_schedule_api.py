import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from goduration.python import Duration

from gotime.clock import ManualClock
from gotime.python import (
    AsyncTicker,
    AsyncTimer,
    Ticker,
    Time,
    Timer,
    sleep,
    sleep_async,
    timeout_at,
    wait_until,
)


def test_python_time_timestamp_constructors_follow_datetime_conventions() -> None:
    aware = Time.from_timestamp(1_700_000_000.25, UTC)
    naive = Time.from_timestamp(1_700_000_000)

    assert aware.datetime.tzinfo is UTC
    assert aware.timestamp() == 1_700_000_000.25
    assert naive.datetime.tzinfo is None
    assert Time.now(UTC).datetime.tzinfo is UTC


def test_python_sync_timer_accepts_timedelta_and_duration() -> None:
    clock = ManualClock(wall_time_ns=1_000_000_000)
    timer = Timer(timedelta(seconds=1), clock=clock)

    clock.advance(1_000_000_000)
    assert timer.wait(timeout=0).timestamp() == 2.0
    assert not timer.reset(Duration(500_000_000))
    clock.advance(500_000_000)
    assert timer.wait(timeout=0).timestamp() == 2.5


def test_python_sync_ticker_and_sleep_are_deterministic() -> None:
    clock = ManualClock()
    ticker = Ticker(0.25, clock=clock)
    sleeps: list[float] = []

    sleep(timedelta(milliseconds=250), sleeper=sleeps.append)
    clock.advance(250_000_000)
    assert ticker.wait(timeout=0).timestamp() == 0.25
    ticker.reset(Duration(500_000_000))
    clock.advance(500_000_000)
    assert next(ticker).timestamp() == 0.75
    ticker.stop()
    assert sleeps == [0.25]


def test_python_scheduler_validation_and_timeout_paths() -> None:
    clock = ManualClock()
    timer = Timer(1, clock=clock)
    ticker = Ticker(1, clock=clock)

    with pytest.raises(TimeoutError, match="timer wait timed out"):
        timer.wait(timeout=0)
    with pytest.raises(TimeoutError, match="ticker wait timed out"):
        ticker.wait(timeout=0)
    assert timer.stop()
    assert not timer.stop()
    with pytest.raises(ValueError, match="ticker interval must be positive"):
        Ticker(0, clock=clock)
    with pytest.raises(ValueError, match="ticker interval must be positive"):
        ticker.reset(0)
    with pytest.raises(TypeError, match="delay must be"):
        Timer(object(), clock=clock)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="nanoseconds must be an integer"):
        clock.advance(True)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="must not be negative"):
        clock.advance(-1)


@pytest.mark.asyncio
async def test_async_sleep_and_deadline_use_injected_sleeper() -> None:
    delays: list[float] = []

    async def record(delay: float) -> None:
        delays.append(delay)

    current = Time(datetime(2024, 1, 1, tzinfo=UTC))
    deadline = Time(datetime(2024, 1, 1, 0, 0, 2, tzinfo=UTC))
    await sleep_async(Duration(500_000_000), sleeper=record)
    await wait_until(deadline, now=lambda: current, sleeper=record)

    assert delays == [0.5, 2.0]


@pytest.mark.asyncio
async def test_async_timer_is_awaitable_resettable_and_cancellable() -> None:
    delays: list[float] = []
    values = iter(
        [
            Time(datetime(2024, 1, 1, tzinfo=UTC)),
            Time(datetime(2024, 1, 2, tzinfo=UTC)),
        ]
    )

    async def immediate(delay: float) -> None:
        delays.append(delay)

    timer = AsyncTimer(0.25, sleeper=immediate, now=lambda: next(values))
    assert (await timer.wait()).datetime.day == 1
    assert not timer.reset(timedelta(seconds=1))
    assert (await timer.wait()).datetime.day == 2
    assert delays == [0.25, 1.0]

    gate = asyncio.Event()

    async def blocked(delay: float) -> None:
        del delay
        await gate.wait()

    pending = AsyncTimer(1, sleeper=blocked)
    await asyncio.sleep(0)
    assert pending.stop()
    with pytest.raises(asyncio.CancelledError):
        await pending.wait()


@pytest.mark.asyncio
async def test_async_ticker_is_a_native_async_iterator() -> None:
    delays: list[float] = []

    async def immediate(delay: float) -> None:
        delays.append(delay)

    ticker = AsyncTicker(
        0.5,
        sleeper=immediate,
        now=lambda: Time(datetime(2024, 1, 1, tzinfo=UTC)),
    )
    assert (await anext(ticker)).datetime.year == 2024
    ticker.reset(timedelta(seconds=1))
    assert (await anext(ticker)).datetime.year == 2024
    ticker.stop()
    with pytest.raises(StopAsyncIteration):
        await anext(ticker)
    assert delays == [0.5, 1.0]


@pytest.mark.asyncio
async def test_async_ticker_validation_and_stop_during_wait() -> None:
    with pytest.raises(ValueError, match="ticker interval must be positive"):
        AsyncTicker(0)

    gate = asyncio.Event()

    async def blocked(delay: float) -> None:
        del delay
        await gate.wait()

    ticker = AsyncTicker(1, sleeper=blocked)
    assert ticker.__aiter__() is ticker
    pending = asyncio.create_task(anext(ticker))
    await asyncio.sleep(0)
    ticker.stop()
    gate.set()
    with pytest.raises(StopAsyncIteration):
        await pending

    with pytest.raises(ValueError, match="ticker interval must be positive"):
        ticker.reset(0)


@pytest.mark.asyncio
async def test_timeout_at_returns_native_asyncio_context_manager() -> None:
    current = Time(datetime(2024, 1, 1, tzinfo=UTC))
    deadline = Time(datetime(2024, 1, 1, tzinfo=UTC))

    with pytest.raises(TimeoutError):
        async with timeout_at(deadline, now=lambda: current):
            await asyncio.sleep(0.01)

    with pytest.raises(TypeError, match="deadline must be"):
        timeout_at("bad")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="deadline must be"):
        await wait_until("bad")  # type: ignore[arg-type]
