"""A deliberately small, pure Python `helm template` example."""

from __future__ import annotations

import argparse
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
    for name in sorted(output):
        sys.stdout.write(f"---\n# Source: {name}\n{output[name]}")
        if not output[name].endswith("\n"):
            sys.stdout.write("\n")
    return 0


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
