"""Sprig-compatible cryptographic helpers with optional backends."""

from __future__ import annotations

import base64
import hashlib
import hmac
import ipaddress
import os
import struct
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, cast

from gotpl.runtime import UNTYPED_NIL, FunctionResult

Entropy = Callable[[int], bytes]
Clock = Callable[[], datetime]

_SEED = b"com.lyndir.masterpassword"
_TEMPLATES = {
    "maximum": (b"anoxxxxxxxxxxxxxxxxx", b"axxxxxxxxxxxxxxxxxno"),
    "long": tuple(
        value.encode()
        for value in (
            "CvcvnoCvcvCvcv",
            "CvcvCvcvnoCvcv",
            "CvcvCvcvCvcvno",
            "CvccnoCvcvCvcv",
            "CvccCvcvnoCvcv",
            "CvccCvcvCvcvno",
            "CvcvnoCvccCvcv",
            "CvcvCvccnoCvcv",
            "CvcvCvccCvcvno",
            "CvcvnoCvcvCvcc",
            "CvcvCvcvnoCvcc",
            "CvcvCvcvCvccno",
            "CvccnoCvccCvcv",
            "CvccCvccnoCvcv",
            "CvccCvccCvcvno",
            "CvcvnoCvccCvcc",
            "CvcvCvccnoCvcc",
            "CvcvCvccCvccno",
            "CvccnoCvcvCvcc",
            "CvccCvcvnoCvcc",
            "CvccCvcvCvccno",
        )
    ),
    "medium": (b"CvcnoCvc", b"CvcCvcno"),
    "short": (b"Cvcn",),
    "basic": (b"aaanaaan", b"aannaaan", b"aaannaaa"),
    "pin": (b"nnnn",),
}
_CHARS = {
    ord("V"): "AEIOU",
    ord("C"): "BCDFGHJKLMNPQRSTVWXYZ",
    ord("v"): "aeiou",
    ord("c"): "bcdfghjklmnpqrstvwxyz",
    ord("A"): "AEIOUBCDFGHJKLMNPQRSTVWXYZ",
    ord("a"): "AEIOUaeiouBCDFGHJKLMNPQRSTVWXYZbcdfghjklmnpqrstvwxyz",
    ord("n"): "0123456789",
    ord("o"): "@&%?,=[]_:-+*$#!'^~;()/.",
    ord(
        "x"
    ): "AEIOUaeiouBCDFGHJKLMNPQRSTVWXYZbcdfghjklmnpqrstvwxyz0123456789!@#$%^&*()",
}


@dataclass(frozen=True, slots=True)
class Certificate:
    """A certificate and key with Go-compatible exported field names."""

    Cert: str
    Key: str


def derive_password(
    counter: int, password_type: str, password: str, user: str, site: str
) -> str:
    templates = _TEMPLATES.get(password_type)
    if templates is None:
        return f"cannot find password template {password_type}"
    user_bytes = user.encode()
    salt = _SEED + struct.pack(">I", len(user_bytes)) + user_bytes
    key = hashlib.scrypt(
        password.encode(), salt=salt, n=32768, r=8, p=2, dklen=64, maxmem=128 << 20
    )
    site_bytes = site.encode()
    message = (
        _SEED
        + struct.pack(">I", len(site_bytes))
        + site_bytes
        + struct.pack(">I", counter & 0xFFFFFFFF)
    )
    seed = hmac.new(key, message, hashlib.sha256).digest()
    template = templates[seed[0] % len(templates)]
    return "".join(
        _CHARS[element][seed[index + 1] % len(_CHARS[element])]
        for index, element in enumerate(template)
    )


def derive_password_go(
    counter: int, password_type: str, password: str, user: str, site: str
) -> str:
    """Validate the uint32 template argument before using the friendly helper."""

    if not 0 <= counter <= 0xFFFFFFFF:
        raise OverflowError(f"{counter} overflows uint32")
    return derive_password(counter, password_type, password, user, site)


def encrypt_aes(
    password: str, plaintext: str, *, entropy: Entropy | None = None
) -> str:
    if not plaintext:
        return ""
    cipher, algorithms, modes = _cipher_backend()
    key = password.encode()[:32].ljust(32, b"\0")
    content = plaintext.encode()
    padding = 16 - len(content) % 16
    content += bytes([padding]) * padding
    iv = (entropy or os.urandom)(16)
    if len(iv) != 16:
        raise ValueError("entropy source returned the wrong byte count")
    encryptor = cipher(algorithms.AES(key), modes.CBC(iv)).encryptor()
    encrypted = encryptor.update(content) + encryptor.finalize()
    return base64.b64encode(iv + encrypted).decode()


def encrypt_aes_result(
    password: str, plaintext: str, *, entropy: Entropy | None = None
) -> FunctionResult:
    try:
        return FunctionResult.success(encrypt_aes(password, plaintext, entropy=entropy))
    except ValueError as error:
        return FunctionResult.failure(error, "")


def decrypt_aes(password: str, crypt64: str) -> str:
    if not crypt64:
        return ""
    try:
        encrypted = base64.b64decode(
            crypt64.replace("\r", "").replace("\n", ""), validate=True
        )
    except ValueError as error:
        raise ValueError("invalid AES ciphertext encoding") from error
    if len(encrypted) < 32 or len(encrypted) % 16:
        raise ValueError("invalid AES ciphertext length")
    cipher, algorithms, modes = _cipher_backend()
    key = password.encode()[:32].ljust(32, b"\0")
    decryptor = cipher(algorithms.AES(key), modes.CBC(encrypted[:16])).decryptor()
    plaintext = decryptor.update(encrypted[16:]) + decryptor.finalize()
    padding = plaintext[-1]
    if padding > len(plaintext):
        raise ValueError("invalid AES padding")
    end = len(plaintext) - padding
    return plaintext[:end].decode()


def decrypt_aes_result(password: str, crypt64: str) -> FunctionResult:
    try:
        return FunctionResult.success(decrypt_aes(password, crypt64))
    except ValueError as error:
        if str(error) != "invalid AES ciphertext encoding":
            raise
        return FunctionResult.failure(error, "")


def bcrypt_hash(value: str) -> str:
    backend = _bcrypt_backend()
    try:
        return cast(
            bytes, backend.hashpw(value.encode(), backend.gensalt(rounds=10))
        ).decode()
    except ValueError:
        if len(value.encode()) > 72:
            return (
                "failed to encrypt string with bcrypt: "
                "bcrypt: password length exceeds 72 bytes"
            )
        raise  # pragma: no cover - defensive support for future bcrypt backends


def bcrypt_verify(value: str, hashed: str) -> bool:
    return bool(_bcrypt_backend().checkpw(value.encode(), hashed.encode()))


def htpasswd(username: str, password: str) -> str:
    if ":" in username:
        return f"invalid username: {username}"
    return f"{username}:{bcrypt_hash(password)}"


def generate_private_key(key_type: str) -> str:
    if key_type not in {"", "rsa", "dsa", "ecdsa", "ed25519"}:
        return f"Unknown type {key_type}"
    api = _x509_backend()
    if key_type in {"", "rsa"}:
        key = api["rsa"].generate_private_key(public_exponent=65537, key_size=4096)
    elif key_type == "dsa":
        key = api["dsa"].generate_private_key(key_size=2048)
    elif key_type == "ecdsa":
        key = api["ec"].generate_private_key(api["ec"].SECP256R1())
    else:
        key = api["ed25519"].Ed25519PrivateKey.generate()
    return _serialize_key(key, api)


def build_custom_certificate(b64cert: str, b64key: str) -> Certificate:
    api = _x509_backend()
    try:
        cert = base64.b64decode(b64cert, validate=True)
    except ValueError as error:
        raise ValueError("unable to decode base64 certificate") from error
    try:
        key = base64.b64decode(b64key, validate=True)
    except ValueError as error:
        raise ValueError("unable to decode base64 private key") from error
    api["x509"].load_pem_x509_certificate(cert)
    api["serialization"].load_pem_private_key(key, password=None)
    return Certificate(cert.decode(), key.decode())


def build_custom_certificate_result(b64cert: str, b64key: str) -> FunctionResult:
    return _certificate_result(lambda: build_custom_certificate(b64cert, b64key))


def generate_ca(
    common_name: str, days_valid: int, *, clock: Clock | None = None
) -> Certificate:
    api = _x509_backend()
    key = api["rsa"].generate_private_key(public_exponent=65537, key_size=2048)
    return _make_certificate(
        common_name, (), (), days_valid, key, None, True, clock, api
    )


def generate_ca_result(
    common_name: str, days_valid: int, *, clock: Clock | None = None
) -> FunctionResult:
    return _certificate_result(
        lambda: generate_ca(common_name, days_valid, clock=clock)
    )


def generate_ca_with_key(
    common_name: str, days_valid: int, private_key: str, *, clock: Clock | None = None
) -> Certificate:
    api = _x509_backend()
    key = _load_key(private_key, api)
    return _make_certificate(
        common_name, (), (), days_valid, key, None, True, clock, api
    )


def generate_ca_with_key_result(
    common_name: str,
    days_valid: int,
    private_key: str,
    *,
    clock: Clock | None = None,
) -> FunctionResult:
    return _certificate_result(
        lambda: generate_ca_with_key(common_name, days_valid, private_key, clock=clock)
    )


def generate_self_signed_certificate(
    common_name: str,
    ips: Sequence[object],
    dns_names: Sequence[object],
    days_valid: int,
    *,
    clock: Clock | None = None,
) -> Certificate:
    api = _x509_backend()
    key = api["rsa"].generate_private_key(public_exponent=65537, key_size=2048)
    return _make_certificate(
        common_name, ips, dns_names, days_valid, key, None, False, clock, api
    )


def generate_self_signed_certificate_result(
    common_name: str,
    ips: Sequence[object],
    dns_names: Sequence[object],
    days_valid: int,
    *,
    clock: Clock | None = None,
) -> FunctionResult:
    return _certificate_result(
        lambda: generate_self_signed_certificate(
            common_name, ips, dns_names, days_valid, clock=clock
        )
    )


def generate_self_signed_certificate_with_key(
    common_name: str,
    ips: Sequence[object],
    dns_names: Sequence[object],
    days_valid: int,
    private_key: str,
    *,
    clock: Clock | None = None,
) -> Certificate:
    api = _x509_backend()
    return _make_certificate(
        common_name,
        ips,
        dns_names,
        days_valid,
        _load_key(private_key, api),
        None,
        False,
        clock,
        api,
    )


def generate_self_signed_certificate_with_key_result(
    common_name: str,
    ips: Sequence[object],
    dns_names: Sequence[object],
    days_valid: int,
    private_key: str,
    *,
    clock: Clock | None = None,
) -> FunctionResult:
    return _certificate_result(
        lambda: generate_self_signed_certificate_with_key(
            common_name, ips, dns_names, days_valid, private_key, clock=clock
        )
    )


def generate_signed_certificate(
    common_name: str,
    ips: Sequence[object],
    dns_names: Sequence[object],
    days_valid: int,
    ca: Certificate,
    *,
    clock: Clock | None = None,
) -> Certificate:
    api = _x509_backend()
    key = api["rsa"].generate_private_key(public_exponent=65537, key_size=2048)
    return _make_certificate(
        common_name, ips, dns_names, days_valid, key, ca, False, clock, api
    )


def generate_signed_certificate_result(
    common_name: str,
    ips: Sequence[object],
    dns_names: Sequence[object],
    days_valid: int,
    ca: Certificate,
    *,
    clock: Clock | None = None,
) -> FunctionResult:
    return _certificate_result(
        lambda: generate_signed_certificate(
            common_name, ips, dns_names, days_valid, ca, clock=clock
        )
    )


def generate_signed_certificate_with_key(
    common_name: str,
    ips: Sequence[object],
    dns_names: Sequence[object],
    days_valid: int,
    ca: Certificate,
    private_key: str,
    *,
    clock: Clock | None = None,
) -> Certificate:
    api = _x509_backend()
    return _make_certificate(
        common_name,
        ips,
        dns_names,
        days_valid,
        _load_key(private_key, api),
        ca,
        False,
        clock,
        api,
    )


def generate_signed_certificate_with_key_result(
    common_name: str,
    ips: Sequence[object],
    dns_names: Sequence[object],
    days_valid: int,
    ca: Certificate,
    private_key: str,
    *,
    clock: Clock | None = None,
) -> FunctionResult:
    return _certificate_result(
        lambda: generate_signed_certificate_with_key(
            common_name, ips, dns_names, days_valid, ca, private_key, clock=clock
        )
    )


def _certificate_result(operation: Callable[[], Certificate]) -> FunctionResult:
    try:
        return FunctionResult.success(operation())
    except (TypeError, ValueError) as error:
        return FunctionResult.failure(error, Certificate("", ""))


def _make_certificate(
    common_name: str,
    ips: object,
    dns_names: object,
    days_valid: int,
    key: Any,
    ca: Certificate | None,
    is_ca: bool,
    clock: Clock | None,
    api: dict[str, Any],
) -> Certificate:
    ip_values = _certificate_sequence(ips)
    dns_values = _certificate_sequence(dns_names)
    x509 = api["x509"]
    parsed_ips: list[ipaddress.IPv4Address | ipaddress.IPv6Address] = []
    for value in ip_values:
        if not isinstance(value, str):
            raise TypeError(f"error parsing ip: {value} is not a string")
        try:
            parsed_ips.append(ipaddress.ip_address(value))
        except ValueError as error:
            raise ValueError(f"error parsing ip: {value}") from error
    parsed_dns: list[str] = []
    for value in dns_values:
        if not isinstance(value, str):
            raise TypeError(
                f"error processing alternate dns name: {value} is not a string"
            )
        parsed_dns.append(value)
    current = (clock or (lambda: datetime.now(UTC)))()
    subject = x509.Name([x509.NameAttribute(api["NameOID"].COMMON_NAME, common_name)])
    parent = x509.load_pem_x509_certificate(ca.Cert.encode()) if ca else None
    signer = _load_key(ca.Key, api) if ca else key
    builder = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(parent.subject if parent else subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(current)
        .not_valid_after(current + timedelta(days=days_valid))
        .add_extension(x509.BasicConstraints(ca=is_ca, path_length=None), True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                key_encipherment=True,
                content_commitment=False,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=is_ca,
                crl_sign=False,
                encipher_only=None,
                decipher_only=None,
            ),
            True,
        )
    )
    alternative_names: list[Any] = [x509.IPAddress(value) for value in parsed_ips]
    alternative_names.extend(x509.DNSName(value) for value in parsed_dns)
    if alternative_names:
        builder = builder.add_extension(
            x509.SubjectAlternativeName(alternative_names), False
        )
    if not is_ca:
        builder = builder.add_extension(
            x509.ExtendedKeyUsage(
                [
                    api["ExtendedKeyUsageOID"].SERVER_AUTH,
                    api["ExtendedKeyUsageOID"].CLIENT_AUTH,
                ]
            ),
            False,
        )
    algorithm = (
        None
        if isinstance(signer, api["ed25519"].Ed25519PrivateKey)
        else api["hashes"].SHA256()
    )
    certificate = builder.sign(private_key=signer, algorithm=algorithm)
    cert_pem = certificate.public_bytes(api["serialization"].Encoding.PEM).decode()
    return Certificate(cert_pem, _serialize_key(key, api))


def _certificate_sequence(value: object) -> Sequence[object]:
    if value is None or value is UNTYPED_NIL:
        return ()
    if not isinstance(value, Sequence):
        raise TypeError(f"{value!r} is not a sequence")
    return cast(Sequence[object], value)


def _load_key(value: str, api: dict[str, Any]) -> Any:
    return api["serialization"].load_pem_private_key(value.encode(), password=None)


def _serialize_key(key: Any, api: dict[str, Any]) -> str:
    serialization = api["serialization"]
    private_format = (
        serialization.PrivateFormat.PKCS8
        if isinstance(key, api["ed25519"].Ed25519PrivateKey)
        else serialization.PrivateFormat.TraditionalOpenSSL
    )
    return cast(
        bytes,
        key.private_bytes(
            serialization.Encoding.PEM, private_format, serialization.NoEncryption()
        ),
    ).decode()


def _bcrypt_backend() -> Any:
    try:
        import bcrypt
    except ImportError as error:
        raise RuntimeError(
            "bcrypt requires the optional 'crypto' extra; install gotpl[crypto]"
        ) from error
    return bcrypt


def _cipher_backend() -> tuple[Any, Any, Any]:
    try:
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    except ImportError as error:
        raise RuntimeError(
            "AES helpers require the optional 'crypto' extra; install gotpl[crypto]"
        ) from error
    return Cipher, algorithms, modes


def _x509_backend() -> dict[str, Any]:
    try:
        from cryptography import x509
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import dsa, ec, ed25519, rsa
        from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID
    except ImportError as error:
        raise RuntimeError(
            "certificate helpers require the optional 'crypto' extra; "
            "install gotpl[crypto]"
        ) from error
    return {
        "x509": x509,
        "hashes": hashes,
        "serialization": serialization,
        "dsa": dsa,
        "ec": ec,
        "ed25519": ed25519,
        "rsa": rsa,
        "NameOID": NameOID,
        "ExtendedKeyUsageOID": ExtendedKeyUsageOID,
    }
