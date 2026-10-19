"""Credential-free tests for version-code-specific Release signer pinning."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from scripts import check_release_signer_pin as checker
from scripts.release_signing_policy import CURRENT_RELEASE_CERT_SHA256, LEGACY_RELEASE_CERT_SHA256


DEBUG = "0" * 64


def make_policy() -> dict:
    allocations = [
        {
            "versionName": name,
            "versionCode": code,
            "signerCertificateSha256": signer,
            "signingEpochId": epoch,
        }
        for name, code, signer, epoch in (
            ("1.1.52", 40, LEGACY_RELEASE_CERT_SHA256, "legacy-v1.1.4-through-v1.1.52"),
            ("1.1.53", 41, CURRENT_RELEASE_CERT_SHA256, "fresh-install-v1.1.53-plus"),
            ("1.1.56", 44, CURRENT_RELEASE_CERT_SHA256, "fresh-install-v1.1.53-plus"),
            ("1.1.57", 45, CURRENT_RELEASE_CERT_SHA256, "fresh-install-v1.1.53-plus"),
        )
    ]
    return {
        "applicationId": "com.shihab.diplay.hudtest",
        "releaseCertificateSha256": CURRENT_RELEASE_CERT_SHA256,
        "legacyReleaseCertificateSha256": LEGACY_RELEASE_CERT_SHA256,
        "signingEpochs": [
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
        ],
        "current": {
            "versionName": "1.1.57",
            "versionCode": 45,
            "channel": "test",
            "signingEpochId": "fresh-install-v1.1.53-plus",
        },
        "allocations": allocations,
        "verifiedHistoricalDeliveries": [],
        "deliveryPolicy": {"releaseCertificateSha256": CURRENT_RELEASE_CERT_SHA256},
    }


class ReleaseSignerPinTests(unittest.TestCase):
    def write_policy(self, root: Path, policy: dict | None = None) -> Path:
        path = root / "ledger.json"
        path.write_text(json.dumps(policy or make_policy()), encoding="utf-8")
        return path

    def test_current_code45_pin_passes_with_hex_case_and_colon_normalization(self):
        with tempfile.TemporaryDirectory() as folder:
            path = self.write_policy(Path(folder))
            value = ":".join(CURRENT_RELEASE_CERT_SHA256[i:i + 2] for i in range(0, 64, 2)).upper()
            self.assertEqual(CURRENT_RELEASE_CERT_SHA256, checker.check(path, value))

    def test_code40_uses_legacy_signer_and_code41_44_45_use_d9_epoch(self):
        with tempfile.TemporaryDirectory() as folder:
            path = self.write_policy(Path(folder))
            for name, code, signer in (
                ("1.1.52", 40, LEGACY_RELEASE_CERT_SHA256),
                ("1.1.53", 41, CURRENT_RELEASE_CERT_SHA256),
                ("1.1.56", 44, CURRENT_RELEASE_CERT_SHA256),
                ("1.1.57", 45, CURRENT_RELEASE_CERT_SHA256),
            ):
                with self.subTest(code=code):
                    self.assertEqual(
                        signer,
                        checker.check(path, signer, version_name=name, version_code=code),
                    )

    def test_code45_rejects_legacy_debug_and_unknown_signers(self):
        with tempfile.TemporaryDirectory() as folder:
            path = self.write_policy(Path(folder))
            for bad_signer in (LEGACY_RELEASE_CERT_SHA256, DEBUG, "a" * 64):
                with self.subTest(signer_class=bad_signer[:2]), self.assertRaisesRegex(
                    checker.SignerPinError, "versionCode 45"
                ):
                    checker.check(path, bad_signer)

    def test_missing_signer_evidence_fails_closed(self):
        policy = make_policy()
        policy["allocations"] = [item for item in policy["allocations"] if item["versionCode"] != 45]
        with tempfile.TemporaryDirectory() as folder:
            path = self.write_policy(Path(folder), policy)
            with self.assertRaisesRegex(checker.SignerPinError, "no matching approved signing-epoch evidence"):
                checker.check(path, CURRENT_RELEASE_CERT_SHA256)

    def test_epoch_or_record_tampering_fails_closed(self):
        cases = []
        changed_epoch = make_policy()
        changed_epoch["signingEpochs"][1]["certificateSha256"] = DEBUG
        cases.append(changed_epoch)
        changed_record = make_policy()
        changed_record["allocations"][-1]["signerCertificateSha256"] = LEGACY_RELEASE_CERT_SHA256
        cases.append(changed_record)
        for policy in cases:
            with tempfile.TemporaryDirectory() as folder:
                path = self.write_policy(Path(folder), policy)
                with self.assertRaises(checker.SignerPinError):
                    checker.check(path, CURRENT_RELEASE_CERT_SHA256)

    def test_active_signer_fields_must_match_current_epoch(self):
        policy = make_policy()
        policy["deliveryPolicy"]["releaseCertificateSha256"] = LEGACY_RELEASE_CERT_SHA256
        with tempfile.TemporaryDirectory() as folder:
            path = self.write_policy(Path(folder), policy)
            with self.assertRaisesRegex(checker.SignerPinError, "active signer fields conflict"):
                checker.check(path, CURRENT_RELEASE_CERT_SHA256)

    def test_missing_or_malformed_environment_pin_fails(self):
        with tempfile.TemporaryDirectory() as folder:
            path = self.write_policy(Path(folder))
            for value in ("", "not-a-digest", "a" * 63):
                with self.subTest(value=value), self.assertRaises(checker.SignerPinError):
                    checker.check(path, value)

    def test_explicit_signer_check_requires_both_version_fields(self):
        with tempfile.TemporaryDirectory() as folder:
            path = self.write_policy(Path(folder))
            with self.assertRaisesRegex(checker.SignerPinError, "Both version name and version code"):
                checker.check(path, LEGACY_RELEASE_CERT_SHA256, version_code=40)


if __name__ == "__main__":
    unittest.main(verbosity=2)
