import pytest

from gotime.go import UTC, Location, Time


def test_append_and_gob_aliases_share_go_wire_formats() -> None:
    value = Time.from_unix(1_609_459_200, 123_456_789, location=UTC)

    assert value.append_binary(b"prefix:") == b"prefix:" + value.marshal_binary()
    assert value.gob_encode() == value.marshal_binary()
    assert Time.gob_decode(value.gob_encode()) == value
    assert value.append_text(b"prefix:") == b"prefix:" + value.marshal_text()


@pytest.mark.parametrize(
    ("data", "message"),
    [
        (b"", "Time.UnmarshalBinary: no data"),
        (b"\x00" + b"\x00" * 14, "Time.UnmarshalBinary: unsupported version"),
        (b"\x01", "Time.UnmarshalBinary: invalid length"),
        (b"\x02" + b"\x00" * 14, "Time.UnmarshalBinary: invalid length"),
    ],
)
def test_unmarshal_binary_rejects_invalid_go_wire_data(
    data: bytes, message: str
) -> None:
    with pytest.raises(ValueError, match=f"^{message}$"):
        Time.unmarshal_binary(data)


def test_binary_serialization_rejects_reserved_and_large_offsets() -> None:
    reserved = Time.from_unix(0, location=Location.fixed("reserved", -60))
    too_large = Time.from_unix(0, location=Location.fixed("large", 2_000_000))

    with pytest.raises(
        ValueError, match=r"^Time.MarshalBinary: unexpected zone offset$"
    ):
        reserved.marshal_binary()
    with pytest.raises(
        ValueError, match=r"^Time.MarshalBinary: unexpected zone offset$"
    ):
        too_large.marshal_binary()


@pytest.mark.parametrize("data", [b"null", b"123", b"{}", b"not-json"])
def test_unmarshal_json_requires_a_json_string(data: bytes) -> None:
    with pytest.raises(
        ValueError, match=r"^Time.UnmarshalJSON: input is not a JSON string$"
    ):
        Time.unmarshal_json(data)


def test_serialization_requires_bytes() -> None:
    with pytest.raises(TypeError, match="data must be bytes"):
        Time.unmarshal_binary("bad")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="data must be bytes"):
        Time.unmarshal_text("bad")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="data must be bytes"):
        Time.unmarshal_json("bad")  # type: ignore[arg-type]


def test_rfc3339_wire_format_supports_go_year_zero_and_long_fractions() -> None:
    year_zero = Time.from_components(0, 1, 1, 0, 0, 0, 1, Location.fixed("", 60))

    assert year_zero.marshal_json() == b'"0000-01-01T00:00:00.000000001+00:01"'
    assert Time.unmarshal_json(year_zero.marshal_json()).equal(year_zero)
    assert (
        Time.unmarshal_text(b"2021-09-29T16:04:33.0123456789999999Z").nanosecond
        == 12_345_678
    )


@pytest.mark.parametrize(
    "text",
    [
        b"2000-01-01T1:12:34Z",
        b"2000-01-01T00:00:00,000Z",
        b"2000-01-01T00:00:00+24:00",
        b"2000-01-01T00:00:00+00:60",
    ],
)
def test_rfc3339_decoder_preserves_go_legacy_permissiveness(text: bytes) -> None:
    Time.unmarshal_text(text)
