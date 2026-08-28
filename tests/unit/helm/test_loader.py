import io
import tarfile
from pathlib import Path

import pytest

from examples.helm_runtime import HelmFiles, load_chart, load_values

FIXTURE = Path(__file__).parents[2] / "fixtures" / "helm" / "basic"


def test_load_chart_reads_metadata_defaults_templates_and_files() -> None:
    chart = load_chart(FIXTURE)

    assert chart.name == "basic"
    assert chart.version == "1.2.3"
    assert chart.values["name"] == "world"
    assert chart.annotations == {"example.com/profile": "basic"}
    assert "templates/configmap.yaml" in chart.templates
    assert isinstance(chart.files, HelmFiles)
    assert chart.files.Get("files/script.sh") == "#!/bin/sh\necho ready\n"


def test_load_chart_requires_a_directory_and_valid_chart_metadata(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError, match="directory"):
        load_chart(tmp_path / "missing")
    with pytest.raises(ValueError, match=r"Chart\.yaml"):
        load_chart(tmp_path)


def test_load_values_requires_a_yaml_mapping(tmp_path: Path) -> None:
    values = tmp_path / "values.yaml"
    values.write_text("- not\n- a\n- mapping\n")

    with pytest.raises(ValueError, match="mapping"):
        load_values(values)


def test_load_values_keeps_yaml_dates_as_helm_strings(tmp_path: Path) -> None:
    values = tmp_path / "values.yaml"
    values.write_text("date: 2024-04-01\nlegacyBoolean: yes\n")

    assert load_values(values) == {"date": "2024-04-01", "legacyBoolean": True}


def test_load_chart_reads_packaged_dependencies(tmp_path: Path) -> None:
    root = tmp_path / "parent"
    charts = root / "charts"
    child = tmp_path / "child"
    (root / "templates").mkdir(parents=True)
    charts.mkdir()
    (child / "templates").mkdir(parents=True)
    (root / "Chart.yaml").write_text("apiVersion: v2\nname: parent\nversion: 1.0.0\n")
    (child / "Chart.yaml").write_text("apiVersion: v2\nname: child\nversion: 2.0.0\n")
    (child / "templates" / "configmap.yaml").write_text("kind: ConfigMap\n")
    with tarfile.open(charts / "child-2.0.0.tgz", "w:gz") as archive:
        archive.add(child, arcname="child")

    chart = load_chart(root)

    assert len(chart.dependencies) == 1
    assert chart.dependencies[0].name == "child"
    assert chart.dependencies[0].templates == {
        "templates/configmap.yaml": "kind: ConfigMap\n"
    }


def test_load_chart_applies_dependency_alias_condition_and_tags(tmp_path: Path) -> None:
    root = tmp_path / "parent"
    child = root / "charts" / "database"
    child.mkdir(parents=True)
    (root / "Chart.yaml").write_text(
        "apiVersion: v2\n"
        "name: parent\n"
        "version: 1.0.0\n"
        "dependencies:\n"
        "  - name: database\n"
        "    version: 2.0.0\n"
        "    repository: file://charts/database\n"
        "    alias: primary\n"
        "    condition: primary.enabled\n"
        "    tags: [storage]\n"
    )
    (child / "Chart.yaml").write_text(
        "apiVersion: v2\nname: database\nversion: 2.0.0\n"
    )

    chart = load_chart(root)

    assert len(chart.dependencies) == 1
    dependency = chart.dependencies[0]
    assert dependency.name == "primary"
    assert dependency.dependency_condition == "primary.enabled"
    assert dependency.dependency_tags == ("storage",)


def test_load_chart_rejects_unsafe_packaged_dependency_paths(tmp_path: Path) -> None:
    root = tmp_path / "parent"
    charts = root / "charts"
    charts.mkdir(parents=True)
    (root / "Chart.yaml").write_text("apiVersion: v2\nname: parent\nversion: 1.0.0\n")
    with tarfile.open(charts / "unsafe.tgz", "w:gz") as archive:
        member = tarfile.TarInfo("../outside")
        member.size = 1
        archive.addfile(member, io.BytesIO(b"x"))

    with pytest.raises(ValueError, match="unsafe path"):
        load_chart(root)
