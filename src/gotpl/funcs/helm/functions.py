"""Helm v4-compatible additions to the pinned Sprig function map."""

from __future__ import annotations

import importlib
import json
import tomllib
from collections.abc import Callable, Mapping
from functools import lru_cache
from typing import Any, Protocol, cast

from gotpl.funcs.sprig import text_func_map

from .errors import MissingOptionalDependencyError


class _YamlModule(Protocol):
    SafeDumper: type[Any]
    SafeLoader: type[Any]

    def dump(
        self,
        data: object,
        *,
        Dumper: type[Any],
        allow_unicode: bool,
        default_flow_style: bool,
        indent: int,
        sort_keys: bool,
    ) -> str: ...

    def safe_load(self, stream: str) -> object: ...

    def load(self, stream: str, *, Loader: type[Any]) -> object: ...

    def safe_dump(
        self,
        data: object,
        *,
        allow_unicode: bool,
        default_flow_style: bool,
        indent: int,
        sort_keys: bool,
    ) -> str: ...


class _TomliWriter(Protocol):
    def dumps(self, data: Mapping[str, object]) -> str: ...


def _load_yaml() -> _YamlModule:
    try:
        return cast(_YamlModule, importlib.import_module("yaml"))
    except ImportError as error:
        raise MissingOptionalDependencyError(
            'Helm YAML functions require `pip install "gotpl[helm]"`'
        ) from error


def load_yaml(stream: str) -> object:
    """Load Helm YAML values without YAML timestamp coercion."""

    yaml = _load_yaml()
    return yaml.load(stream, Loader=_yaml_loader(yaml.SafeLoader))


@lru_cache(maxsize=2)
def _yaml_loader(base_loader: type[Any]) -> type[Any]:
    loader = type("_HelmSafeLoader", (base_loader,), {})
    loader.yaml_implicit_resolvers = {
        key: [
            (tag, pattern)
            for tag, pattern in resolvers
            if tag != "tag:yaml.org,2002:timestamp"
        ]
        for key, resolvers in base_loader.yaml_implicit_resolvers.items()
    }
    return loader


def _to_yaml(value: object, *, pretty: bool = False, must: bool = False) -> str:
    try:
        yaml = _load_yaml()
        rendered = yaml.dump(
            value,
            Dumper=_yaml_dumper(yaml.SafeDumper, pretty),
            allow_unicode=True,
            default_flow_style=False,
            indent=2,
            sort_keys=True,
        )
        return rendered.removesuffix("\n")
    except MissingOptionalDependencyError:
        raise
    except Exception:
        if must:
            raise
        return ""


@lru_cache(maxsize=4)
def _yaml_dumper(base_dumper: type[Any], pretty: bool) -> type[Any]:
    attributes: dict[str, object] = {}
    if pretty:

        def increase_indent(
            dumper: Any,
            flow: bool = False,
            indentless: bool = False,
        ) -> Any:
            del indentless
            return base_dumper.increase_indent(dumper, flow, False)

        attributes["increase_indent"] = increase_indent
    dumper = type(
        "_HelmPrettyDumper" if pretty else "_HelmDumper",
        (base_dumper,),
        attributes,
    )

    def represent_string(instance: Any, value: str) -> Any:
        node = base_dumper.represent_str(instance, value)
        resolved_tag = instance.resolve(type(node), value, (True, False))
        if "\n" in value:
            node.style = "|"
        elif node.style == "'" or resolved_tag != node.tag:
            node.style = '"'
        return node

    dumper.add_representer(str, represent_string)
    return dumper


def _from_yaml(value: str) -> dict[str, object]:
    try:
        parsed = load_yaml(value)
        if isinstance(parsed, dict):
            mapping = cast(Mapping[object, object], parsed)
            return {str(key): item for key, item in mapping.items()}
        return {}
    except MissingOptionalDependencyError:
        raise
    except Exception as error:
        return {"Error": str(error)}


def _from_yaml_array(value: str) -> list[object]:
    try:
        parsed = load_yaml(value)
        return cast(list[object], parsed) if isinstance(parsed, list) else []
    except MissingOptionalDependencyError:
        raise
    except Exception as error:
        return [str(error)]


def _to_toml(value: object, *, must: bool = False) -> str:
    try:
        module = cast(_TomliWriter, importlib.import_module("tomli_w"))
        if not isinstance(value, Mapping):
            raise TypeError("TOML root must be a mapping")
        mapping = cast(Mapping[object, object], value)
        rendered = module.dumps({str(key): item for key, item in mapping.items()})
        return _indent_toml_tables(rendered)
    except ImportError as error:
        raise MissingOptionalDependencyError(
            'Helm TOML functions require `pip install "gotpl[helm]"`'
        ) from error
    except Exception as error:
        if must:
            raise
        return str(error)


def _indent_toml_tables(source: str) -> str:
    """Match BurntSushi TOML's visual nesting for ordinary table output."""

    depth = 0
    output: list[str] = []
    for line in source.splitlines(keepends=True):
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            depth = _toml_table_depth(stripped)
            output.append(("  " * (depth - 1)) + line)
        elif stripped and depth:
            output.append(("  " * depth) + line)
        else:
            output.append(line)
    return "".join(output)


def _toml_table_depth(header: str) -> int:
    name = header[2:-2] if header.startswith("[[") else header[1:-1]
    depth = 1
    quote = ""
    escaped = False
    for character in name:
        if escaped:
            escaped = False
        elif quote == '"' and character == "\\":
            escaped = True
        elif quote:
            if character == quote:
                quote = ""
        elif character in {'"', "'"}:
            quote = character
        elif character == ".":
            depth += 1
    return depth


def _from_toml(value: str) -> dict[str, object]:
    try:
        return cast(dict[str, object], tomllib.loads(value))
    except Exception as error:
        return {"Error": str(error)}


def _from_json(value: str) -> dict[str, object]:
    try:
        parsed = json.loads(value)
        return cast(dict[str, object], parsed) if isinstance(parsed, dict) else {}
    except Exception as error:
        return {"Error": str(error)}


def _from_json_array(value: str) -> list[object]:
    try:
        parsed = json.loads(value)
        return cast(list[object], parsed) if isinstance(parsed, list) else []
    except Exception as error:
        return [str(error)]


def function_map(
    *,
    include: Callable[[str, object], object],
    tpl: Callable[[str, object], object],
    required: Callable[[str, object], object],
    fail: Callable[[str], object],
    lookup: Callable[[str, str, str, str], object] | None = None,
    enable_dns: bool = False,
    custom: Mapping[str, Callable[..., object]] | None = None,
) -> dict[str, Callable[..., object]]:
    """Return Helm's text function map with late-bound engine functions."""

    functions = text_func_map()
    functions.pop("env", None)
    functions.pop("expandenv", None)

    def to_toml(value: object) -> str:
        return _to_toml(value)

    def must_to_toml(value: object) -> str:
        return _to_toml(value, must=True)

    def must_to_yaml(value: object) -> str:
        return _to_yaml(value, must=True)

    def to_yaml_pretty(value: object) -> str:
        return _to_yaml(value, pretty=True)

    def empty_lookup(
        _api: str, _kind: str, _namespace: str, _name: str
    ) -> dict[str, object]:
        return {}

    additions: dict[str, Callable[..., object]] = {
        "toToml": to_toml,
        "mustToToml": must_to_toml,
        "fromToml": _from_toml,
        "toYaml": _to_yaml,
        "mustToYaml": must_to_yaml,
        "toYamlPretty": to_yaml_pretty,
        "fromYaml": _from_yaml,
        "fromYamlArray": _from_yaml_array,
        "fromJson": _from_json,
        "fromJsonArray": _from_json_array,
        "include": include,
        "tpl": tpl,
        "required": required,
        "fail": fail,
        "lookup": lookup or empty_lookup,
    }
    functions.update(additions)
    if not enable_dns:

        def disabled_dns(_name: str) -> str:
            return ""

        functions["getHostByName"] = disabled_dns
    if custom:
        functions.update(custom)
    return functions


__all__ = ["function_map"]
