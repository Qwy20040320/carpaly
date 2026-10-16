#!/usr/bin/env python3
"""Compare a public Environment signer pin with the reviewed repository policy."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

try:
    from scripts.release_signing_policy import LEGACY_RELEASE_CERT_SHA256, normalize_sha256, signer_for_ledger_version
except ModuleNotFoundError:  # Direct `python scripts/check_release_signer_pin.py ...` execution.
    from release_signing_policy import LEGACY_RELEASE_CERT_SHA256, normalize_sha256, signer_for_ledger_version


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


def check(
    policy_path: Path,
    actual: str,
    *,
    version_name: str | None = None,
    version_code: int | None = None,
) -> str:
    try:
        policy = json.loads(policy_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SignerPinError("Could not read the reviewed Release signer policy") from exc
    if not isinstance(policy, dict):
        raise SignerPinError("Release signer policy must be a JSON object")
    current = policy.get("current")
    if not isinstance(current, dict):
        raise SignerPinError("Ledger current version is missing")
    if (version_name is None) != (version_code is None):
        raise SignerPinError("Both version name and version code are required for an explicit signer check")
    selected_name = version_name if version_name is not None else current.get("versionName")
    selected_code = version_code if version_code is not None else current.get("versionCode")
    if not isinstance(selected_name, str) or isinstance(selected_code, bool) or not isinstance(selected_code, int):
        raise SignerPinError("Selected version metadata is missing or malformed")

    expected = signer_for_ledger_version(policy, selected_name, selected_code)
    if expected is None:
        raise SignerPinError("Selected version has no matching approved signing-epoch evidence")
    current_signer = signer_for_ledger_version(
        policy, str(current.get("versionName", "")), current.get("versionCode")
    )
    if current_signer is None:
        raise SignerPinError("Ledger current version has no matching approved signing-epoch evidence")
    delivery = policy.get("deliveryPolicy")
    if not isinstance(delivery, dict):
        raise SignerPinError("Ledger deliveryPolicy is missing")
    ledger_signer = normalize_sha256(policy.get("releaseCertificateSha256"))
    delivery_signer = normalize_sha256(delivery.get("releaseCertificateSha256"))
    legacy_signer = normalize_sha256(policy.get("legacyReleaseCertificateSha256"))
    if legacy_signer != LEGACY_RELEASE_CERT_SHA256:
        raise SignerPinError("Ledger legacy signer differs from reviewed policy")
    if ledger_signer != current_signer or delivery_signer != current_signer:
        raise SignerPinError("Ledger active signer fields conflict with the current version epoch")
    configured = normalize(actual, "Environment RELEASE_SIGNING_CERT_SHA256")
    if configured != expected:
        raise SignerPinError(
            f"Environment signer pin differs from versionCode {selected_code} signing epoch; refusing before any credential use"
        )
    return expected


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--actual", default="")
    parser.add_argument("--version-name")
    parser.add_argument("--version-code", type=int)
    args = parser.parse_args()
    try:
        fingerprint = check(
            args.policy,
            args.actual,
            version_name=args.version_name,
            version_code=args.version_code,
        )
    except SignerPinError as exc:
        print(f"RELEASE_SIGNER_PIN_STATUS=FAIL: {exc}", file=sys.stderr)
        return 1
    print(f"RELEASE_SIGNER_PIN_STATUS=PASS sha256={fingerprint}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
