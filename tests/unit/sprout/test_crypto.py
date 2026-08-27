from __future__ import annotations

import base64
from collections.abc import Callable, Mapping

import pytest

from gotpl import FunctionResult, Template
from gotpl.funcs.sprout import Handler, registry


def _functions() -> Mapping[str, Callable[..., object]]:
    return Handler(registry("crypto")).build()


def test_crypto_registry_matches_deterministic_sprout_behavior() -> None:
    functions = _functions()

    assert (
        functions["derivePassword"](1, "short", "password", "user", "example.com")
        == "Zed5"
    )
    missing = functions["derivePassword"](1, "missing", "p", "u", "s")
    assert isinstance(missing, FunctionResult)
    assert str(missing.error) == "cannot find password template missing"
    unknown = functions["genPrivateKey"]("invalid")
    assert isinstance(unknown, FunctionResult)
    assert str(unknown.error) == "unknown type invalid"


def test_crypto_registry_aes_round_trip_and_empty_values() -> None:
    pytest.importorskip("cryptography")
    functions = _functions()

    encrypted = functions["encryptAES"]("secret", "plaintext")
    assert isinstance(encrypted, FunctionResult)
    assert encrypted.error is None
    assert isinstance(encrypted.value, str)
    assert base64.b64decode(encrypted.value)
    assert functions["decryptAES"]("secret", encrypted.value) == FunctionResult.success(
        "plaintext"
    )
    assert functions["encryptAES"]("secret", "") == FunctionResult.success("")
    assert functions["decryptAES"]("secret", "") == FunctionResult.success("")


def test_crypto_registry_is_template_ready() -> None:
    functions = _functions()
    source = '{{derivePassword 1 "short" "password" "user" "example.com"}}'

    assert Template(source, functions=functions).render() == "Zed5"


def test_crypto_registry_contains_the_complete_pinned_surface() -> None:
    functions = _functions()

    assert set(functions) == {
        "bcrypt",
        "buildCustomCert",
        "decryptAES",
        "derivePassword",
        "encryptAES",
        "genCA",
        "genCAWithKey",
        "genPrivateKey",
        "genSelfSignedCert",
        "genSelfSignedCertWithKey",
        "genSignedCert",
        "genSignedCertWithKey",
        "htpasswd",
    }
