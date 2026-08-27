from collections.abc import Callable

import pytest

import gotpl.funcs.sprig as sprig
from gotpl import GoPointer
from gotpl.runtime import INVALID, UNTYPED_NIL


def function(name: str) -> Callable[..., object]:
    return sprig.generic_func_map()[name]


def test_url_parse_covers_relative_opaque_and_authority_forms() -> None:
    relative = function("urlParse")("something")
    assert isinstance(relative, dict)
    assert relative["path"] == "something"
    assert relative["userinfo"] == ""

    opaque = function("urlParse")("mailto:user@example.com?subject=test#part")
    assert isinstance(opaque, dict)
    assert opaque["opaque"] == "user@example.com"
    assert opaque["path"] == ""
    assert function("urlJoin")(opaque) == "mailto:user@example.com?subject=test#part"
    assert function("urlJoin")({"opaque": "value"}) == "value"


def test_url_helpers_preserve_host_case_and_escape_decoded_fragments() -> None:
    parsed = function("urlParse")("HTTP://User@EXAMPLE.COM:80/a#frag%20ment/%C3%A9")

    assert isinstance(parsed, dict)
    assert parsed["scheme"] == "http"
    assert parsed["host"] == "EXAMPLE.COM:80"
    assert parsed["hostname"] == "EXAMPLE.COM"
    assert parsed["fragment"] == "frag ment/é"
    assert function("urlJoin")(parsed) == (
        "http://User@EXAMPLE.COM:80/a#frag%20ment/%C3%A9"
    )


def test_url_helpers_decode_and_reencode_ipv6_zones() -> None:
    parsed = function("urlParse")("http://[fe80::1%25zone]:8080/a")

    assert isinstance(parsed, dict)
    assert parsed["host"] == "[fe80::1%zone]:8080"
    assert parsed["hostname"] == "fe80::1%zone"
    assert function("urlJoin")(parsed) == "http://[fe80::1%25zone]:8080/a"


def test_url_parse_rejects_invalid_percent_encoding() -> None:
    with pytest.raises(ValueError, match="invalid URL escape"):
        function("urlParse")("https://example.test/%zz")
    with pytest.raises(ValueError, match="invalid URL escape"):
        function("urlParse")("http://exa%6Dple.com/a")


def test_url_join_defaults_missing_components_and_validates_types() -> None:
    assert function("urlJoin")({"path": "a b"}) == "a%20b"
    with pytest.raises(TypeError, match="scheme key"):
        function("urlJoin")({"scheme": 1})


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (INVALID, "invalid"),
        (UNTYPED_NIL, "invalid"),
        (None, "invalid"),
        (GoPointer(object(), "widget"), "ptr"),
        (True, "bool"),
        (1, "int"),
        (1.5, "float64"),
        (1j, "complex128"),
        ("x", "string"),
        (b"x", "slice"),
        ({"x": 1}, "map"),
        (lambda: None, "func"),
        (object(), "struct"),
    ],
)
def test_kind_of_adapts_python_values_to_go_kinds(value: object, expected: str) -> None:
    assert function("kindOf")(value) == expected


def test_type_and_kind_predicates_cover_pointer_like_values() -> None:
    pointer = GoPointer(object(), "widget")
    assert function("typeOf")(pointer) == "*widget"
    assert function("typeIs")("*widget", pointer) is True
    assert function("typeIsLike")("widget", pointer) is True
    assert function("kindIs")("ptr", pointer) is True


def test_deep_equal_terminates_for_recursive_python_collections() -> None:
    left_list: list[object] = []
    right_list: list[object] = []
    left_list.append(left_list)
    right_list.append(right_list)

    left_dict: dict[str, object] = {}
    right_dict: dict[str, object] = {}
    left_dict["self"] = left_dict
    right_dict["self"] = right_dict

    assert function("deepEqual")(left_list, right_list) is True
    assert function("deepEqual")(left_dict, right_dict) is True
    assert function("deepEqual")(left_list, [right_list, 1]) is False


def test_deep_equal_treats_non_nil_python_callables_like_go_functions() -> None:
    def callback() -> None:
        return None

    assert function("deepEqual")(callback, callback) is False


def test_deep_equal_does_not_expose_python_equality_exceptions() -> None:
    class HostileEquality:
        def __eq__(self, other: object) -> bool:
            raise RuntimeError("hostile equality")

    assert function("deepEqual")(HostileEquality(), HostileEquality()) is False
