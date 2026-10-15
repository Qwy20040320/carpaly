#!/usr/bin/env python3
"""Compare a public Environment signer pin with the reviewed repository policy."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


FINGERPRINT = re.compile(r"^[0-9a-f]{64}$")


class SignerPinError(ValueError):
    """A signer pin is missing, malformed, or conflicts with reviewed policy."""


def normalize(value: object, label: str) -> str:
    if not isinstance(value, str):
        raise SignerPinError(f"{label} is missing")
    normalized = value.strip().lower().removeprefix("sha256:").replace(":", "").replace(" ", "")
    if not FINGERPRINT.fullmatch(normalized):
        raise SignerPinError(f"{label} must be a 32-byte SHA-256 fingerprint")
    return normalized


def check(policy_path: Path, actual: str) -> str:
    try:
        policy = json.loads(policy_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SignerPinError("Could not read the reviewed Release signer policy") from exc
    if not isinstance(policy, dict):
        raise SignerPinError("Release signer policy must be a JSON object")
    expected = normalize(policy.get("releaseCertificateSha256"), "Ledger releaseCertificateSha256")
    delivery = policy.get("deliveryPolicy")
    if not isinstance(delivery, dict):
        raise SignerPinError("Ledger deliveryPolicy is missing")
    delivery_expected = normalize(
        delivery.get("releaseCertificateSha256"), "Ledger deliveryPolicy.releaseCertificateSha256",
    )
    configured = normalize(actual, "Environment RELEASE_SIGNING_CERT_SHA256")
    if expected != delivery_expected:
        raise SignerPinError("Ledger signer policy fields conflict; refusing before any credential use")
    if configured != expected:
        raise SignerPinError("Environment signer pin differs from reviewed policy; refusing before any credential use")
    return expected


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--actual", default="")
    args = parser.parse_args()
    try:
        fingerprint = check(args.policy, args.actual)
    except SignerPinError as exc:
        print(f"RELEASE_SIGNER_PIN_STATUS=FAIL: {exc}", file=sys.stderr)
        return 1
    print(f"RELEASE_SIGNER_PIN_STATUS=PASS sha256={fingerprint}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
