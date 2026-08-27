from datetime import UTC, datetime, timedelta

from goduration.go import NANOSECOND, SECOND, Duration

from gotime.go import Location, Time


def _now(wall: datetime, monotonic: int) -> Time:
    return Time.now(clock=lambda: wall, monotonic_clock=lambda: monotonic)


def test_monotonic_readings_drive_instant_operations_when_both_are_present() -> None:
    first = _now(datetime(2024, 1, 1, tzinfo=UTC), 100)
    wall_clock_moved_back = _now(
        datetime(2023, 1, 1, tzinfo=UTC),
        150,
    )

    assert wall_clock_moved_back.subtract(first) == Duration(50)
    assert first.before(wall_clock_moved_back)
    assert wall_clock_moved_back.after(first)
    assert first.compare(wall_clock_moved_back) == -1
    assert not first.equal(wall_clock_moved_back)
    assert first < wall_clock_moved_back


def test_add_preserves_monotonic_reading_and_debug_string_displays_it() -> None:
    value = _now(datetime(2024, 1, 1, tzinfo=UTC), 100)
    later = value.add(SECOND)

    assert later.subtract(value) == SECOND
    assert str(value).endswith(" m=+0.000000100")
    assert str(later).endswith(" m=+1.000000100")


def test_location_calendar_and_rounding_operations_strip_monotonic_reading() -> None:
    value = _now(datetime(2024, 1, 1, tzinfo=UTC), 100)
    fixed = Location.fixed("X", 3_600)

    for stripped in (
        value.utc(),
        value.local(),
        value.in_location(fixed),
        value.add_date(days=1),
        value.round(NANOSECOND),
        value.truncate(NANOSECOND),
    ):
        assert " m=" not in str(stripped)


def test_serialization_does_not_preserve_process_monotonic_reading() -> None:
    value = _now(datetime(2024, 1, 1, tzinfo=UTC), 100)

    assert " m=" not in Time.unmarshal_binary(value.marshal_binary()).__str__()
    assert " m=" not in Time.unmarshal_text(value.marshal_text()).__str__()


def test_named_operations_fall_back_to_wall_time_for_one_reading() -> None:
    monotonic = _now(datetime(2024, 1, 1, tzinfo=UTC), 100)
    wall_only = Time.from_datetime(datetime(2024, 1, 1, tzinfo=UTC))

    assert monotonic.equal(wall_only)
    assert monotonic.subtract(wall_only) == Duration(0)
    assert not monotonic.before(wall_only)


def test_injected_since_and_until_use_injected_monotonic_clock() -> None:
    value = _now(datetime(2024, 1, 1, tzinfo=UTC), 1_000)
    wall = datetime(2030, 1, 1, tzinfo=UTC)

    assert Time.since(
        value,
        clock=lambda: wall,
        monotonic_clock=lambda: 1_250,
    ) == Duration(250)
    assert Time.until(
        value,
        clock=lambda: wall - timedelta(days=1),
        monotonic_clock=lambda: 750,
    ) == Duration(250)
