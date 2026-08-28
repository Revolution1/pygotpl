"""A deliberately small, pure Python `helm template` example."""

from __future__ import annotations

import argparse
import re
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import cast

from examples.helm_runtime import (
    Capabilities,
    Engine,
    KubeVersion,
    Release,
    load_chart,
    load_values,
)
from gotpl.errors import TemplateError
from gotpl.funcs.helm import MissingOptionalDependencyError

_MANIFEST_SPLITTER = re.compile(r"(?:^|\s*\n)---\s*(?:\n|$)")
_KIND = re.compile(r'^\s*kind:\s*["\']?([^\s"\']+)', re.MULTILINE)
_INSTALL_ORDER = (
    "Namespace",
    "NetworkPolicy",
    "ResourceQuota",
    "LimitRange",
    "PodSecurityPolicy",
    "PodDisruptionBudget",
    "Secret",
    "ConfigMap",
    "StorageClass",
    "PersistentVolume",
    "PersistentVolumeClaim",
    "ServiceAccount",
    "CustomResourceDefinition",
    "ClusterRole",
    "ClusterRoleList",
    "ClusterRoleBinding",
    "ClusterRoleBindingList",
    "Role",
    "RoleList",
    "RoleBinding",
    "RoleBindingList",
    "Service",
    "DaemonSet",
    "Pod",
    "ReplicationController",
    "ReplicaSet",
    "Deployment",
    "HorizontalPodAutoscaler",
    "StatefulSet",
    "Job",
    "CronJob",
    "IngressClass",
    "Ingress",
    "APIService",
)
_KIND_ORDER = {kind: index for index, kind in enumerate(_INSTALL_ORDER)}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="gotpl-helm")
    commands = parser.add_subparsers(dest="command", required=True)
    template = commands.add_parser("template", help="render an unpacked chart")
    template.add_argument("release")
    template.add_argument("chart", type=Path)
    template.add_argument("-f", "--values", action="append", type=Path, default=[])
    template.add_argument("--set", action="append", default=[])
    template.add_argument("--namespace", default="default")
    template.add_argument("--kube-version", default="v1.36.0")
    template.add_argument("--strict", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the miniature Helm renderer and return a process exit code."""

    arguments = _parser().parse_args(argv)
    try:
        return _run(arguments)
    except (
        OSError,
        TemplateError,
        MissingOptionalDependencyError,
        ValueError,
    ) as error:
        sys.stderr.write(f"Error: {error}\n")
        return 1


def _run(arguments: argparse.Namespace) -> int:
    chart = load_chart(arguments.chart)
    values: dict[str, object] = {}
    for path in cast(list[Path], arguments.values):
        values = _merge(values, load_values(path))
    for assignment in cast(list[str], arguments.set):
        _assign(values, assignment)
    kube = _parse_kube_version(cast(str, arguments.kube_version))
    output = Engine(strict=cast(bool, arguments.strict)).render(
        chart,
        values,
        release=Release(
            name=cast(str, arguments.release),
            namespace=cast(str, arguments.namespace),
        ),
        capabilities=Capabilities(kube_version=kube),
    )
    for index, (name, rendered) in enumerate(_manifests(output)):
        if index:
            sys.stdout.write("\n")
        sys.stdout.write(f"---\n# Source: {name}\n{rendered}")
        sys.stdout.write("\n")
    return 0


def _manifests(output: dict[str, str]) -> list[tuple[str, str]]:
    manifests: list[tuple[int, str, int, str]] = []
    unknown_order = len(_INSTALL_ORDER)
    for name in sorted(output):
        if Path(name).name == "NOTES.txt":
            continue
        documents = _MANIFEST_SPLITTER.split(output[name])
        for document_index, document in enumerate(documents):
            rendered = document.strip()
            if not rendered:
                continue
            match = _KIND.search(rendered)
            kind = match.group(1) if match is not None else ""
            manifests.append(
                (_KIND_ORDER.get(kind, unknown_order), name, document_index, rendered)
            )
    manifests.sort(key=lambda item: item[:3])
    return [(name, rendered) for _, name, _, rendered in manifests]


def _assign(values: dict[str, object], assignment: str) -> None:
    if "=" not in assignment:
        raise ValueError(f"invalid --set assignment {assignment!r}")
    path, raw = assignment.split("=", 1)
    keys = path.split(".")
    target = values
    for key in keys[:-1]:
        child = target.setdefault(key, {})
        if not isinstance(child, dict):
            raise ValueError(f"cannot assign through non-mapping key {key!r}")
        target = cast(dict[str, object], child)
    target[keys[-1]] = _scalar(raw)


def _scalar(value: str) -> object:
    lowered = value.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    if lowered in {"null", "nil"}:
        return None
    try:
        return int(value, 10)
    except ValueError:
        try:
            return float(value)
        except ValueError:
            return value


def _parse_kube_version(value: str) -> KubeVersion:
    return KubeVersion.parse(value)


def _merge(left: dict[str, object], right: dict[str, object]) -> dict[str, object]:
    result = dict(left)
    for key, value in right.items():
        current = result.get(key)
        if isinstance(current, dict) and isinstance(value, dict):
            result[key] = _merge(
                cast(dict[str, object], current), cast(dict[str, object], value)
            )
        else:
            result[key] = value
    return result


if __name__ == "__main__":
    raise SystemExit(main())
