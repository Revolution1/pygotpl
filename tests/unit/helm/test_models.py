import pytest

from examples.helm_runtime import APIVersions, Capabilities, HelmVersion, KubeVersion


def test_kube_version_parses_vendor_versions_and_exposes_helm_fields() -> None:
    version = KubeVersion.parse("1.33.4-gke.1245000")

    assert version.version == "v1.33.4-gke.1245000"
    assert version.major == "1"
    assert version.minor == "33"
    assert str(version) == "v1.33.4"
    assert version.Version == version.GitVersion() == version.version
    assert version.Major == version.major
    assert version.Minor == version.minor


@pytest.mark.parametrize("value", ["", "v1", "latest", "v1.x.0"])
def test_kube_version_rejects_invalid_versions(value: str) -> None:
    with pytest.raises(ValueError, match="invalid Kubernetes version"):
        KubeVersion.parse(value)


def test_api_versions_preserve_order_duplicates_and_sequence_behavior() -> None:
    versions = APIVersions(("v1", "apps/v1", "v1"))

    assert tuple(versions) == ("v1", "apps/v1", "v1")
    assert len(versions) == 3
    assert versions[1] == "apps/v1"
    assert versions.Has("apps/v1")
    assert not versions.Has("unexpected/v1")


def test_default_capabilities_match_the_pinned_helm_build_metadata() -> None:
    capabilities = Capabilities.default()

    assert capabilities.api_versions.Has("apps/v1")
    assert capabilities.api_versions.Has("apiextensions.k8s.io/v1")
    assert len(capabilities.api_versions) == 55
    assert capabilities.helm_version == HelmVersion(
        version="v4.2",
        kube_client_version="v1.36",
        go_version="go1.27.0",
    )
