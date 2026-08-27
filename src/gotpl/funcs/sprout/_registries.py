"""Implemented Sprout registries assembled from public compatibility APIs."""

from __future__ import annotations

import hashlib
import importlib
from base64 import b32decode, b32encode, b64decode, b64encode
from collections.abc import Callable
from typing import Protocol, cast

from gotpl._compat.gofmt.go import sprintf
from gotpl.funcs.sprig import generic_func_map
from gotpl.runtime import INVALID, UNTYPED_NIL, FunctionResult

from .errors import MissingOptionalDependencyError
from .inventory import INVENTORY
from .registry import FunctionRegistry, TemplateFunction

_SPRIG = generic_func_map()


class _YamlModule(Protocol):
    def safe_load(self, stream: str) -> object: ...

    def safe_dump(
        self,
        data: object,
        *,
        allow_unicode: bool,
        default_flow_style: bool,
        indent: int,
        sort_keys: bool,
    ) -> str: ...


def _metadata(name: str, functions: dict[str, TemplateFunction]) -> FunctionRegistry:
    inventory = INVENTORY.registries[name]
    if set(functions) != set(inventory.functions):
        raise RuntimeError(f"implemented {name} registry differs from inventory")
    return FunctionRegistry(
        name=name,
        uid=inventory.uid,
        functions=functions,
        aliases=inventory.aliases,
        notices=inventory.notices,
    )


def _md5_sum(value: str) -> str:
    return hashlib.md5(value.encode(), usedforsecurity=False).hexdigest()


def backward_registry() -> FunctionRegistry:
    return _metadata(
        "backward",
        {
            "fail": _SPRIG["fail"],
            "urlParse": _SPRIG["urlParse"],
            "urlJoin": _SPRIG["urlJoin"],
            "getHostByName": _SPRIG["getHostByName"],
        },
    )


def checksum_registry() -> FunctionRegistry:
    return _metadata(
        "checksum",
        {
            "sha1Sum": _SPRIG["sha1sum"],
            "sha256Sum": _SPRIG["sha256sum"],
            "sha512Sum": _SPRIG["sha512sum"],
            "adler32Sum": _SPRIG["adler32sum"],
            "md5Sum": _md5_sum,
        },
    )


def conversion_registry() -> FunctionRegistry:
    from ._conversion import functions

    return _metadata("conversion", functions())


def crypto_registry() -> FunctionRegistry:
    from ._crypto import functions

    return _metadata("crypto", functions())


def filesystem_registry() -> FunctionRegistry:
    return _metadata(
        "filesystem",
        {
            "pathBase": _SPRIG["base"],
            "pathDir": _SPRIG["dir"],
            "pathExt": _SPRIG["ext"],
            "pathClean": _SPRIG["clean"],
            "pathIsAbs": _SPRIG["isAbs"],
            "osBase": _SPRIG["osBase"],
            "osDir": _SPRIG["osDir"],
            "osExt": _SPRIG["osExt"],
            "osClean": _SPRIG["osClean"],
            "osIsAbs": _SPRIG["osIsAbs"],
        },
    )


def environment_registry() -> FunctionRegistry:
    return _metadata(
        "env",
        {
            "env": _SPRIG["env"],
            "expandEnv": _SPRIG["expandenv"],
        },
    )


def _result_with_prefix(
    function: Callable[[object], object], prefix: str, value: object
) -> FunctionResult:
    result = function(value)
    if not isinstance(result, FunctionResult):
        return FunctionResult.success(result)
    if result.error is None:
        return result
    return FunctionResult.failure(
        ValueError(f"{prefix}: {result.error}"), value=result.value
    )


def _base64_encode(value: str) -> str:
    return b64encode(value.encode()).decode()


def _base64_decode(value: str) -> FunctionResult:
    try:
        normalized = value.replace("\r", "").replace("\n", "")
        return FunctionResult.success(b64decode(normalized, validate=True).decode())
    except (UnicodeDecodeError, ValueError) as error:
        return FunctionResult.failure(ValueError(f"base64 decode error: {error}"))


def _base32_encode(value: str) -> str:
    return b32encode(value.encode()).decode()


def _base32_decode(value: str) -> FunctionResult:
    try:
        return FunctionResult.success(b32decode(value, casefold=False).decode())
    except (UnicodeDecodeError, ValueError) as error:
        return FunctionResult.failure(ValueError(f"base32 decode error: {error}"))


def _load_yaml() -> _YamlModule | FunctionResult:
    try:
        module = importlib.import_module("yaml")
    except ImportError:
        return FunctionResult.failure(
            MissingOptionalDependencyError(
                'YAML functions require `pip install "gotpl[yaml]"`'
            )
        )
    return cast(_YamlModule, module)


def _from_yaml(value: str) -> object:
    yaml = _load_yaml()
    if isinstance(yaml, FunctionResult):
        return yaml
    try:
        result = yaml.safe_load(value)
        return {} if result is None else result
    except Exception as error:
        return FunctionResult.failure(ValueError(f"yaml decode error: {error}"))


def _to_indent_yaml(indent: int, value: object) -> object:
    yaml = _load_yaml()
    if isinstance(yaml, FunctionResult):
        return yaml
    if value == "":
        return '""'
    try:
        return yaml.safe_dump(
            value,
            allow_unicode=True,
            default_flow_style=False,
            indent=indent,
            sort_keys=True,
        ).removesuffix("\n")
    except Exception as error:
        return FunctionResult.failure(ValueError(f"yaml encode error: {error}"))


def _to_yaml(value: object) -> object:
    return _to_indent_yaml(4, value)


def _from_json(value: object) -> FunctionResult:
    return _result_with_prefix(
        cast(Callable[[object], object], _SPRIG["mustFromJson"]),
        "json decode error",
        value,
    )


def _to_json(value: object) -> FunctionResult:
    return _result_with_prefix(
        cast(Callable[[object], object], _SPRIG["mustToJson"]),
        "json encode error",
        value,
    )


def _to_pretty_json(value: object) -> FunctionResult:
    return _result_with_prefix(
        cast(Callable[[object], object], _SPRIG["mustToPrettyJson"]),
        "json encode error",
        value,
    )


def _to_raw_json(value: object) -> FunctionResult:
    return _result_with_prefix(
        cast(Callable[[object], object], _SPRIG["mustToRawJson"]),
        "json encode error",
        value,
    )


def encoding_registry() -> FunctionRegistry:
    return _metadata(
        "encoding",
        {
            "base64Encode": _base64_encode,
            "base64Decode": _base64_decode,
            "base32Encode": _base32_encode,
            "base32Decode": _base32_decode,
            "fromJSON": _from_json,
            "toJSON": _to_json,
            "toPrettyJSON": _to_pretty_json,
            "toRawJSON": _to_raw_json,
            "fromYAML": _from_yaml,
            "toYAML": _to_yaml,
            "toIndentYAML": _to_indent_yaml,
        },
    )


def maps_registry() -> FunctionRegistry:
    from ._maps import functions

    return _metadata("maps", functions())


def network_registry() -> FunctionRegistry:
    from ._network import functions

    return _metadata("network", functions())


def numeric_registry() -> FunctionRegistry:
    from ._numeric import functions

    return _metadata("numeric", functions())


def random_registry() -> FunctionRegistry:
    from ._random import functions

    return _metadata("random", functions())


def _kind_of(value: object) -> object:
    if value is None or value is UNTYPED_NIL or value is INVALID:
        return FunctionResult.failure(ValueError("value must not be nil"))
    return _SPRIG["kindOf"](value)


def _kind_is(target: str, value: object) -> object:
    kind = _kind_of(value)
    if isinstance(kind, FunctionResult):
        return kind
    return kind == target


def _has_field(name: str, value: object) -> object:
    if (
        isinstance(
            value,
            (
                dict,
                list,
                tuple,
                set,
                frozenset,
                str,
                bytes,
                bytearray,
                int,
                float,
                bool,
            ),
        )
        or value is None
        or value is UNTYPED_NIL
        or value is INVALID
    ):
        return FunctionResult.failure(TypeError("last argument must be a struct"))
    return hasattr(value, name)


def _deep_copy(value: object) -> object:
    if value is None or value is UNTYPED_NIL or value is INVALID:
        return FunctionResult.failure(ValueError("value cannot be nil"))
    return _SPRIG["mustDeepCopy"](value)


def reflect_registry() -> FunctionRegistry:
    return _metadata(
        "reflect",
        {
            "typeIs": _SPRIG["typeIs"],
            "typeIsLike": _SPRIG["typeIsLike"],
            "typeOf": _SPRIG["typeOf"],
            "kindIs": _kind_is,
            "kindOf": _kind_of,
            "hasField": _has_field,
            "deepEqual": _SPRIG["deepEqual"],
            "deepCopy": _deep_copy,
        },
    )


def regex_registry() -> FunctionRegistry:
    from ._regex import regex_functions

    return _metadata("regex", regex_functions())


def regexp_registry() -> FunctionRegistry:
    from ._regex import regexp_functions

    return _metadata("regexp", regexp_functions())


def semver_registry() -> FunctionRegistry:
    return _metadata(
        "semver",
        {
            "semver": _SPRIG["semver"],
            "semverCompare": _SPRIG["semverCompare"],
        },
    )


def slices_registry() -> FunctionRegistry:
    from ._slices import functions

    return _metadata("slices", functions())


def strings_registry() -> FunctionRegistry:
    from ._strings import functions

    return _metadata("strings", functions())


def time_registry() -> FunctionRegistry:
    from ._time import functions

    return _metadata("time", functions())


def uniqueid_registry() -> FunctionRegistry:
    from ._uniqueid import functions

    return _metadata("uniqueid", functions())


def _cat(*values: object) -> str:
    output = ""
    for index, value in enumerate(values):
        if value is None or value is UNTYPED_NIL or value is INVALID:
            continue
        if index > 0:
            output += " "
        output += sprintf("%v", value)
    return output


def std_registry() -> FunctionRegistry:
    return _metadata(
        "std",
        {
            "hello": _SPRIG["hello"],
            "default": _SPRIG["default"],
            "empty": _SPRIG["empty"],
            "all": _SPRIG["all"],
            "any": _SPRIG["any"],
            "coalesce": _SPRIG["coalesce"],
            "ternary": _SPRIG["ternary"],
            "cat": _cat,
        },
    )
