"""Strict parsing for OTA signing-key input material."""

from __future__ import annotations

import re

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec


_PKCS8_PEM = re.compile(
    rb"\A\s*-----BEGIN PRIVATE KEY-----\s+[A-Za-z0-9+/=\r\n]+\s+-----END PRIVATE KEY-----\s*\Z"
)


def parse_p256_pkcs8_private_key(pem: bytes) -> ec.EllipticCurvePrivateKey:
    """Load exactly one unencrypted PKCS#8 PEM ECDSA P-256 key.

    The PEM armor check matters because OpenSSL and cryptography also accept the
    SEC1 ``EC PRIVATE KEY`` form, which is not the format required by the OTA
    publisher contract.
    """
    if not isinstance(pem, bytes) or not _PKCS8_PEM.fullmatch(pem):
        raise ValueError("OTA signing key must be one unencrypted PKCS#8 PEM block")
    try:
        key = serialization.load_pem_private_key(pem, password=None)
    except (TypeError, ValueError) as exc:
        raise ValueError("OTA signing key is not a readable unencrypted PKCS#8 PEM key") from exc
    if not isinstance(key, ec.EllipticCurvePrivateKey) or not isinstance(key.curve, ec.SECP256R1):
        raise ValueError("OTA signing key must use ECDSA P-256")
    return key
