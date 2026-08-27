"""Sprout crypto adapters over gotpl's public Sprig compatibility map."""

from __future__ import annotations

from collections.abc import Callable

from gotpl.funcs.sprig import generic_func_map
from gotpl.runtime import FunctionResult

from .errors import MissingOptionalDependencyError
from .registry import TemplateFunction

_SPRIG = generic_func_map()


def _call(name: str, *args: object) -> object:
    try:
        return _SPRIG[name](*args)
    except RuntimeError as error:
        if "optional 'crypto' extra" not in str(error):
            raise
        raise MissingOptionalDependencyError(
            'Cryptographic functions require `pip install "gotpl[crypto]"`'
        ) from error


def _error_from_string(value: object, prefix: str) -> object:
    if isinstance(value, str) and value.startswith(prefix):
        return FunctionResult.failure(ValueError(value), value="")
    return value


def _bcrypt(value: str) -> object:
    return _error_from_string(_call("bcrypt", value), "failed to encrypt")


def _htpasswd(username: str, password: str) -> object:
    return _error_from_string(_call("htpasswd", username, password), "invalid username")


def _derive_password(
    counter: int, password_type: str, password: str, user: str, site: str
) -> object:
    value = _call("derivePassword", counter, password_type, password, user, site)
    return _error_from_string(value, "cannot find password template")


def _generate_private_key(key_type: str) -> object:
    value = _call("genPrivateKey", key_type)
    if isinstance(value, str) and value.startswith("Unknown type "):
        return FunctionResult.failure(
            ValueError(f"unknown type {key_type}"),
            value="",
        )
    return value


def _forward(name: str) -> TemplateFunction:
    def wrapped(*args: object) -> object:
        return _call(name, *args)

    return wrapped


def functions() -> dict[str, Callable[..., object]]:
    """Return the complete Sprout v1.1.1 crypto function surface."""

    return {
        "bcrypt": _bcrypt,
        "htpasswd": _htpasswd,
        "derivePassword": _derive_password,
        "genPrivateKey": _generate_private_key,
        "buildCustomCert": _forward("buildCustomCert"),
        "genCA": _forward("genCA"),
        "genCAWithKey": _forward("genCAWithKey"),
        "genSelfSignedCert": _forward("genSelfSignedCert"),
        "genSelfSignedCertWithKey": _forward("genSelfSignedCertWithKey"),
        "genSignedCert": _forward("genSignedCert"),
        "genSignedCertWithKey": _forward("genSignedCertWithKey"),
        "encryptAES": _forward("encryptAES"),
        "decryptAES": _forward("decryptAES"),
    }
