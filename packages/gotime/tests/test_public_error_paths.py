from datetime import UTC, datetime, timedelta

import pytest
from goduration.go import SECOND as GO_SECOND
from goduration.python import Duration as PythonDuration

from gotime.go import UTC as GO_UTC
from gotime.go import Location, LocationError
from gotime.go import Time as GoTime
from gotime.python import Time as PythonTime


@pytest.mark.parametrize("name", ["../UTC", "/UTC", "\\UTC", "Not/AZone"])
def test_go_location_rejects_invalid_or_unknown_names(name: str) -> None:
    with pytest.raises(LocationError):
        Location.load(name)


def test_go_location_and_value_type_validation() -> None:
    with pytest.raises(TypeError, match="location name must be a string"):
        Location.load(1)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="location offset must be an integer"):
        Location.fixed("bad", True)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match=r"value must be datetime\.tzinfo"):
        Location.from_tzinfo("UTC")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="Unix seconds must be an integer"):
        GoTime.from_unix(True)  # type: ignore[arg-type]
    with pytest.raises(OverflowError, match="signed 64-bit"):
        GoTime.from_unix(1 << 63)
    with pytest.raises(ValueError, match="nanosecond must be between"):
        GoTime(0, 1_000_000_000)
    with pytest.raises(TypeError, match="location must be"):
        GoTime(0, location="UTC")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="time components must be integers"):
        GoTime.from_components(2024, 1, 1, 0, 0, 0, True, GO_UTC)
    with pytest.raises(TypeError, match="location must be"):
        GoTime.from_components(2024, 1, 1, 0, 0, 0, 0, "UTC")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match=r"value must be datetime\.datetime"):
        GoTime.from_datetime("bad")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="aware datetime"):
        GoTime.from_datetime(datetime(2024, 1, 1))


def test_go_time_method_type_validation() -> None:
    value = GoTime.from_unix(0, location=GO_UTC)

    with pytest.raises(TypeError, match="location must be"):
        value.in_location("UTC")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="layout must be a string"):
        value.format(1)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="prefix must be bytes"):
        value.append_format("", "2006")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="duration must be"):
        value.add(1)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="duration must be"):
        value.round(1)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="duration must be"):
        value.truncate(1)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="other must be"):
        value.subtract(1)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="other must be"):
        value.equal(1)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="other must be"):
        value.compare(1)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="years must be an integer"):
        value.add_date(years=True)  # type: ignore[arg-type]

    assert value.__eq__(1) is NotImplemented
    assert value.__lt__(1) is NotImplemented
    assert value.__add__(1) is NotImplemented
    assert value.__sub__(1) is NotImplemented  # type: ignore[call-overload]
    reverse = value.__radd__(GO_SECOND)
    assert isinstance(reverse, GoTime)
    assert reverse.equal(value + GO_SECOND)


def test_go_conversion_and_serialization_boundary_errors() -> None:
    outside_datetime = GoTime.from_components(10_000, 1, 1, 0, 0, 0, 0, GO_UTC)
    huge_offset = GoTime.from_components(
        2024, 1, 1, 0, 0, 0, 0, Location.fixed("huge", 86_400)
    )

    with pytest.raises(OverflowError, match="datetime's supported range"):
        outside_datetime.to_datetime()
    with pytest.raises(ValueError, match="year outside"):
        outside_datetime.marshal_text()
    with pytest.raises(ValueError, match=r"Time\.MarshalJSON: year outside"):
        outside_datetime.marshal_json()
    with pytest.raises(ValueError, match="timezone hour outside"):
        huge_offset.marshal_text()
    with pytest.raises(TypeError, match="prefix must be bytes"):
        GoTime.zero().append_binary("bad")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="prefix must be bytes"):
        GoTime.zero().append_text("bad")  # type: ignore[arg-type]


def test_python_time_validation_and_operator_fallbacks() -> None:
    with pytest.raises(TypeError, match=r"value must be datetime\.datetime"):
        PythonTime("bad")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="submicrosecond nanoseconds"):
        PythonTime(datetime.now(), True)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="between 0 and 999"):
        PythonTime(datetime.now(), 1_000)
    with pytest.raises(TypeError, match="timestamp must be"):
        PythonTime.from_timestamp(True)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match=r"gotime\.go\.Time"):
        PythonTime.from_go("bad")  # type: ignore[arg-type]
    with pytest.raises(OverflowError, match="outside datetime"):
        PythonTime.from_go(GoTime.from_components(10_000, 1, 1, 0, 0, 0, 0, GO_UTC))

    value = PythonTime(datetime(2024, 1, 1, tzinfo=UTC), 1)
    with pytest.raises(ValueError, match="lose nanosecond precision"):
        value.to_datetime()
    assert value.to_datetime(allow_precision_loss=True).year == 2024
    with pytest.raises(TypeError, match=r"goduration\.python\.Duration"):
        value.add(1)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match=r"gotime\.python\.Time"):
        value.subtract(1)  # type: ignore[arg-type]
    assert value.__eq__(1) is NotImplemented
    assert value.__lt__(1) is NotImplemented
    assert value.__add__(1) is NotImplemented
    assert value.__sub__(1) is NotImplemented  # type: ignore[call-overload]
    assert (value + timedelta(seconds=1)).datetime.day == 1
    assert (value - timedelta(seconds=1)).datetime.day == 31
    assert (value - PythonDuration(1)).submicrosecond_nanoseconds == 0
