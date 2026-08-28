"""Models owned by the miniature Helm runtime example."""

from __future__ import annotations

import re
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

from .files import HelmFiles

_KUBE_VERSION_PATTERN = re.compile(
    r"^v?(?P<major>[0-9]+)\.(?P<minor>[0-9]+)"
    r"(?:\.(?P<patch>[0-9]+))?(?P<suffix>[-+].*)?$"
)

# Helm v4.2.3 with client-go v0.36.0. Regenerate this tuple when the pinned
# Helm reference changes; order is observable when templates range over it.
_DEFAULT_API_VERSIONS = (
    "v1",
    "admissionregistration.k8s.io/v1",
    "admissionregistration.k8s.io/v1alpha1",
    "admissionregistration.k8s.io/v1beta1",
    "internal.apiserver.k8s.io/v1alpha1",
    "apps/v1",
    "apps/v1beta1",
    "apps/v1beta2",
    "authentication.k8s.io/v1",
    "authentication.k8s.io/v1alpha1",
    "authentication.k8s.io/v1beta1",
    "authorization.k8s.io/v1",
    "authorization.k8s.io/v1beta1",
    "autoscaling/v1",
    "autoscaling/v2",
    "batch/v1",
    "batch/v1beta1",
    "certificates.k8s.io/v1",
    "certificates.k8s.io/v1beta1",
    "certificates.k8s.io/v1alpha1",
    "coordination.k8s.io/v1alpha2",
    "coordination.k8s.io/v1beta1",
    "coordination.k8s.io/v1",
    "discovery.k8s.io/v1",
    "discovery.k8s.io/v1beta1",
    "events.k8s.io/v1",
    "events.k8s.io/v1beta1",
    "extensions/v1beta1",
    "flowcontrol.apiserver.k8s.io/v1",
    "flowcontrol.apiserver.k8s.io/v1beta1",
    "flowcontrol.apiserver.k8s.io/v1beta2",
    "flowcontrol.apiserver.k8s.io/v1beta3",
    "networking.k8s.io/v1",
    "networking.k8s.io/v1beta1",
    "node.k8s.io/v1",
    "node.k8s.io/v1alpha1",
    "node.k8s.io/v1beta1",
    "policy/v1",
    "policy/v1beta1",
    "rbac.authorization.k8s.io/v1",
    "rbac.authorization.k8s.io/v1beta1",
    "rbac.authorization.k8s.io/v1alpha1",
    "resource.k8s.io/v1",
    "resource.k8s.io/v1beta2",
    "resource.k8s.io/v1beta1",
    "resource.k8s.io/v1alpha3",
    "scheduling.k8s.io/v1alpha2",
    "scheduling.k8s.io/v1beta1",
    "scheduling.k8s.io/v1",
    "storage.k8s.io/v1beta1",
    "storage.k8s.io/v1",
    "storage.k8s.io/v1alpha1",
    "storagemigration.k8s.io/v1beta1",
    "apiextensions.k8s.io/v1beta1",
    "apiextensions.k8s.io/v1",
)


def _empty_values() -> Mapping[str, object]:
    return {}


def _empty_annotations() -> Mapping[str, str]:
    return {}


@dataclass(frozen=True, slots=True)
class Release:
    """Helm release information exposed as the `.Release` global."""

    name: str = "RELEASE-NAME"
    namespace: str = "default"
    is_upgrade: bool = False
    is_install: bool = True
    revision: int = 1
    service: str = "Helm"

    def as_values(self) -> Mapping[str, object]:
        return MappingProxyType(
            {
                "Name": self.name,
                "Namespace": self.namespace,
                "IsUpgrade": self.is_upgrade,
                "IsInstall": self.is_install,
                "Revision": self.revision,
                "Service": self.service,
            }
        )


@dataclass(frozen=True, slots=True)
class KubeVersion:
    """Kubernetes version information exposed by Helm capabilities."""

    version: str = "v1.36.0"
    major: str = "1"
    minor: str = "36"
    _normalized_version: str = field(default="v1.36.0", repr=False)

    @classmethod
    def parse(cls, value: str) -> KubeVersion:
        """Parse a Kubernetes version while preserving vendor suffixes."""

        match = _KUBE_VERSION_PATTERN.fullmatch(value)
        if match is None:
            raise ValueError(f"invalid Kubernetes version {value!r}")
        major = match.group("major")
        minor = match.group("minor")
        patch = match.group("patch")
        normalized = f"v{major}.{minor}"
        if patch is not None:
            normalized += f".{patch}"
        return cls(
            version=value if value.startswith("v") else f"v{value}",
            major=major,
            minor=minor,
            _normalized_version=normalized,
        )

    @property
    def Version(self) -> str:
        return self.version

    @property
    def Major(self) -> str:
        return self.major

    @property
    def Minor(self) -> str:
        return self.minor

    def GitVersion(self) -> str:
        return self.version

    def __str__(self) -> str:
        return self._normalized_version

    def as_values(self) -> Mapping[str, str]:
        return MappingProxyType(
            {"Version": self.version, "Major": self.major, "Minor": self.minor}
        )


@dataclass(frozen=True, slots=True)
class APIVersions:
    """Immutable API-version set with Helm's `Has` method."""

    values: tuple[str, ...] = ()

    def __init__(self, values: Iterable[str] = ()) -> None:
        object.__setattr__(self, "values", tuple(values))

    def __iter__(self) -> Iterator[str]:
        return iter(self.values)

    def __len__(self) -> int:
        return len(self.values)

    def __getitem__(self, index: int) -> str:
        return self.values[index]

    def Has(self, version: str) -> bool:
        return version in self.values

    has = Has


@dataclass(frozen=True, slots=True)
class HelmVersion:
    """Build information exposed by Helm's `.Capabilities.HelmVersion`."""

    version: str = "v4.2"
    git_commit: str = ""
    git_tree_state: str = ""
    go_version: str = "go1.27.0"
    kube_client_version: str = "v1.36"

    @property
    def Version(self) -> str:
        return self.version

    @property
    def GitCommit(self) -> str:
        return self.git_commit

    @property
    def GitTreeState(self) -> str:
        return self.git_tree_state

    @property
    def GoVersion(self) -> str:
        return self.go_version

    @property
    def KubeClientVersion(self) -> str:
        return self.kube_client_version


@dataclass(frozen=True, slots=True)
class Capabilities:
    """Cluster and Helm capabilities available during rendering."""

    kube_version: KubeVersion = field(default_factory=KubeVersion)
    api_versions: APIVersions = field(
        default_factory=lambda: APIVersions(_DEFAULT_API_VERSIONS)
    )
    helm_version: HelmVersion = field(default_factory=HelmVersion)

    @classmethod
    def default(cls) -> Capabilities:
        return cls()

    def as_values(self) -> Mapping[str, object]:
        return MappingProxyType(
            {
                "KubeVersion": self.kube_version,
                "APIVersions": self.api_versions,
                "HelmVersion": self.helm_version,
            }
        )


@dataclass(frozen=True, slots=True)
class Chart:
    """A chart's metadata, templates, files, defaults, and dependencies."""

    name: str
    version: str
    templates: Mapping[str, str]
    api_version: str = "v2"
    app_version: str = ""
    chart_type: str = "application"
    description: str = ""
    annotations: Mapping[str, str] = field(default_factory=_empty_annotations)
    values: Mapping[str, object] = field(default_factory=_empty_values)
    files: HelmFiles | Mapping[str, str | bytes] = field(default_factory=HelmFiles)
    dependencies: tuple[Chart, ...] = ()
    dependency_condition: str = ""
    dependency_tags: tuple[str, ...] = ()
    dependency_import_values: tuple[object, ...] = ()

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("chart name must not be empty")
        if not self.version:
            raise ValueError("chart version must not be empty")
        if self.chart_type not in {"application", "library"}:
            raise ValueError("chart type must be application or library")
        object.__setattr__(self, "templates", MappingProxyType(dict(self.templates)))
        object.__setattr__(
            self, "annotations", MappingProxyType(dict(self.annotations))
        )
        object.__setattr__(self, "values", MappingProxyType(dict(self.values)))
        if not isinstance(self.files, HelmFiles):
            object.__setattr__(self, "files", HelmFiles(self.files))
        object.__setattr__(self, "dependencies", tuple(self.dependencies))
        object.__setattr__(self, "dependency_tags", tuple(self.dependency_tags))
        object.__setattr__(
            self, "dependency_import_values", tuple(self.dependency_import_values)
        )

    def metadata_values(self, *, is_root: bool) -> Mapping[str, object]:
        return MappingProxyType(
            {
                "Name": self.name,
                "Version": self.version,
                "APIVersion": self.api_version,
                "AppVersion": self.app_version,
                "Type": self.chart_type,
                "Description": self.description,
                "Annotations": self.annotations,
                "IsRoot": is_root,
            }
        )
