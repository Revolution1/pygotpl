from __future__ import annotations

import pytest

import gotpl


@pytest.mark.parametrize(
    ("source", "value", "expected"),
    [
        (
            '<script>if(true){/{{.}}/g.test("x")}</script>',
            "a.b",
            '<script>if(true){/a\\.b/g.test("x")}</script>',
        ),
        (
            '<script>if(true){x=1}/{{.}}/g.test("x")</script>',
            "a.b",
            '<script>if(true){x=1}/a\\.b/g.test("x")</script>',
        ),
        (
            '<script>if(true){/{{.}}/g.test("x")}</script>',
            "./;alert(1);var q=/.",
            '<script>if(true){/\\.\\/;alert\\(1\\);var q=\\/\\./g.test("x")}</script>',
        ),
        (
            "<script>`${ (function(){/{{.}}/g.test(x)}) }`</script>",
            "a.b",
            "<script>`${ (function(){/a\\.b/g.test(x)}) }`</script>",
        ),
        (
            "<script>`${ (function(){}/{{.}}/g.test(x)) }`</script>",
            "a.b",
            "<script>`${ (function(){}/a\\.b/g.test(x)) }`</script>",
        ),
    ],
)
def test_javascript_braces_preserve_regexp_escaping(
    source: str, value: str, expected: str
) -> None:
    """Prevent the JavaScript slash-context regression fixed by Go 1.27."""

    assert gotpl.render_html(source, value) == expected
