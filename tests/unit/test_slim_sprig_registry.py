import json
import math
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import gotpl.funcs.slim_sprig as slim_sprig

PROJECT_ROOT = Path(__file__).parents[2]
INVENTORY = PROJECT_ROOT / "docs" / "reports" / "slim-sprig-v3.0.0-functions.json"


def test_slim_sprig_inventory_is_complete_and_versioned() -> None:
    raw = cast(dict[str, object], json.loads(INVENTORY.read_text(encoding="utf-8")))
    names = cast(list[str], raw["function_names"])
    nonhermetic = cast(list[str], raw["nonhermetic_function_names"])

    assert raw["function_count"] == 164 == len(names) == len(set(names))
    assert raw["nonhermetic_function_count"] == 11 == len(nonhermetic)
    assert set(nonhermetic) < set(names)
    assert cast(dict[str, str], raw["reference"])["revision"] == "v3.0.0"
    assert set(slim_sprig.generic_func_map()) == set(names)


def test_slim_sprig_maps_are_isolated_copies_of_the_pinned_profile() -> None:
    first = slim_sprig.generic_func_map()
    second = slim_sprig.text_func_map()

    assert len(first) == 164
    assert first.keys() == second.keys()
    assert "upper" in first
    assert "semver" not in first
    assert "merge" not in first
    assert "sha512sum" not in first
    first["custom"] = lambda: "value"
    assert "custom" not in second


def test_slim_sprig_html_and_hermetic_profiles_are_explicit() -> None:
    html = slim_sprig.html_func_map()
    hermetic_text = slim_sprig.hermetic_text_func_map()
    hermetic_html = slim_sprig.hermetic_html_func_map()

    assert html.keys() == slim_sprig.generic_func_map().keys()
    assert hermetic_text.keys() == hermetic_html.keys()
    assert len(hermetic_text) == 153
    assert set(hermetic_text) < set(html)


def test_slim_sprig_map_values_are_template_functions() -> None:
    assert all(
        isinstance(function, Callable)
        for function in slim_sprig.generic_func_map().values()
    )


def test_slim_sprig_forwards_clock_injection() -> None:
    fixed = datetime(2024, 7, 9, tzinfo=UTC)
    functions = slim_sprig.text_func_map(clock=lambda: fixed)

    assert functions["now"]() == fixed


def test_slim_sprig_forwards_external_state_injection() -> None:
    functions = slim_sprig.text_func_map(
        randbelow=lambda _width: 0,
        environ={"NAME": "Ada"},
        resolver=lambda _name: ["192.0.2.1"],
    )

    assert functions["randInt"](4, 5) == 4
    assert functions["env"]("NAME") == "Ada"
    assert functions["getHostByName"]("example.test") == "192.0.2.1"


def test_slim_sprig_retains_its_decimal_only_integer_casts() -> None:
    functions = slim_sprig.generic_func_map()

    assert [functions["int"](value) for value in ("1.0", "0x10", "010", "08")] == [
        0,
        0,
        10,
        8,
    ]
    assert functions["add"]("0x10", 1) == 1


def test_slim_sprig_integer_casts_follow_int64_boundaries() -> None:
    integer = slim_sprig.generic_func_map()["int64"]

    assert integer(True) == 1
    assert integer((1 << 63) + 1) == (1 << 63) - 1
    assert integer(-(1 << 63) - 1) == -(1 << 63)
    assert integer(1.9) == 1
    assert integer(float(1 << 63)) == -(1 << 63)
    assert integer(math.inf) == -(1 << 63)
    assert integer(str(1 << 63)) == 0
    assert integer(object()) == 0
