"""Central Python value adaptation for Go template semantics."""

from collections.abc import Callable, Collection, Iterable, Iterator, Mapping
from dataclasses import dataclass
from inspect import getattr_static, ismethod
from types import MemberDescriptorType
from typing import Generic, Literal, TypeAlias, TypeGuard, TypeVar, cast

from gotpl._compat.gofmt.go import GoPointer
from gotpl._compat.gofmt.types import FormatMode, FormatValueKind
from gotpl.errors import SandboxViolationError, TemplateExecutionError

from .awaitables import reject_awaitable
from .policy import SandboxPolicy
from .results import unwrap_function_result

MissingKeyMode: TypeAlias = Literal["default", "zero", "error"]
_Key = TypeVar("_Key")
_Value = TypeVar("_Value")


@dataclass(frozen=True, slots=True)
class TypedMap(Mapping[_Key, _Value], Generic[_Key, _Value]):
    """A Python mapping carrying its Go-compatible element zero value."""

    data: Mapping[_Key, _Value]
    zero: _Value
    key_type: str | None = None
    value_type: str | None = None

    def __getitem__(self, key: _Key) -> _Value:
        return self.data[key]

    def __iter__(self) -> Iterator[_Key]:
        return iter(self.data)

    def __len__(self) -> int:
        return len(self.data)

    def __go_map_type__(self) -> tuple[str, str] | None:
        """Expose explicit Go map type names to the formatter package."""
        if self.key_type and self.value_type:
            return self.key_type, self.value_type
        return None


@dataclass(frozen=True, slots=True)
class GoSeq(Generic[_Value]):
    """Adapt a Python iterable to Go's single-value ``iter.Seq`` semantics."""

    values: Iterable[_Value]


@dataclass(frozen=True, slots=True)
class GoSeq2(Generic[_Key, _Value]):
    """Adapt key-value pairs to Go's ``iter.Seq2`` range semantics."""

    values: Iterable[tuple[_Key, _Value]]


class _InvalidValue:
    __slots__ = ()

    def __repr__(self) -> str:
        return "INVALID"

    def __go_format_value__(
        self,
        kind: FormatValueKind,
        mode: FormatMode,
        *,
        nested: bool,
    ) -> str:
        del nested
        if kind == "type":
            return "invalid" if mode == "python" else "<nil>"
        return "<no value>"


INVALID = _InvalidValue()


class _UntypedNil:
    __slots__ = ()

    def __repr__(self) -> str:
        return "UNTYPED_NIL"

    def __go_format_value__(
        self,
        kind: FormatValueKind,
        mode: FormatMode,
        *,
        nested: bool,
    ) -> str:
        del nested
        if kind == "type":
            return "nil" if mode == "python" else "<nil>"
        return "<nil>"


UNTYPED_NIL = _UntypedNil()


def number_value(value: str | bool | None, *, is_complex: bool) -> object:
    """Decode one compiled Go numeric literal."""

    if not isinstance(value, str):
        return INVALID
    text = value.replace("_", "")
    if text.endswith("i"):
        return complex(text[:-1] + "j")
    if is_complex:
        return complex(text.replace("i", "j"))
    if any(marker in text for marker in ".eEpP"):
        return float.fromhex(text) if "0x" in text.lower() else float(text)
    sign = -1 if text.startswith("-") else 1
    unsigned = text.lstrip("+-")
    if unsigned.lower().startswith(("0b", "0o", "0x")):
        number = int(unsigned, 0)
    elif len(unsigned) > 1 and unsigned.startswith("0"):
        number = int(unsigned, 8)
    else:
        number = int(unsigned, 10)
    return sign * number


@dataclass(frozen=True, slots=True)
class ValueAdapter:
    """Resolve fields and truth values through one auditable boundary."""

    missing_key: MissingKeyMode = "default"
    sandbox: SandboxPolicy | None = None

    def lookup(self, value: object, field: str) -> object:
        """Resolve one exported Go-style field from a Python value."""

        if value is INVALID:
            return self._missing(field)
        if self.sandbox is not None and not isinstance(value, Mapping):
            return self._sandboxed_lookup(value, field)
        if type(cast(object, value)) is dict:
            mapping = cast(dict[object, object], value)
            try:
                return mapping[field]
            except KeyError:
                return self._missing(field, mapping)
        template_lookup = _get_template_lookup(cast(object, value))
        if callable(template_lookup):
            try:
                return template_lookup(field)
            except (AttributeError, KeyError):
                return self._missing(field)
        if isinstance(value, Mapping):
            mapping = cast(Mapping[object, object], value)
            if field in mapping:
                return mapping[field]
            return self._missing(field, mapping)
        if field.startswith("_"):
            return self._missing(field)
        try:
            return getattr(value, field)
        except AttributeError:
            return self._missing(field)
        except Exception as error:
            raise TemplateExecutionError(
                f"attribute {field!r} failed: {error}"
            ) from error

    def _sandboxed_lookup(self, value: object, field: str) -> object:
        policy = self.sandbox
        if policy is None:
            raise AssertionError("sandboxed lookup requires a policy")
        try:
            custom_lookup = getattr_static(value, "__gotemplate_lookup__")
        except AttributeError:
            custom_lookup = None
        if custom_lookup is not None:
            if not policy.allow_custom_lookup:
                raise SandboxViolationError("custom template lookup is not allowed")
            lookup_name = "__gotemplate_lookup__"
            lookup = getattr(value, lookup_name)
            try:
                return lookup(field)
            except (AttributeError, KeyError):
                return self._missing(field)

        if field.startswith("_"):
            raise SandboxViolationError(f"attribute {field!r} is not allowed")
        try:
            static_value = getattr_static(value, field)
        except AttributeError:
            if field not in policy.allow_attributes:
                raise SandboxViolationError(
                    f"attribute {field!r} is not allowed"
                ) from None
            static_value = None

        is_property = isinstance(static_value, property) or (
            hasattr(static_value, "__get__")
            and not isinstance(static_value, MemberDescriptorType)
            and not callable(static_value)
        )
        if is_property and field not in policy.allow_properties:
            raise SandboxViolationError(f"property {field!r} is not allowed")
        if callable(static_value) and field not in policy.allow_methods:
            raise SandboxViolationError(f"method {field!r} is not allowed")
        if (
            not is_property
            and not callable(static_value)
            and field not in policy.allow_attributes
        ):
            raise SandboxViolationError(f"attribute {field!r} is not allowed")
        try:
            result = getattr(value, field)
        except AttributeError:
            return self._missing(field)
        except Exception as error:
            raise TemplateExecutionError(
                f"attribute {field!r} failed: {error}"
            ) from error
        if callable(result) and field not in policy.allow_methods:
            raise SandboxViolationError(f"method {field!r} is not allowed")
        return result

    def lookup_chain(self, value: object, fields: tuple[str, ...]) -> object:
        """Resolve an already split field chain."""

        for index, field in enumerate(fields):
            value = self.lookup(value, field)
            if value is INVALID:
                break
            if index < len(fields) - 1 and is_bound_method(value):
                try:
                    value = unwrap_function_result(reject_awaitable(value()))
                except Exception as error:
                    raise TemplateExecutionError(
                        f"method {field!r} failed: {error}"
                    ) from error
        return value

    def _missing(
        self, field: str, mapping: Mapping[object, object] | None = None
    ) -> object:
        if self.missing_key == "error":
            raise TemplateExecutionError(f"missing key or attribute {field!r}")
        if self.missing_key == "zero":
            if isinstance(mapping, TypedMap):
                return mapping.zero
            return None
        return INVALID

    def is_true(self, value: object) -> bool:
        """Return Go template truthiness for an adapted Python value."""

        if value is INVALID or value is UNTYPED_NIL or value is None or value is False:
            return False
        if isinstance(value, GoPointer):
            return cast(GoPointer[object], value).value is not None
        if isinstance(value, (int, float, complex)):
            return value != 0
        if isinstance(value, (str, bytes)):
            return len(value) != 0
        if isinstance(value, (list, tuple, dict, set, frozenset)):
            return len(cast(Collection[object], value)) != 0
        return True


def is_bound_method(value: object) -> TypeGuard[Callable[..., object]]:
    """Return whether a Python callable is bound to an instance or class."""

    return ismethod(value) or (
        callable(value) and getattr(value, "__self__", None) is not None
    )


def _get_template_lookup(value: object) -> object:
    return getattr(value, "__gotemplate_lookup__", None)
