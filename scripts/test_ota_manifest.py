from __future__ import annotations

import base64
import json
import unittest
from datetime import datetime, timezone
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

if __package__:
    from . import build_ota_manifests, ota_manifest
else:
    import build_ota_manifests
    import ota_manifest


SIGNER = "d9b329525fc1ef21c365fab72c10367527cc038297c4f30eaa22b2207429139e"
LEGACY_SIGNER = "4d26d1c861b41a2cee4515e31f5f5c7eb13b9dd06e7485aa1687bc1d2ac73d90"
REPO = "Qwy20040320/carpaly"
APK_HASH = "a" * 64
KEY_ID = "test-ota-key"


def signer_for_test_version(version_code: int) -> str:
    """Match synthetic Release proofs to the repository's reviewed signer epochs."""
    return LEGACY_SIGNER if version_code <= 40 else SIGNER


def make_release(version: str, code: int, *, prerelease: bool = False, draft: bool = False):
    tag = f"v{version}"
    apk_name = f"CarPaly-XingyueL-v{version}.apk"
    apk_url = f"https://github.com/{REPO}/releases/download/{tag}/{apk_name}"
    release = {
        "tag_name": tag,
        "name": tag,
        "draft": draft,
        "prerelease": prerelease,
        "published_at": "2026-10-12T10:00:00Z",
        "html_url": f"https://github.com/{REPO}/releases/tag/{tag}",
        "body": "Verified notes",
        "assets": [
            {
                "name": apk_name,
                "browser_download_url": apk_url,
                "size": 12_000_000,
                "digest": f"sha256:{APK_HASH}",
            },
            {
                "name": apk_name + ".sha256",
                "browser_download_url": apk_url + ".sha256",
                "size": 96,
                "digest": "sha256:" + "b" * 64,
            },
        ],
    }
    checks = {name: "PASS" for name in (
        "APK_SIGNATURE", "PACKAGE_NAME_MATCH", "SIGNING_CERTIFICATE_MATCH",
        "APK_ZIP_INTEGRITY", "RELEASE_VARIANT_NOT_DEBUGGABLE",
    )}
    verification = {
        "status": "PASS",
        "apk": apk_name,
        "versionName": version,
        "versionCode": code,
        "packageName": "com.shihab.diplay.hudtest",
        "signerCertificateSha256": signer_for_test_version(code),
        "apkSha256": APK_HASH,
        "checks": checks,
    }
    return release, verification


def make_tags(*releases):
    return [
        {"name": release["tag_name"], "commit": {"sha": (str(index + 1) * 40)}}
        for index, (release, _) in enumerate(releases)
    ]


class SignedManifestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.private_key = ec.generate_private_key(ec.SECP256R1())
        der = cls.private_key.public_key().public_bytes(
            serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
        )
        cls.private_pem = cls.private_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ).decode("ascii")
        cls.trust = {
            "schemaVersion": 1,
            "keys": [{
                "keyId": KEY_ID,
                "algorithm": "SHA256withECDSA-P256",
                "status": "active",
                "publicKeyX509Base64": base64.b64encode(der).decode("ascii"),
            }],
        }
        cls.policy = {
            "applicationId": "com.shihab.diplay.hudtest",
            "minimumSupportedVersionCode": 36,
            "maximumApkBytes": 52_428_800,
        }
        cls.ledger = json.loads(ota_manifest.LEDGER_PATH.read_text(encoding="utf-8"))

    def test_signed_envelope_round_trips_and_detects_tampering(self):
        payload = {"schemaVersion": 1, "manifestKeyId": KEY_ID, "channel": "stable", "versionCode": 40}
        envelope = ota_manifest.sign_payload(payload, KEY_ID, self.private_pem, self.trust)
        self.assertEqual(payload, ota_manifest.verify_envelope(envelope, self.trust))
        tampered = dict(envelope)
        tampered["signedPayload"] = base64.b64encode(b'{"channel":"beta"}').decode("ascii")
        with self.assertRaises(ota_manifest.ManifestError):
            ota_manifest.verify_envelope(tampered, self.trust)

    def test_jca_compatible_cross_language_vector_verifies_in_python(self):
        fixture = json.loads((Path(__file__).resolve().parents[1] /
                              "common/src/test/resources/ota_cross_language_vector.json")
                             .read_text(encoding="utf-8"))
        envelope = {
            "schemaVersion": fixture["schemaVersion"],
            "manifestKeyId": fixture["keyId"],
            "signedPayload": fixture["signedPayload"],
            "manifestSignature": fixture["manifestSignature"],
        }
        trust = {"schemaVersion": 1, "keys": [{
            "keyId": fixture["keyId"],
            "algorithm": fixture["algorithm"],
            "status": "active",
            "publicKeyX509Base64": fixture["publicKeyX509Base64"],
        }]}
        payload = ota_manifest.verify_envelope(envelope, trust)
        self.assertEqual("phase11-cross-language-test", payload["manifestKeyId"])
        self.assertEqual("stable", payload["channel"])

    def test_signing_key_must_match_an_active_app_pinned_key(self):
        other = ec.generate_private_key(ec.SECP256R1()).private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ).decode("ascii")
        with self.assertRaisesRegex(ota_manifest.ManifestError, "does not match"):
            ota_manifest.sign_payload({"manifestKeyId": KEY_ID}, KEY_ID, other, self.trust)

    def test_signing_requires_pkcs8_pem_not_sec1_ec_private_key(self):
        sec1 = self.private_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption(),
        ).decode("ascii")
        with self.assertRaisesRegex(ota_manifest.ManifestError, "PKCS#8"):
            ota_manifest.sign_payload(
                {"manifestKeyId": KEY_ID}, KEY_ID, sec1, self.trust,
            )

    def test_verifier_rejects_pinned_record_with_wrong_algorithm_label(self):
        envelope = ota_manifest.sign_payload(
            {"manifestKeyId": KEY_ID}, KEY_ID, self.private_pem, self.trust,
        )
        mislabeled = {"keys": [{**self.trust["keys"][0], "algorithm": "ES256"}]}
        with self.assertRaisesRegex(ota_manifest.ManifestError, "not trusted"):
            ota_manifest.verify_envelope(envelope, mislabeled)

    def test_revoked_key_is_not_accepted_for_verification(self):
        payload = {"schemaVersion": 1, "manifestKeyId": KEY_ID}
        envelope = ota_manifest.sign_payload(payload, KEY_ID, self.private_pem, self.trust)
        revoked = {"keys": [{**self.trust["keys"][0], "status": "revoked"}]}
        with self.assertRaisesRegex(ota_manifest.ManifestError, "not trusted"):
            ota_manifest.verify_envelope(envelope, revoked)

    def test_only_verified_stable_and_beta_releases_enter_separate_channels(self):
        stable, stable_proof = make_release("1.1.51", 39)
        beta, beta_proof = make_release("1.1.52", 40, prerelease=True)
        draft, draft_proof = make_release("1.1.53", 41, prerelease=True, draft=True)
        records = ota_manifest.verified_channel_records(
            releases=[stable, beta, draft],
            tags=make_tags((stable, stable_proof), (beta, beta_proof), (draft, draft_proof)),
            repository=REPO,
            ledger=self.ledger,
            verifications={stable["tag_name"]: stable_proof, beta["tag_name"]: beta_proof,
                           draft["tag_name"]: draft_proof},
            policy=self.policy,
        )
        self.assertEqual("v1.1.51", records["stable"]["releaseTag"])
        self.assertEqual("v1.1.52", records["beta"]["releaseTag"])
        self.assertEqual(40, records["beta"]["versionCode"])

    def test_unverified_historical_asset_never_becomes_an_ota_release(self):
        release, proof = make_release("1.1.5", 37, prerelease=True)
        release["assets"][0]["name"] = "CarPaly-XingyueL1.1.5-Upgrade-Test.apk"
        records = ota_manifest.verified_channel_records(
            releases=[release], tags=make_tags((release, proof)), repository=REPO, ledger=self.ledger,
            verifications={release["tag_name"]: proof}, policy=self.policy,
        )
        self.assertIsNone(records["beta"])

    def test_signed_missing_channel_is_an_explicit_unavailable_tombstone(self):
        stable, proof = make_release("1.1.51", 39)
        envelopes = ota_manifest.prepare_signed_channels(
            releases=[stable], tags=make_tags((stable, proof)), repository=REPO, ledger=self.ledger,
            verifications={stable["tag_name"]: proof}, policy=self.policy,
            trust=self.trust, private_key_pem=self.private_pem, key_id=KEY_ID,
        )
        beta = ota_manifest.verify_envelope(envelopes["beta"], self.trust)
        self.assertFalse(beta["available"])
        self.assertEqual("beta", beta["channel"])

    def test_release_date_is_normalized_to_utc(self):
        value = ota_manifest._iso_release_date({"published_at": "2026-10-11T20:00:00+08:00"})
        self.assertEqual("2026-10-11T12:00:00Z", value)

    def test_checksum_sidecar_must_match_exact_apk_name_hash_and_size(self):
        name = "CarPaly-XingyueL-v1.1.51.apk"
        body = (APK_HASH + "  " + name + "\n").encode("ascii")
        self.assertTrue(ota_manifest.checksum_sidecar_matches(
            body, apk_name=name, expected_sha256=APK_HASH, expected_size=len(body),
        ))
        self.assertFalse(ota_manifest.checksum_sidecar_matches(
            body, apk_name=name, expected_sha256="b" * 64, expected_size=len(body),
        ))
        self.assertFalse(ota_manifest.checksum_sidecar_matches(
            body, apk_name="other.apk", expected_sha256=APK_HASH, expected_size=len(body),
        ))

    def test_required_ota_release_must_be_published_verified_and_merged_to_main(self):
        release, proof = make_release("1.1.51", 39)
        tags = make_tags((release, proof))
        args = {
            "releases": [release], "tags": tags, "ledger": self.ledger,
            "verifications": {release["tag_name"]: proof}, "policy": self.policy,
            "main_verified_tags": {release["tag_name"]},
            "verified_checksum_tags": {release["tag_name"]},
        }
        build_ota_manifests.validate_required_release_tag("v1.1.51", **args)
        for override, message in (
            ({"main_verified_tags": set()}, "not contained in current main"),
            ({"verified_checksum_tags": set()}, "checksum evidence"),
            ({"releases": [{**release, "draft": True}]}, "published GitHub Release"),
            ({"verifications": {}}, "checksum evidence"),
        ):
            with self.subTest(override=override), self.assertRaisesRegex(
                    ota_manifest.ManifestError, message):
                build_ota_manifests.validate_required_release_tag(
                    "v1.1.51", **{**args, **override},
                )

    def test_required_ota_release_rejects_invalid_tag(self):
        with self.assertRaisesRegex(ota_manifest.ManifestError, "semantic version"):
            build_ota_manifests.validate_required_release_tag(
                "latest", releases=[], tags=[], ledger=self.ledger, verifications={},
                policy=self.policy, main_verified_tags=set(), verified_checksum_tags=set(),
            )


if __name__ == "__main__":
    unittest.main()
