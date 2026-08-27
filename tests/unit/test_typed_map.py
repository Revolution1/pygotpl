import pytest

import gotpl


def test_typed_map_behaves_as_a_normal_mapping_for_present_values() -> None:
    values = gotpl.TypedMap({"present": 7}, zero=0)

    assert len(values) == 1
    assert list(values) == ["present"]
    assert values["present"] == 7
    assert gotpl.render("{{.present}}", values) == "7"


def test_typed_map_supplies_zero_for_missingkey_zero_and_index() -> None:
    values = gotpl.TypedMap({"present": 7}, zero=0)

    assert gotpl.render("{{.missing}}", values) == "<no value>"
    assert gotpl.render("{{.missing}}", values, missing_key="zero") == "0"
    assert gotpl.render('{{index . "missing"}}', values) == "0"


def test_typed_map_still_honors_missingkey_error() -> None:
    values = gotpl.TypedMap[str, bool]({}, zero=False)

    with pytest.raises(gotpl.TemplateExecutionError, match="missing"):
        gotpl.render("{{.missing}}", values, missing_key="error")


def test_ordinary_output_uses_go_byte_and_pointer_representations() -> None:
    target = object()
    pointer = gotpl.GoPointer(target, target_type="widget")

    assert gotpl.render("{{.}}", b"A") == "[65]"
    assert gotpl.render("{{.}}", pointer) == f"0x{id(target):x}"


def test_nil_go_pointer_is_false_in_control_actions() -> None:
    pointer = gotpl.GoPointer[object](None, target_type="widget")

    assert gotpl.render("{{if .}}set{{else}}empty{{end}}", pointer) == "empty"
