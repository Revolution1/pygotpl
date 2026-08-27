import pytest

import gotpl


def test_go_seq_exposes_values_and_rejects_two_bindings() -> None:
    values = gotpl.GoSeq(["a", "b"])

    assert gotpl.render("{{range .}}{{.}};{{end}}", values) == "a;b;"
    assert gotpl.render("{{range $value := .}}{{$value}};{{end}}", values) == ("a;b;")
    with pytest.raises(gotpl.TemplateExecutionError, match="more than one"):
        gotpl.render("{{range $key, $value := .}}{{end}}", values)


def test_go_seq2_exposes_keys_with_one_binding_and_pairs_with_two() -> None:
    values = gotpl.GoSeq2([("a", 1), ("b", 2)])

    assert gotpl.render("{{range .}}{{.}};{{end}}", values) == "a;b;"
    assert gotpl.render("{{range $key := .}}{{$key}};{{end}}", values) == "a;b;"
    assert (
        gotpl.render("{{range $key, $value := .}}{{$key}}={{$value}};{{end}}", values)
        == "a=1;b=2;"
    )


def test_go_sequences_enter_range_else_when_empty() -> None:
    sequence = gotpl.GoSeq[object]([])
    pairs = gotpl.GoSeq2[object, object]([])

    assert gotpl.render("{{range .}}set{{else}}empty{{end}}", sequence) == "empty"
    assert gotpl.render("{{range .}}set{{else}}empty{{end}}", pairs) == "empty"
