from dataclasses import dataclass

from gotpl.runtime.values import INVALID, UNTYPED_NIL, ValueAdapter


@dataclass
class Profile:
    Name: str
    Count: int = 0
    _secret: str = "hidden"


def test_invalid_value_has_a_stable_debug_representation() -> None:
    assert repr(INVALID) == "INVALID"
    assert repr(UNTYPED_NIL) == "UNTYPED_NIL"


def test_value_adapter_reads_mapping_keys_and_public_attributes() -> None:
    adapter = ValueAdapter()
    assert adapter.lookup({"Name": "mapping"}, "Name") == "mapping"
    assert adapter.lookup({"_0": "first"}, "_0") == "first"
    assert adapter.lookup(Profile("attribute"), "Name") == "attribute"


def test_value_adapter_returns_invalid_for_missing_or_private_fields() -> None:
    adapter = ValueAdapter()
    profile = Profile("value")
    assert adapter.lookup(INVALID, "anything") is INVALID
    assert adapter.lookup(profile, "Missing") is INVALID
    assert adapter.lookup(profile, "_secret") is INVALID
    assert adapter.lookup(profile, "__class__") is INVALID


def test_value_adapter_follows_field_chains() -> None:
    adapter = ValueAdapter()
    value = {"User": Profile("Ada")}
    assert adapter.lookup_chain(value, ("User", "Name")) == "Ada"
    assert adapter.lookup_chain(value, ("User", "Missing", "Name")) is INVALID


def test_value_adapter_implements_go_template_truthiness() -> None:
    adapter = ValueAdapter()
    empty_values: tuple[object, ...] = (
        INVALID,
        UNTYPED_NIL,
        None,
        False,
        0,
        0.0,
        "",
        [],
        (),
        {},
    )
    for empty in empty_values:
        assert adapter.is_true(empty) is False
    nonempty_values: tuple[object, ...] = (
        True,
        1,
        -1,
        "x",
        [0],
        {"x": None},
        object(),
    )
    for nonempty in nonempty_values:
        assert adapter.is_true(nonempty) is True
