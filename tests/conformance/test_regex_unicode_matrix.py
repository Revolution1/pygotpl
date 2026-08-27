from gotpl._compat.goregexp._unicode_properties import property_class_contents
from gotpl._compat.goregexp._unicode_tables import CATEGORY_ALIASES, PROPERTY_RANGES
from gotpl.funcs.sprig.regex import regex_match

from .support import TemplateRequest, run_go_oracle_many


def _representative(name: str) -> str:
    for lower, upper, stride in PROPERTY_RANGES[name]:
        for value in range(lower, upper + 1, stride):
            if not 0xD800 <= value <= 0xDFFF:
                return chr(value)
    raise AssertionError(f"property {name} has no Unicode scalar representative")


def test_every_go_accessible_unicode_table_has_differential_evidence() -> None:
    names = sorted(name for name in PROPERTY_RANGES if "_" not in name)
    # Surrogate code points cannot occur as decoded Go runes.
    excluded = {"Cs"}
    cases = [(name, _representative(name)) for name in names if name not in excluded]
    requests = [
        TemplateRequest(
            engine="text",
            name=f"unicode-property-{index}",
            template=f'{{{{regexMatch "\\\\p{{{name}}}" .Value}}}}',
            data={"Value": value},
            function_profile="sprig-hermetic",
        )
        for index, (name, value) in enumerate(cases)
    ]

    expected = run_go_oracle_many(requests)
    failures = [
        (name, result)
        for (name, _value), result in zip(cases, expected, strict=True)
        if result != {"output": "true", "error": None}
    ]

    assert len(cases) > 100
    assert failures == []
    assert all(regex_match(rf"\p{{{name}}}", value) for name, value in cases)


def test_every_go_category_alias_resolves_to_the_generated_target() -> None:
    for alias, target in CATEGORY_ALIASES.items():
        assert property_class_contents(alias) == property_class_contents(target)


def test_generated_property_tables_have_valid_ranges() -> None:
    for ranges in PROPERTY_RANGES.values():
        previous_upper = -1
        for lower, upper, stride in ranges:
            assert 0 <= lower <= upper <= 0x10FFFF
            assert stride >= 1
            assert lower > previous_upper
            previous_upper = upper
