"""Pinned CarPaly Android Release signing epochs.

This module contains public certificate fingerprints only. It never handles keys.
Changing an epoch requires a reviewed policy change and new evidence.
"""

from __future__ import annotations

import re
from typing import Any


LEGACY_RELEASE_CERT_SHA256 = "4d26d1c861b41a2cee4515e31f5f5c7eb13b9dd06e7485aa1687bc1d2ac73d90"
CURRENT_RELEASE_CERT_SHA256 = "d9b329525fc1ef21c365fab72c10367527cc038297c4f30eaa22b2207429139e"

APPROVED_SIGNING_EPOCHS = (
    {
        "id": "legacy-v1.1.4-through-v1.1.52",
        "minimumVersionCode": 36,
        "maximumVersionCode": 40,
        "certificateSha256": LEGACY_RELEASE_CERT_SHA256,
        "upgradePolicy": "legacy-signer-only",
    },
    {
        "id": "fresh-install-v1.1.53-plus",
        "minimumVersionCode": 41,
        "maximumVersionCode": None,
        "certificateSha256": CURRENT_RELEASE_CERT_SHA256,
        "upgradePolicy": "fresh-install-required",
    },
)


def signing_epoch_for_version_code(epochs: Any, version_code: int) -> dict[str, Any] | None:
    if isinstance(version_code, bool) or not isinstance(version_code, int) or version_code < 1:
        return None
    if not isinstance(epochs, list):
        return None
    matches = []
    for epoch in epochs:
        if not isinstance(epoch, dict):
            continue
        minimum = epoch.get("minimumVersionCode")
        maximum = epoch.get("maximumVersionCode")
        if (
            isinstance(minimum, int)
            and not isinstance(minimum, bool)
            and version_code >= minimum
            and (
                maximum is None
                or (isinstance(maximum, int) and not isinstance(maximum, bool) and version_code <= maximum)
            )
        ):
            matches.append(epoch)
    return matches[0] if len(matches) == 1 else None


def approved_epoch_for_version_code(version_code: int) -> dict[str, Any] | None:
    return signing_epoch_for_version_code([dict(epoch) for epoch in APPROVED_SIGNING_EPOCHS], version_code)


def signer_for_ledger_version(ledger: dict, version_name: str, version_code: int) -> str | None:
    """Return a signer only when the allocation and pinned code epoch both agree."""
    epoch = signing_epoch_for_version_code(ledger.get("signingEpochs"), version_code)
    approved = approved_epoch_for_version_code(version_code)
    if epoch is None or approved is None:
        return None
    for field in ("id", "minimumVersionCode", "maximumVersionCode", "upgradePolicy"):
        if epoch.get(field) != approved[field]:
            return None
    expected = approved["certificateSha256"]
    actual_epoch_cert = epoch.get("certificateSha256")
    if not isinstance(actual_epoch_cert, str) or actual_epoch_cert.lower() != expected:
        return None

    records = [
        record
        for record in [*ledger.get("allocations", []), *ledger.get("verifiedHistoricalDeliveries", [])]
        if isinstance(record, dict)
        and record.get("versionName") == version_name
        and record.get("versionCode") == version_code
    ]
    if len(records) != 1:
        return None
    record = records[0]
    actual = record.get("signerCertificateSha256")
    if not isinstance(actual, str) or actual.lower() != expected:
        return None
    if record.get("signingEpochId") not in (None, approved["id"]):
        return None
    return expected


def validate_signing_epoch_configuration(ledger: dict) -> None:
    epochs = ledger.get("signingEpochs")
    if not isinstance(epochs, list) or len(epochs) != len(APPROVED_SIGNING_EPOCHS):
        raise ValueError("The ledger must contain the two reviewed Release signing epochs")
    for actual, approved in zip(epochs, APPROVED_SIGNING_EPOCHS):
        if not isinstance(actual, dict) or any(actual.get(key) != value for key, value in approved.items()):
            raise ValueError("The ledger Release signing epochs differ from the reviewed certificate policy")
    if normalize_sha256(ledger.get("legacyReleaseCertificateSha256")) != LEGACY_RELEASE_CERT_SHA256:
        raise ValueError("The ledger legacy signer fingerprint differs from the reviewed certificate policy")


def normalize_sha256(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = re.sub(r"[:\s]", "", value).lower()
    return normalized if re.fullmatch(r"[a-f0-9]{64}", normalized) else None
