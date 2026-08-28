from pathlib import Path

import pytest

from examples.helm_cli import (
    _assign,  # pyright: ignore[reportPrivateUsage]
    _manifests,  # pyright: ignore[reportPrivateUsage]
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


def test_cli_layers_values_files_and_omits_notes_and_empty_templates(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    chart = tmp_path / "chart"
    templates = chart / "templates"
    templates.mkdir(parents=True)
    (chart / "Chart.yaml").write_text("apiVersion: v2\nname: demo\nversion: 1.0.0\n")
    (chart / "values.yaml").write_text("image:\n  repository: default\n  tag: old\n")
    first = tmp_path / "first.yaml"
    first.write_text("image:\n  repository: custom\n")
    second = tmp_path / "second.yaml"
    second.write_text("image:\n  tag: latest\n")
    (templates / "deployment.yaml").write_text(
        "{{.Values.image.repository}}:{{.Values.image.tag}}\n"
    )
    (templates / "empty.yaml").write_text("{{if false}}unused{{end}}\n")
    (templates / "NOTES.txt").write_text("private release notes\n")

    result = main(
        ["template", "release", str(chart), "-f", str(first), "-f", str(second)]
    )

    assert result == 0
    output = capsys.readouterr().out
    assert output == "---\n# Source: demo/templates/deployment.yaml\ncustom:latest\n"


def test_cli_splits_and_orders_rendered_manifests_like_helm() -> None:
    output = {
        "demo/templates/workloads.yaml": (
            "kind: Deployment\nmetadata: {name: app}\n"
            "---\nkind: Service\nmetadata: {name: app}\n"
        ),
        "demo/templates/config.yaml": "kind: ConfigMap\nmetadata: {name: app}\n",
    }

    assert _manifests(output) == [
        (
            "demo/templates/config.yaml",
            "kind: ConfigMap\nmetadata: {name: app}",
        ),
        (
            "demo/templates/workloads.yaml",
            "kind: Service\nmetadata: {name: app}",
        ),
        (
            "demo/templates/workloads.yaml",
            "kind: Deployment\nmetadata: {name: app}",
        ),
    ]


def test_cli_reports_chart_errors_without_a_traceback(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    result = main(["template", "release", str(tmp_path / "missing")])

    assert result == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("Error: chart path ")
    assert "must be a directory" in captured.err


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
