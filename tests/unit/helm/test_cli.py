from pathlib import Path

import pytest

from examples.helm_cli import (
    _assign,  # pyright: ignore[reportPrivateUsage]
    _merge,  # pyright: ignore[reportPrivateUsage]
    _scalar,  # pyright: ignore[reportPrivateUsage]
    main,
)

FIXTURE = Path(__file__).parents[2] / "fixtures" / "helm" / "basic"


def test_miniature_helm_cli_renders_a_chart(
    capsys: pytest.CaptureFixture[str],
) -> None:
    result = main(
        [
            "template",
            "demo",
            str(FIXTURE),
            "--namespace",
            "testing",
            "--set",
            "name=Python",
        ]
    )

    assert result == 0
    captured = capsys.readouterr()
    assert "# Source: basic/templates/configmap.yaml" in captured.out
    assert "name: demo-basic" in captured.out
    assert 'greeting: "hello Python"' in captured.out


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("true", True),
        ("FALSE", False),
        ("null", None),
        ("nil", None),
        ("42", 42),
        ("1.25", 1.25),
        ("value", "value"),
    ],
)
def test_cli_scalar_conversion(source: str, expected: object) -> None:
    assert _scalar(source) == expected


def test_cli_assignment_builds_nested_values_and_rejects_invalid_paths() -> None:
    values: dict[str, object] = {}
    _assign(values, "image.repository=example/app")
    _assign(values, "image.tag=3")
    assert values == {"image": {"repository": "example/app", "tag": 3}}

    with pytest.raises(ValueError, match="invalid --set assignment"):
        _assign(values, "missing-separator")
    with pytest.raises(ValueError, match="non-mapping key 'image'"):
        _assign({"image": "not-a-map"}, "image.tag=latest")


def test_cli_merge_recurses_without_mutating_inputs() -> None:
    left: dict[str, object] = {
        "image": {"repository": "old", "tag": 1},
        "keep": True,
    }
    right: dict[str, object] = {"image": {"repository": "new"}, "keep": False}

    assert _merge(left, right) == {
        "image": {"repository": "new", "tag": 1},
        "keep": False,
    }
    assert left == {"image": {"repository": "old", "tag": 1}, "keep": True}
