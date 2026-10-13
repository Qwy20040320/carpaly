#!/usr/bin/env python3
"""Fail-closed checks for enabling the separately protected production OTA signer."""

from __future__ import annotations

import argparse
import base64
import json
import re
import sys
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec


ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "config/ota-publisher-policy.json"
TRUST_PATH = ROOT / "common/src/main/res/raw/ota_manifest_public_keys.json"
KEY_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


class PublisherPolicyError(ValueError):
    pass


def validate_readiness(policy: Any, trust: Any) -> str:
    if not isinstance(policy, dict) or policy.get("schemaVersion") != 1:
        raise PublisherPolicyError("OTA publisher policy is missing or has an unsupported schema")
    if policy.get("productionEnabled") is not True:
        raise PublisherPolicyError("Production OTA publishing is explicitly disabled")
    if policy.get("environment") != "ota-manifest-publisher" or policy.get("allowedBranch") != "main":
        raise PublisherPolicyError("OTA publisher policy must target the dedicated Environment on main")
    if policy.get("environmentConfigurationReviewed") is not True:
        raise PublisherPolicyError("Production OTA Environment setup has not been reviewed and attested")
    reviewers = policy.get("minimumRequiredReviewers")
    if isinstance(reviewers, bool) or not isinstance(reviewers, int) or reviewers < 1:
        raise PublisherPolicyError("Production OTA Environment must require at least one reviewer")
    key_id = policy.get("keyId")
    if not isinstance(key_id, str) or not KEY_ID.fullmatch(key_id):
        raise PublisherPolicyError("Production OTA key id is missing or invalid")
    if not isinstance(trust, dict) or trust.get("schemaVersion") != 1 or not isinstance(trust.get("keys"), list):
        raise PublisherPolicyError("App-pinned OTA trust store is malformed")
    matches = [record for record in trust["keys"] if isinstance(record, dict) and record.get("keyId") == key_id]
    if len(matches) != 1 or matches[0].get("algorithm") != "SHA256withECDSA-P256" \
            or matches[0].get("status") != "active":
        raise PublisherPolicyError("Production OTA key id does not resolve to one active app-pinned P-256 key")
    try:
        public_der = base64.b64decode(matches[0]["publicKeyX509Base64"], validate=True)
        public_key = serialization.load_der_public_key(public_der)
    except (KeyError, ValueError, TypeError) as exc:
        raise PublisherPolicyError("Production OTA public key is not valid X.509 SubjectPublicKeyInfo DER") from exc
    if not isinstance(public_key, ec.EllipticCurvePublicKey) or not isinstance(public_key.curve, ec.SECP256R1):
        raise PublisherPolicyError("Production OTA public key is not ECDSA P-256")
    return key_id


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PublisherPolicyError("Could not read OTA publisher policy or pinned public keys") from exc


def main() -> int:
    try:
        key_id = validate_readiness(_read_json(POLICY_PATH), _read_json(TRUST_PATH))
    except (OSError, PublisherPolicyError) as exc:
        print(f"OTA_PUBLISHER_READINESS=BLOCKED: {exc}", file=sys.stderr)
        return 2
    print(f"OTA_PUBLISHER_READINESS=PASS key_id={key_id} private_key=NOT_READ")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
