import json
import re
from pathlib import Path
from typing import cast

import gotpl.funcs.sprig as sprig
from gotpl.parse.semantic import BUILTIN_FUNCTIONS

PROJECT_ROOT = Path(__file__).parents[2]
INVENTORY = PROJECT_ROOT / "docs" / "reports" / "sprig-v3.3.0-functions.json"


def test_sprig_inventory_is_complete_and_versioned() -> None:
    raw = cast(dict[str, object], json.loads(INVENTORY.read_text(encoding="utf-8")))
    names = cast(list[str], raw["function_names"])
    nonhermetic = cast(list[str], raw["nonhermetic_function_names"])

    assert raw["function_count"] == 211 == len(names) == len(set(names))
    assert raw["nonhermetic_function_count"] == 17 == len(nonhermetic)
    assert set(nonhermetic) < set(names)
    assert cast(dict[str, str], raw["reference"])["revision"] == "v3.3.0"


def test_sprig_function_maps_are_independent_mutable_copies() -> None:
    first = sprig.generic_func_map()
    second = sprig.text_func_map()
    html = sprig.html_func_map()
    hermetic_text = sprig.hermetic_text_func_map()
    hermetic_html = sprig.hermetic_html_func_map()

    first.pop("upper")

    assert "upper" in second
    assert set(second) == set(html)
    assert set(hermetic_text) == set(hermetic_html)
    assert set(hermetic_text) < set(second)
    assert set(second) - set(hermetic_text) == {
        "date",
        "dateInZone",
        "dateModify",
        "date_in_zone",
        "date_modify",
        "env",
        "expandenv",
        "getHostByName",
        "htmlDate",
        "htmlDateInZone",
        "now",
        "randAlpha",
        "randAlphaNum",
        "randAscii",
        "randBytes",
        "randNumeric",
        "uuidv4",
    }


def test_implemented_sprig_names_belong_to_the_target_inventory() -> None:
    raw = cast(dict[str, object], json.loads(INVENTORY.read_text(encoding="utf-8")))
    names = set(cast(list[str], raw["function_names"]))

    assert set(sprig.generic_func_map()) == names
    assert len(sprig.hermetic_text_func_map()) == 194


def test_every_sprig_name_has_explicit_behavioral_evidence() -> None:
    raw = cast(dict[str, object], json.loads(INVENTORY.read_text(encoding="utf-8")))
    names = cast(list[str], raw["function_names"])
    sources = [
        path
        for path in (PROJECT_ROOT / "tests" / "unit").glob("test_sprig*.py")
        if path.name != Path(__file__).name
    ]
    sources.extend(
        (PROJECT_ROOT / "tests" / "conformance" / "fixtures" / "sprig").glob("*.json")
    )
    evidence = "\n".join(path.read_text(encoding="utf-8") for path in sources)

    missing = [
        name
        for name in names
        if re.search(rf"(?<![A-Za-z0-9_]){re.escape(name)}(?![A-Za-z0-9_])", evidence)
        is None
    ]

    assert missing == []


def test_sprig_only_overrides_the_upstream_slice_builtin() -> None:
    functions = sprig.generic_func_map()

    assert set(functions) & BUILTIN_FUNCTIONS == {"slice"}
