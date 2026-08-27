from pathlib import Path

import pytest

from examples.helm_runtime import HelmFiles, load_chart, load_values

FIXTURE = Path(__file__).parents[2] / "fixtures" / "helm" / "basic"


def test_load_chart_reads_metadata_defaults_templates_and_files() -> None:
    chart = load_chart(FIXTURE)

    assert chart.name == "basic"
    assert chart.version == "1.2.3"
    assert chart.values["name"] == "world"
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
