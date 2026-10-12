#!/usr/bin/env python3
"""Export one X.509-encoded ECDSA P-256 OTA public-key record; never prints private bytes."""

from __future__ import annotations

import argparse
import base64
import json
import sys
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec


def public_key_record(private_key_pem: bytes, key_id: str) -> dict[str, Any]:
    if not key_id or len(key_id) > 64 or any(
        not (character.isascii() and (character.isalnum() or character in "._-"))
        for character in key_id
    ):
        raise ValueError("OTA key id must contain 1-64 ASCII letters, digits, dot, underscore, or hyphen")
    try:
        signer = serialization.load_pem_private_key(private_key_pem, password=None)
    except (TypeError, ValueError) as exc:
        raise ValueError("OTA signing key must be a readable unencrypted PKCS#8 PEM") from exc
    if not isinstance(signer, ec.EllipticCurvePrivateKey) or not isinstance(
        signer.curve, ec.SECP256R1
    ):
        raise ValueError("OTA signing key must use ECDSA P-256")
    public_der = signer.public_key().public_bytes(
        serialization.Encoding.DER,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return {
        "keyId": key_id,
        "algorithm": "SHA256withECDSA-P256",
        "status": "active",
        "publicKeyX509Base64": base64.b64encode(public_der).decode("ascii"),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private-key", type=Path, required=True,
                        help="path to protected offline key material (never echoed or copied)")
    parser.add_argument("--key-id", required=True)
    arguments = parser.parse_args(argv)
    try:
        record = public_key_record(arguments.private_key.read_bytes(), arguments.key_id)
    except (OSError, ValueError) as exc:
        print(f"OTA_PUBLIC_KEY_EXPORT=BLOCKED: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(record, sort_keys=True, indent=2))
    print("OTA_PUBLIC_KEY_EXPORT=PASS", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
