from __future__ import annotations

import uuid

from gotime.go import Time

from gotpl.funcs.sprout import Handler, registry
from gotpl.runtime import FunctionResult

V1 = "0bcce080-0c83-11ef-8000-000000000000"
V5 = "886313e1-3b8a-5372-9b90-0c9aee199e5d"
V7 = "018f5395-4e88-7000-8000-000000000000"


def _unwrap(result: object) -> object:
    assert isinstance(result, FunctionResult)
    assert result.error is None
    return result.value


def test_uniqueid_registry_generates_and_derives_uuid_versions() -> None:
    functions = Handler(registry("uniqueid")).build()

    generated_v4 = str(functions["uuidv4"]())
    generated_v7 = str(_unwrap(functions["uuidv7"]()))
    assert uuid.UUID(generated_v4).version == 4
    assert uuid.UUID(generated_v7).version == 7
    assert _unwrap(functions["uuidv5"]("dns", "python.org")) == V5
    assert _unwrap(functions["uuidv5"]("DNS", "python.org")) == V5
    assert _unwrap(functions["uuidv3"]("dns", "python.org")) == (
        "6fa459ea-ee8a-3ca4-894e-db77e160355e"
    )
    assert functions["uuidNil"]() == "00000000-0000-0000-0000-000000000000"


def test_uniqueid_registry_validates_versions_and_embedded_times() -> None:
    functions = Handler(registry("uniqueid")).build()

    assert functions["isUUID"](V5) is True
    assert functions["isUUID"]("urn:uuid:" + V5) is True
    assert functions["isUUID"]("{" + V5 + "}") is True
    assert functions["isUUID"](V5.replace("-", "")) is True
    assert functions["isUUID"]("not-a-uuid") is False
    assert _unwrap(functions["uuidVersion"](V1)) == 1
    assert _unwrap(functions["uuidVersion"](V5)) == 5
    assert _unwrap(functions["uuidVersion"](V7)) == 7

    for value in (V1, V7):
        embedded = _unwrap(functions["uuidTime"](value))
        assert isinstance(embedded, Time)
        assert embedded.unix() == 1_715_094_245


def test_uniqueid_registry_reports_namespace_uuid_and_time_errors() -> None:
    functions = Handler(registry("uniqueid")).build()

    for name, arguments, message in (
        ("uuidv5", ("invalid", "python.org"), "invalid namespace"),
        ("uuidVersion", ("not-a-uuid",), "invalid UUID"),
        ("uuidTime", (V5,), "uuid version 5 does not embed a time"),
    ):
        result = functions[name](*arguments)
        assert isinstance(result, FunctionResult)
        assert result.error is not None
        assert message in str(result.error)
