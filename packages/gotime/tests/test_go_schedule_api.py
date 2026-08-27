import pytest
from goduration.go import SECOND, Duration

from gotime.clock import ManualClock
from gotime.go import after, after_func, new_ticker, new_timer, sleep, tick


def test_timer_fires_from_deterministic_wall_and_monotonic_clock() -> None:
    clock = ManualClock(wall_time_ns=10_000_000_000, monotonic_ns=100)
    timer = new_timer(SECOND, clock=clock)

    with pytest.raises(TimeoutError, match="timer receive timed out"):
        timer.receive(timeout=0)
    clock.advance(SECOND.nanoseconds)
    fired = timer.receive(timeout=0)

    assert fired.unix_nanoseconds() == 11_000_000_000
    assert str(fired).endswith("m=+1.000000100")
    assert not timer.stop()


def test_timer_stop_and_reset_report_prior_active_state() -> None:
    clock = ManualClock()
    timer = new_timer(SECOND, clock=clock)

    assert timer.stop()
    assert not timer.stop()
    assert not timer.reset(SECOND)
    assert timer.reset(SECOND)
    clock.advance(SECOND.nanoseconds)
    assert timer.receive(timeout=0).unix_nanoseconds() == SECOND.nanoseconds


def test_after_func_runs_once_and_can_be_reset() -> None:
    clock = ManualClock()
    calls: list[int] = []
    timer = after_func(SECOND, lambda: calls.append(clock.monotonic_ns()), clock=clock)

    clock.advance(SECOND.nanoseconds)
    assert calls == [SECOND.nanoseconds]
    assert not timer.reset(SECOND)
    clock.advance(SECOND.nanoseconds)
    assert calls == [SECOND.nanoseconds, 2 * SECOND.nanoseconds]


def test_ticker_drops_pending_ticks_and_reset_changes_period() -> None:
    clock = ManualClock()
    ticker = new_ticker(SECOND, clock=clock)

    clock.advance(3 * SECOND.nanoseconds)
    assert ticker.receive(timeout=0).unix_nanoseconds() == SECOND.nanoseconds
    with pytest.raises(TimeoutError, match="ticker receive timed out"):
        ticker.receive(timeout=0)

    ticker.reset(Duration(2 * SECOND.nanoseconds))
    clock.advance(2 * SECOND.nanoseconds)
    assert ticker.receive(timeout=0).unix_nanoseconds() == 5 * SECOND.nanoseconds
    ticker.stop()
    clock.advance(10 * SECOND.nanoseconds)
    with pytest.raises(TimeoutError, match="ticker receive timed out"):
        ticker.receive(timeout=0)


def test_go_constructors_validate_ticker_periods_and_tick_compatibility() -> None:
    clock = ManualClock()

    assert tick(Duration(0), clock=clock) is None
    with pytest.raises(ValueError, match="non-positive interval for new ticker"):
        new_ticker(Duration(0), clock=clock)
    ticker = new_ticker(SECOND, clock=clock)
    with pytest.raises(ValueError, match="non-positive interval for ticker reset"):
        ticker.reset(Duration(-1))


def test_after_alias_and_injected_sleep() -> None:
    clock = ManualClock()
    timer = after(SECOND, clock=clock)
    calls: list[float] = []

    sleep(SECOND, sleeper=calls.append)
    sleep(Duration(-1), sleeper=calls.append)
    assert calls == [1.0]
    clock.advance(SECOND.nanoseconds)
    assert timer.receive(timeout=0).unix_nanoseconds() == SECOND.nanoseconds


def test_go_scheduler_type_and_callback_validation() -> None:
    clock = ManualClock()

    with pytest.raises(TypeError, match="duration must be"):
        new_timer(1, clock=clock)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="callback must be callable"):
        after_func(SECOND, None, clock=clock)  # type: ignore[arg-type]
