#!/usr/bin/env python3
"""Build signed, fail-closed CarPaly OTA manifests from verified public Releases."""

from __future__ import annotations

import base64
import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.exceptions import InvalidSignature

if __package__:
    from .ota_key_material import parse_p256_pkcs8_private_key
else:
    from ota_key_material import parse_p256_pkcs8_private_key

if __package__:
    from .sync_release_docs import _released_records, public_releases
else:
    from sync_release_docs import _released_records, public_releases


ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "config/ota-policy.json"
LEDGER_PATH = ROOT / "config/android-version-ledger.json"
TRUST_PATH = ROOT / "common/src/main/res/raw/ota_manifest_public_keys.json"
VERSION = re.compile(r"^\d+\.\d+\.\d+$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
KEY_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
COMMIT_SHA = re.compile(r"^[0-9a-f]{40}$")
CHANNELS = ("stable", "beta")


class ManifestError(ValueError):
    pass


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ManifestError(f"Could not read JSON configuration {path.relative_to(ROOT)}: {exc}") from exc
    if not isinstance(value, dict):
        raise ManifestError(f"Expected a JSON object in {path.relative_to(ROOT)}")
    return value


def _parse_private_key(pem: str) -> ec.EllipticCurvePrivateKey:
    if not pem.strip():
        raise ManifestError("OTA manifest signing private key is not configured")
    try:
        return parse_p256_pkcs8_private_key(pem.encode("utf-8"))
    except (UnicodeEncodeError, ValueError) as exc:
        raise ManifestError("OTA manifest signing key must be an unencrypted PKCS#8 ECDSA P-256 key") from exc


def public_key_id_matches(private_key: ec.EllipticCurvePrivateKey, key_id: str,
                          trust: Mapping[str, Any]) -> bool:
    if not KEY_ID.fullmatch(key_id):
        return False
    records = trust.get("keys")
    if not isinstance(records, list):
        return False
    public_der = private_key.public_key().public_bytes(
        serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    expected = base64.b64encode(public_der).decode("ascii")
    matches = [item for item in records if isinstance(item, Mapping) and item.get("keyId") == key_id]
    return len(matches) == 1 and matches[0].get("algorithm") == "SHA256withECDSA-P256" \
        and matches[0].get("status") == "active" and matches[0].get("publicKeyX509Base64") == expected


def canonical_payload(payload: Mapping[str, Any]) -> bytes:
    """The signed bytes are carried verbatim in the envelope, avoiding parser reserialization drift."""
    try:
        text = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ManifestError("OTA payload contains a value outside the canonical JSON subset") from exc
    return text.encode("utf-8")


def sign_payload(payload: Mapping[str, Any], key_id: str,
                 private_key_pem: str, trust: Mapping[str, Any]) -> dict[str, Any]:
    key = _parse_private_key(private_key_pem)
    if payload.get("manifestKeyId") != key_id:
        raise ManifestError("Payload key id differs from requested signer key id")
    if not public_key_id_matches(key, key_id, trust):
        raise ManifestError("OTA signing key does not match an active app-pinned public key")
    encoded = canonical_payload(payload)
    signature = key.sign(encoded, ec.ECDSA(hashes.SHA256()))
    return {
        "schemaVersion": 1,
        "manifestKeyId": key_id,
        "signedPayload": base64.b64encode(encoded).decode("ascii"),
        "manifestSignature": base64.b64encode(signature).decode("ascii"),
    }


def verify_envelope(envelope: Mapping[str, Any], trusted_keys: Mapping[str, Any]) -> dict[str, Any]:
    if set(envelope) != {"schemaVersion", "manifestKeyId", "signedPayload", "manifestSignature"}:
        raise ManifestError("OTA envelope has unexpected or missing fields")
    if envelope.get("schemaVersion") != 1:
        raise ManifestError("Unsupported OTA envelope schema")
    key_id = envelope.get("manifestKeyId")
    if not isinstance(key_id, str) or not KEY_ID.fullmatch(key_id):
        raise ManifestError("Invalid OTA manifest key id")
    records = trusted_keys.get("keys")
    if not isinstance(records, list):
        raise ManifestError("App-pinned OTA trust store is malformed")
    matches = [item for item in records if isinstance(item, Mapping) and item.get("keyId") == key_id]
    if len(matches) != 1 or matches[0].get("algorithm") != "SHA256withECDSA-P256" \
            or matches[0].get("status") not in {"active", "retiring"}:
        raise ManifestError("OTA manifest signer is not trusted by this app")
    try:
        public_der = base64.b64decode(matches[0]["publicKeyX509Base64"], validate=True)
        public_key = serialization.load_der_public_key(public_der)
        if not isinstance(public_key, ec.EllipticCurvePublicKey) or not isinstance(public_key.curve, ec.SECP256R1):
            raise ManifestError("Pinned OTA key is not ECDSA P-256")
        payload_bytes = base64.b64decode(envelope["signedPayload"], validate=True)
        signature = base64.b64decode(envelope["manifestSignature"], validate=True)
        public_key.verify(signature, payload_bytes, ec.ECDSA(hashes.SHA256()))
        payload = json.loads(payload_bytes.decode("utf-8"))
    except ManifestError:
        raise
    except (KeyError, ValueError, UnicodeDecodeError, InvalidSignature) as exc:
        raise ManifestError("OTA manifest signature or payload is invalid") from exc
    if not isinstance(payload, dict) or payload.get("manifestKeyId") != key_id:
        raise ManifestError("Signed payload key id does not match its envelope")
    return payload


def _iso_release_date(release: Mapping[str, Any]) -> str:
    value = release.get("published_at")
    if not isinstance(value, str):
        raise ManifestError("Verified Release has no published timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ManifestError("Verified Release has an invalid published timestamp") from exc
    if parsed.tzinfo is None:
        raise ManifestError("Verified Release timestamp must include a timezone")
    return parsed.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def checksum_sidecar_matches(body: bytes, *, apk_name: str, expected_sha256: str, expected_size: int) -> bool:
    if not 1 <= len(body) <= 256 or len(body) != expected_size or not SHA256.fullmatch(expected_sha256):
        return False
    try:
        text = body.decode("ascii")
    except UnicodeDecodeError:
        return False
    match = re.fullmatch(r"([0-9a-fA-F]{64})  ([^\r\n]+)\r?\n", text)
    return bool(match and match.group(1).lower() == expected_sha256 and match.group(2) == apk_name)


def verified_channel_records(*, releases: Sequence[Mapping[str, Any]], tags: Sequence[Mapping[str, Any]],
                             repository: str, ledger: Mapping[str, Any],
                             verifications: Mapping[str, Mapping[str, Any] | None],
                             policy: Mapping[str, Any],
                             main_verified_tags: set[str] | None = None,
                             verified_checksum_tags: set[str] | None = None) -> dict[str, dict[str, Any] | None]:
    records = _released_records(releases, tags, repository, ledger, verifications)
    result: dict[str, dict[str, Any] | None] = {channel: None for channel in CHANNELS}
    for record in records:
        if record.get("draft") or record.get("apkVerificationStatus") != "PASS":
            continue
        if main_verified_tags is not None and record.get("tag") not in main_verified_tags:
            continue
        if verified_checksum_tags is not None and record.get("tag") not in verified_checksum_tags:
            continue
        channel = "beta" if record.get("prerelease") else "stable"
        apk = record.get("verifiedApk")
        release = next((item for item in public_releases(releases) if item.get("tag_name") == record.get("tag")), None)
        if not isinstance(apk, Mapping) or release is None:
            continue
        version_name = str(apk.get("versionName", ""))
        version_code = apk.get("versionCode")
        digest = str(apk.get("sha256", "")).lower()
        expected_name = f"CarPaly-XingyueL-v{version_name}.apk"
        expected_checksum_name = expected_name + ".sha256"
        checksum_assets = [asset for asset in record.get("assets", [])
                           if isinstance(asset, Mapping) and asset.get("name") == expected_checksum_name]
        if not VERSION.fullmatch(version_name) or record.get("tag") != f"v{version_name}" \
                or apk.get("name") != expected_name or not isinstance(version_code, int) or version_code < 1 \
                or not SHA256.fullmatch(digest) or len(checksum_assets) != 1 \
                or not COMMIT_SHA.fullmatch(str(record.get("tagSha", ""))):
            continue
        checksum_asset = checksum_assets[0]
        checksum_size = checksum_asset.get("size")
        checksum_url = str(checksum_asset.get("url", ""))
        if not isinstance(checksum_size, int) or checksum_size not in range(1, 257) \
                or checksum_url != str(apk["url"]) + ".sha256":
            continue
        if version_code < int(policy["minimumSupportedVersionCode"]):
            continue
        apk_size = int(apk.get("size") or 0)
        if apk_size <= 0 or apk_size > int(policy["maximumApkBytes"]):
            continue
        channel_records = result[channel]
        if channel_records is None or version_code > channel_records["versionCode"]:
            result[channel] = {
                "schemaVersion": 1,
                "channel": channel,
                "versionName": version_name,
                "versionCode": version_code,
                "packageName": str(policy["applicationId"]),
                "minimumSupportedVersionCode": int(policy["minimumSupportedVersionCode"]),
                "releaseTag": str(record["tag"]),
                "sourceCommit": str(record["tagSha"]),
                "releaseDate": _iso_release_date(release),
                "releaseNotesUrl": str(record["htmlUrl"]),
                "releaseNotes": str(release.get("body", ""))[:8_000],
                "apkUrl": str(apk["url"]),
                "checksumUrl": checksum_url,
                "checksumSize": checksum_size,
                "apkSize": apk_size,
                "apkSha256": digest,
                "signerCertSha256": str(apk.get("signerSha256", "")).lower(),
                "manifestKeyId": "",
            }
    return result


def prepare_signed_channels(*, releases: Sequence[Mapping[str, Any]], tags: Sequence[Mapping[str, Any]],
                            repository: str, ledger: Mapping[str, Any],
                            verifications: Mapping[str, Mapping[str, Any] | None],
                            policy: Mapping[str, Any], trust: Mapping[str, Any],
                            private_key_pem: str, key_id: str,
                            now: datetime | None = None,
                            main_verified_tags: set[str] | None = None,
                            verified_checksum_tags: set[str] | None = None) -> dict[str, dict[str, Any]]:
    key = _parse_private_key(private_key_pem)
    if not public_key_id_matches(key, key_id, trust):
        raise ManifestError("OTA signing key does not match an active app-pinned public key")
    payloads = verified_channel_records(
        releases=releases, tags=tags, repository=repository, ledger=ledger,
        verifications=verifications, policy=policy, main_verified_tags=main_verified_tags,
        verified_checksum_tags=verified_checksum_tags,
    )
    issued_at = (now or datetime.now(timezone.utc)).astimezone(timezone.utc).replace(microsecond=0)
    expires_at = issued_at + timedelta(days=30)
    issued_text = issued_at.isoformat().replace("+00:00", "Z")
    expires_text = expires_at.isoformat().replace("+00:00", "Z")
    result: dict[str, dict[str, Any]] = {}
    for channel, payload in payloads.items():
        if payload is None:
            payload = {
                "schemaVersion": 1,
                "channel": channel,
                "available": False,
                "packageName": str(policy["applicationId"]),
                "minimumSupportedVersionCode": int(policy["minimumSupportedVersionCode"]),
                "manifestKeyId": key_id,
            }
        else:
            payload["available"] = True
            payload["manifestKeyId"] = key_id
        payload["issuedAt"] = issued_text
        payload["expiresAt"] = expires_text
        result[channel] = sign_payload(payload, key_id, private_key_pem, trust)
    return result


def write_channels(output_dir: Path, envelopes: Mapping[str, Mapping[str, Any]]) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for channel in CHANNELS:
        envelope = envelopes.get(channel)
        if envelope is None:
            continue  # A missing channel never replaces an older signed manifest.
        target = output_dir / f"{channel}.json"
        temporary = target.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(envelope, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(temporary, target)
        written.append(target)
    return written
