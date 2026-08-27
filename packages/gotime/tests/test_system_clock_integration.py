import threading

from gotime.clock import SystemClock


def test_system_clock_reads_time_fires_and_cancels_callbacks() -> None:
    clock = SystemClock()
    fired = threading.Event()

    assert clock.wall_time_ns() > 0
    assert clock.monotonic_ns() > 0
    completed = clock.call_later(1_000_000, fired.set)
    assert fired.wait(0.5)
    assert not completed.cancel()

    cancelled_event = threading.Event()
    cancelled = clock.call_later(100_000_000, cancelled_event.set)
    assert cancelled.cancel()
    assert not cancelled_event.wait(0.02)
