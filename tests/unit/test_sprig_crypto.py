import base64
import builtins
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.x509.oid import NameOID

import gotpl
import gotpl.funcs.sprig as sprig
from gotpl.funcs.sprig import crypto


@pytest.mark.parametrize(
    ("counter", "password_type", "expected"),
    [
        (1, "long", "ZedaFaxcZaso9*"),
        (2, "long", "Fovi2@JifpTupx"),
        (1, "maximum", "pf4zS1LjCg&LjhsZ7T2~"),
        (1, "medium", "ZedJuz8$"),
        (1, "basic", "pIS54PLs"),
        (1, "short", "Zed5"),
        (1, "pin", "6685"),
    ],
)
def test_derive_password_matches_sprig_vectors(
    counter: int, password_type: str, expected: str
) -> None:
    assert (
        crypto.derive_password(
            counter, password_type, "password", "user", "example.com"
        )
        == expected
    )


def test_derive_password_reports_unknown_template() -> None:
    assert crypto.derive_password(1, "missing", "p", "u", "s") == (
        "cannot find password template missing"
    )


def test_aes_matches_sprig_key_padding_and_supports_injected_entropy() -> None:
    encrypted = crypto.encrypt_aes(
        "secretkey", "plaintext", entropy=lambda count: bytes(range(count))
    )

    assert encrypted == "AAECAwQFBgcICQoLDA0OD4aChIkqfhLglmmHSXlA6r0="
    assert crypto.decrypt_aes("secretkey", encrypted) == "plaintext"
    assert crypto.encrypt_aes("secret", "") == ""
    assert crypto.decrypt_aes("secret", "") == ""


def test_aes_rejects_malformed_ciphertext() -> None:
    with pytest.raises(ValueError, match="wrong byte count"):
        crypto.encrypt_aes("secret", "text", entropy=lambda _count: b"short")
    with pytest.raises(ValueError, match="encoding"):
        crypto.decrypt_aes("secret", "%%%")
    with pytest.raises(ValueError, match="ciphertext"):
        crypto.decrypt_aes("secret", base64.b64encode(b"short").decode())
    with pytest.raises(ValueError, match="padding"):
        crypto.decrypt_aes("secret", base64.b64encode(bytes(32)).decode())


def test_aes_decoder_accepts_go_base64_newlines_and_loose_padding() -> None:
    encrypted = crypto.encrypt_aes(
        "secret", "value", entropy=lambda count: bytes(range(count))
    )
    assert crypto.decrypt_aes("secret", f"{encrypted[:8]}\r\n{encrypted[8:]}") == (
        "value"
    )

    # Go's Sprig helper removes the number of bytes named by the final byte; it
    # does not validate that every PKCS#7 padding byte has the same value.
    raw = bytearray(base64.b64decode(encrypted))
    key = b"secret".ljust(32, b"\0")
    decryptor = Cipher(algorithms.AES(key), modes.CBC(bytes(raw[:16]))).decryptor()
    plaintext = bytearray(decryptor.update(bytes(raw[16:])) + decryptor.finalize())
    plaintext[-2] ^= 1
    encryptor = Cipher(algorithms.AES(key), modes.CBC(bytes(raw[:16]))).encryptor()
    malformed = (
        bytes(raw[:16]) + encryptor.update(bytes(plaintext)) + encryptor.finalize()
    )
    assert crypto.decrypt_aes("secret", base64.b64encode(malformed).decode()) == "value"


def test_bcrypt_and_htpasswd_use_the_optional_backend() -> None:
    hashed = crypto.bcrypt_hash("abc")

    assert crypto.bcrypt_verify("abc", hashed)
    assert crypto.htpasswd("user", "abc").startswith("user:$2")
    assert crypto.htpasswd("bad:name", "abc") == "invalid username: bad:name"
    assert crypto.bcrypt_hash("x" * 73) == (
        "failed to encrypt string with bcrypt: bcrypt: password length exceeds 72 bytes"
    )


def test_crypto_functions_are_available_to_templates() -> None:
    functions = sprig.generic_func_map(entropy=lambda count: bytes(range(count)))

    assert (
        gotpl.render(
            '{{derivePassword 1 "short" "password" "user" "example.com"}}',
            functions=functions,
        )
        == "Zed5"
    )
    assert (
        gotpl.render(
            '{{"plaintext" | encryptAES "secretkey" | decryptAES "secretkey"}}',
            functions=functions,
        )
        == "plaintext"
    )
    assert functions["genPrivateKey"]("bad") == "Unknown type bad"


def test_registered_crypto_error_functions_preserve_go_result_contract() -> None:
    functions = sprig.generic_func_map(entropy=lambda count: bytes(count))

    encrypted = functions["encryptAES"]("key", "value")
    invalid_aes = functions["decryptAES"]("key", "%%")
    invalid_cert = functions["buildCustomCert"]("%%", "%%")

    assert isinstance(encrypted, gotpl.FunctionResult)
    assert isinstance(encrypted.value, str)
    assert encrypted.error is None
    assert isinstance(invalid_aes, gotpl.FunctionResult)
    assert isinstance(invalid_aes.error, ValueError)
    assert isinstance(invalid_cert, gotpl.FunctionResult)
    assert isinstance(invalid_cert.error, ValueError)

    key = crypto.generate_private_key("ecdsa")
    invalid_leaf = functions["genSelfSignedCertWithKey"](
        "leaf", ["invalid"], [], 1, key
    )
    assert isinstance(invalid_leaf, gotpl.FunctionResult)
    assert isinstance(invalid_leaf.error, ValueError)
    failed_encryption = sprig.generic_func_map(entropy=lambda _count: b"short")[
        "encryptAES"
    ]("key", "value")
    assert isinstance(failed_encryption, gotpl.FunctionResult)
    assert isinstance(failed_encryption.error, ValueError)
    with pytest.raises(ValueError, match="ciphertext length"):
        functions["decryptAES"]("key", base64.b64encode(b"short").decode())


def test_derive_password_registry_rejects_values_outside_go_uint32() -> None:
    derive = sprig.generic_func_map()["derivePassword"]

    with pytest.raises(OverflowError, match="uint32"):
        derive(-1, "short", "password", "user", "example.com")
    with pytest.raises(OverflowError, match="uint32"):
        derive(1 << 32, "short", "password", "user", "example.com")


def test_certificate_objects_and_with_key_pipeline_work_in_templates() -> None:
    functions = sprig.generic_func_map(clock=lambda: datetime(2025, 1, 2, tzinfo=UTC))

    assert (
        gotpl.render(
            '{{- $ca := genPrivateKey "ecdsa" | genCAWithKey "test-ca" 1 -}}'
            '{{contains "BEGIN CERTIFICATE" $ca.Cert}}/'
            '{{contains "EC PRIVATE KEY" $ca.Key}}',
            functions=functions,
        )
        == "true/true"
    )


def test_all_sprig_crypto_names_are_registered() -> None:
    functions = sprig.generic_func_map()

    assert {
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
    } <= functions.keys()


def test_private_key_algorithms_use_go_compatible_pem_labels() -> None:
    assert "RSA PRIVATE KEY" in crypto.generate_private_key("rsa")
    assert "DSA PRIVATE KEY" in crypto.generate_private_key("dsa")
    assert "EC PRIVATE KEY" in crypto.generate_private_key("ecdsa")
    assert "PRIVATE KEY" in crypto.generate_private_key("ed25519")


def test_certificate_authority_and_custom_certificate_round_trip() -> None:
    key = crypto.generate_private_key("ecdsa")
    fixed = datetime(2025, 1, 2, 3, 4, 5, tzinfo=UTC)
    ca = crypto.generate_ca_with_key("test-ca", 30, key, clock=lambda: fixed)
    certificate = x509.load_pem_x509_certificate(ca.Cert.encode())

    assert certificate.subject.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value == (
        "test-ca"
    )
    assert certificate.extensions.get_extension_for_class(
        x509.BasicConstraints
    ).value.ca
    assert certificate.not_valid_before_utc == fixed
    rebuilt = crypto.build_custom_certificate(
        base64.b64encode(ca.Cert.encode()).decode(),
        base64.b64encode(ca.Key.encode()).decode(),
    )
    assert rebuilt == ca
    registered = sprig.generic_func_map()["buildCustomCert"](
        base64.b64encode(ca.Cert.encode()).decode(),
        base64.b64encode(ca.Key.encode()).decode(),
    )
    assert registered == gotpl.FunctionResult.success(ca)


def test_self_signed_and_ca_signed_certificates_preserve_names() -> None:
    fixed = datetime(2025, 1, 2, tzinfo=UTC)
    leaf_key = crypto.generate_private_key("ecdsa")
    self_signed = crypto.generate_self_signed_certificate_with_key(
        "self.test",
        ["192.0.2.1"],
        ["alt.test"],
        2,
        leaf_key,
        clock=lambda: fixed,
    )
    self_cert = x509.load_pem_x509_certificate(self_signed.Cert.encode())
    names = self_cert.extensions.get_extension_for_class(
        x509.SubjectAlternativeName
    ).value
    assert names.get_values_for_type(x509.IPAddress)[0].compressed == "192.0.2.1"
    assert names.get_values_for_type(x509.DNSName) == ["alt.test"]

    ca_key = crypto.generate_private_key("ecdsa")
    ca = crypto.generate_ca_with_key("issuer", 10, ca_key, clock=lambda: fixed)
    signed = crypto.generate_signed_certificate_with_key(
        "leaf.test", [], [], 2, ca, leaf_key, clock=lambda: fixed
    )
    signed_cert = x509.load_pem_x509_certificate(signed.Cert.encode())
    ca_cert = x509.load_pem_x509_certificate(ca.Cert.encode())
    assert signed_cert.issuer == ca_cert.subject


def test_certificate_inputs_are_validated() -> None:
    key = crypto.generate_private_key("ecdsa")
    with pytest.raises(ValueError, match="error parsing ip"):
        crypto.generate_self_signed_certificate_with_key(
            "bad", ["not-an-ip"], [], 1, key
        )
    with pytest.raises(TypeError, match="not a string"):
        crypto.generate_self_signed_certificate_with_key("bad", [1], [], 1, key)
    with pytest.raises(TypeError, match="not a string"):
        crypto.generate_self_signed_certificate_with_key("bad", [], [1], 1, key)
    with pytest.raises(ValueError, match="base64 certificate"):
        crypto.build_custom_certificate("%%%", base64.b64encode(key.encode()).decode())
    ca = crypto.generate_ca_with_key("ca", 1, key)
    with pytest.raises(ValueError, match="base64 private key"):
        crypto.build_custom_certificate(
            base64.b64encode(ca.Cert.encode()).decode(), "%%%"
        )


def test_generated_private_key_can_be_loaded() -> None:
    value = crypto.generate_private_key("ecdsa")
    assert serialization.load_pem_private_key(value.encode(), password=None)


def test_default_rsa_certificate_entry_points() -> None:
    ca = crypto.generate_ca("ca", 1)
    self_signed = crypto.generate_self_signed_certificate("self", [], [], 1)
    signed = crypto.generate_signed_certificate("leaf", [], [], 1, ca)

    assert x509.load_pem_x509_certificate(ca.Cert.encode())
    assert x509.load_pem_x509_certificate(self_signed.Cert.encode())
    assert x509.load_pem_x509_certificate(signed.Cert.encode()).issuer == (
        x509.load_pem_x509_certificate(ca.Cert.encode()).subject
    )


def test_registered_certificate_entry_points_return_go_results() -> None:
    functions = sprig.generic_func_map(clock=lambda: datetime(2025, 1, 2, tzinfo=UTC))
    ca_result = functions["genCA"]("ca", 1)
    self_result = functions["genSelfSignedCert"]("self", [], [], 1)

    assert isinstance(ca_result, gotpl.FunctionResult)
    assert isinstance(ca_result.value, crypto.Certificate)
    assert isinstance(self_result, gotpl.FunctionResult)
    assert isinstance(self_result.value, crypto.Certificate)

    ca = ca_result.value
    assert isinstance(ca, crypto.Certificate)
    signed_result = functions["genSignedCert"]("leaf", [], [], 1, ca)
    assert isinstance(signed_result, gotpl.FunctionResult)
    assert isinstance(signed_result.value, crypto.Certificate)

    key = crypto.generate_private_key("ecdsa")
    self_with_key = functions["genSelfSignedCertWithKey"]("self", [], [], 1, key)
    signed_with_key = functions["genSignedCertWithKey"]("leaf", [], [], 1, ca, key)
    assert isinstance(self_with_key, gotpl.FunctionResult)
    assert isinstance(self_with_key.value, crypto.Certificate)
    assert isinstance(signed_with_key, gotpl.FunctionResult)
    assert isinstance(signed_with_key.value, crypto.Certificate)


def test_ed25519_certificate_uses_algorithm_free_signing() -> None:
    key = crypto.generate_private_key("ed25519")
    ca = crypto.generate_ca_with_key("ed-ca", 1, key)

    assert (
        x509.load_pem_x509_certificate(ca.Cert.encode()).signature_hash_algorithm
        is None
    )


@pytest.mark.parametrize(
    ("blocked_root", "call"),
    [
        ("bcrypt", lambda: crypto.bcrypt_hash("x")),
        (
            "cryptography",
            lambda: crypto.encrypt_aes("key", "value"),
        ),
        (
            "cryptography",
            lambda: crypto.generate_private_key("ecdsa"),
        ),
    ],
)
def test_missing_optional_backends_have_actionable_errors(
    monkeypatch: pytest.MonkeyPatch,
    blocked_root: str,
    call: Callable[[], object],
) -> None:
    original_import = builtins.__import__

    def blocked_import(
        name: str,
        globals: Mapping[str, object] | None = None,
        locals: Mapping[str, object] | None = None,
        fromlist: Sequence[str] = (),
        level: int = 0,
    ) -> object:
        if name == blocked_root or name.startswith(f"{blocked_root}."):
            raise ImportError(name)
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", blocked_import)
    with pytest.raises(RuntimeError, match=r"gotpl\[crypto\]"):
        call()
