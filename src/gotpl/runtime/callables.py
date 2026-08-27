"""Python callable adaptation for Go-style template functions."""

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from functools import lru_cache
from inspect import Parameter, Signature, signature
from types import MappingProxyType, UnionType
from typing import Any, Literal, Union, get_args, get_origin


class TemplateCallArityError(TypeError):
    """An internal, stable positional-argument mismatch."""


class TemplateCallTypeError(TypeError):
    """An internal, stable annotated-argument mismatch."""


@dataclass(frozen=True, slots=True)
class CallSpec:
    """The positional subset of a Python callable signature."""

    minimum: int
    maximum: int | None
    required_keyword_only: tuple[str, ...]
    positional_annotations: tuple[object, ...]
    variadic_annotation: object
    requires_validation: bool

    @property
    def requires_type_validation(self) -> bool:
        """Whether invocation must check runtime argument types."""

        return any(
            _annotation_is_enforceable(item)
            for item in (*self.positional_annotations, self.variadic_annotation)
        )

    def arity_error(self, name: str, count: int) -> str | None:
        """Return a Go-style error when *count* cannot satisfy this signature."""

        if count >= self.minimum and (self.maximum is None or count <= self.maximum):
            return None
        if self.maximum is None:
            wanted = f"at least {self.minimum}"
        elif self.minimum == self.maximum:
            wanted = str(self.minimum)
        else:
            wanted = f"{self.minimum} to {self.maximum}"
        return f"wrong number of args for {name}: want {wanted} got {count}"

    def type_error(self, name: str, arguments: Sequence[object]) -> str | None:
        """Return an error for the first enforceable annotation mismatch."""

        for index, argument in enumerate(arguments):
            annotation = (
                self.positional_annotations[index]
                if index < len(self.positional_annotations)
                else self.variadic_annotation
            )
            if not _matches_annotation(argument, annotation):
                return (
                    f"argument {index + 1} to {name}: expected "
                    f"{_annotation_name(annotation)}, got {type(argument).__name__}"
                )
        return None


class PreparedFunctionRegistry(Mapping[str, Callable[..., object]]):
    """Immutable callables paired with their construction-time signatures."""

    __slots__ = ("_functions", "call_specs", "includes_builtins")
    _functions: Mapping[str, Callable[..., object]]
    call_specs: Mapping[str, CallSpec | None]
    includes_builtins: bool

    def __init__(
        self,
        functions: Mapping[str, Callable[..., object]],
        call_specs: Mapping[str, CallSpec | None] | None = None,
        *,
        includes_builtins: bool = False,
    ) -> None:
        values = dict(functions)
        specs = (
            {
                name: prepare_template_function(name, function)
                for name, function in values.items()
            }
            if call_specs is None
            else dict(call_specs)
        )
        if set(specs) != set(values):
            raise ValueError("prepared function names do not match callable names")
        self._functions = MappingProxyType(values)
        self.call_specs = MappingProxyType(specs)
        self.includes_builtins = includes_builtins

    def __getitem__(self, name: str) -> Callable[..., object]:
        return self._functions[name]

    def __iter__(self) -> Iterator[str]:
        return iter(self._functions)

    def __len__(self) -> int:
        return len(self._functions)


def prepare_template_function(
    name: str,
    function: Callable[..., object],
) -> CallSpec | None:
    """Inspect once and reject signatures a positional template cannot call."""

    spec = call_spec(function)
    if spec is None or not spec.required_keyword_only:
        return spec
    parameter = spec.required_keyword_only[0]
    raise TypeError(
        f"template function {name!r} has required keyword-only parameter {parameter!r}"
    )


def invoke_template_function(
    name: str,
    function: Callable[..., object],
    arguments: Sequence[object],
) -> object:
    """Validate positional arity and invoke a registered template function."""

    return invoke_prepared_template_function(
        name,
        function,
        arguments,
        call_spec(function),
    )


def invoke_prepared_template_function(
    name: str,
    function: Callable[..., object],
    arguments: Sequence[object],
    spec: CallSpec | None,
) -> object:
    """Invoke using signature metadata prepared when the registry was built."""

    if spec is not None and spec.requires_validation:
        error = spec.arity_error(name, len(arguments))
        if error is not None:
            raise TemplateCallArityError(error)
        error = spec.type_error(name, arguments)
        if error is not None:
            raise TemplateCallTypeError(error)
    return function(*arguments)


def call_spec(function: Callable[..., object]) -> CallSpec | None:
    """Return an inspectable call specification, caching common callables."""

    try:
        hash(function)
    except TypeError:
        return _inspect_call_spec(function)
    return _cached_call_spec(function)


@lru_cache(maxsize=1024)
def _cached_call_spec(function: Callable[..., object]) -> CallSpec | None:
    return _inspect_call_spec(function)


def _inspect_call_spec(function: Callable[..., object]) -> CallSpec | None:
    try:
        callable_signature = signature(function)
    except (TypeError, ValueError):
        return None
    return _spec_from_signature(callable_signature)


def _spec_from_signature(callable_signature: Signature) -> CallSpec:
    positional = [
        parameter
        for parameter in callable_signature.parameters.values()
        if parameter.kind
        in {Parameter.POSITIONAL_ONLY, Parameter.POSITIONAL_OR_KEYWORD}
    ]
    minimum = sum(parameter.default is Parameter.empty for parameter in positional)
    variadic = any(
        parameter.kind is Parameter.VAR_POSITIONAL
        for parameter in callable_signature.parameters.values()
    )
    required_keyword_only = tuple(
        parameter.name
        for parameter in callable_signature.parameters.values()
        if parameter.kind is Parameter.KEYWORD_ONLY
        and parameter.default is Parameter.empty
    )
    variadic_parameter = next(
        (
            parameter
            for parameter in callable_signature.parameters.values()
            if parameter.kind is Parameter.VAR_POSITIONAL
        ),
        None,
    )
    positional_annotations = tuple(
        _normalized_annotation(parameter.annotation) for parameter in positional
    )
    variadic_annotation = (
        Parameter.empty
        if variadic_parameter is None
        else _normalized_annotation(variadic_parameter.annotation)
    )
    maximum = None if variadic else len(positional)
    return CallSpec(
        minimum,
        maximum,
        required_keyword_only,
        positional_annotations,
        variadic_annotation,
        (
            minimum != 0
            or maximum is not None
            or any(_annotation_is_enforceable(item) for item in positional_annotations)
            or _annotation_is_enforceable(variadic_annotation)
        ),
    )


def _normalized_annotation(annotation: object) -> object:
    if isinstance(annotation, str):
        return {
            "bool": bool,
            "bytes": bytes,
            "complex": complex,
            "float": float,
            "int": int,
            "object": object,
            "str": str,
        }.get(annotation, Parameter.empty)
    return annotation


def _matches_annotation(value: object, annotation: object) -> bool:
    if annotation is Parameter.empty or annotation is Any or annotation is object:
        return True
    if annotation is None:
        annotation = type(None)
    origin = get_origin(annotation)
    if origin in {UnionType, Union}:
        return any(_matches_annotation(value, item) for item in get_args(annotation))
    if origin is Literal:
        return value in get_args(annotation)
    checked = origin if isinstance(origin, type) else annotation
    if checked is int:
        return isinstance(value, int) and not isinstance(value, bool)
    if checked is float:
        return isinstance(value, float)
    if checked is complex:
        return isinstance(value, complex)
    if isinstance(checked, type):
        return isinstance(value, checked)
    return True


def _annotation_is_enforceable(annotation: object) -> bool:
    if annotation is Parameter.empty or annotation is Any or annotation is object:
        return False
    if annotation is None:
        return True
    origin = get_origin(annotation)
    return (
        origin in {UnionType, Union, Literal}
        or isinstance(origin, type)
        or isinstance(annotation, type)
    )


def _annotation_name(annotation: object) -> str:
    origin = get_origin(annotation)
    if origin in {UnionType, Union}:
        return " | ".join(_annotation_name(item) for item in get_args(annotation))
    if isinstance(origin, type):
        return origin.__name__
    if isinstance(annotation, type):
        return annotation.__name__
    return str(annotation)
