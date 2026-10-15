"""Unit tests for credential-free signer pin validation."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from scripts import check_release_signer_pin as checker


FINGERPRINT = "4d26d1c861b41a2cee4515e31f5f5c7eb13b9dd06e7485aa1687bc1d2ac73d90"


class ReleaseSignerPinTests(unittest.TestCase):
    def write_policy(self, root: Path, *, ledger: str = FINGERPRINT, delivery: str = FINGERPRINT) -> Path:
        path = root / "ledger.json"
        path.write_text(json.dumps({
            "releaseCertificateSha256": ledger,
            "deliveryPolicy": {"releaseCertificateSha256": delivery},
        }), encoding="utf-8")
        return path

    def test_matching_pin_passes_with_hex_case_and_colon_normalization(self):
        with tempfile.TemporaryDirectory() as folder:
            path = self.write_policy(Path(folder))
            self.assertEqual(checker.check(path, ":".join(FINGERPRINT[i:i + 2] for i in range(0, 64, 2)).upper()), FINGERPRINT)

    def test_environment_mismatch_fails_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            path = self.write_policy(Path(folder))
            with self.assertRaisesRegex(checker.SignerPinError, "before any credential use"):
                checker.check(path, "d9b329525fc1ef21c365fab72c10367527cc038297c4f30eaa22b2207429139e")

    def test_conflicting_ledger_fields_fail_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            path = self.write_policy(Path(folder), delivery="d9b329525fc1ef21c365fab72c10367527cc038297c4f30eaa22b2207429139e")
            with self.assertRaisesRegex(checker.SignerPinError, "Ledger signer policy fields conflict"):
                checker.check(path, FINGERPRINT)

    def test_missing_or_malformed_environment_pin_fails_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            path = self.write_policy(Path(folder))
            for value in ("", "not-a-digest", "a" * 63):
                with self.subTest(value=value), self.assertRaises(checker.SignerPinError):
                    checker.check(path, value)


if __name__ == "__main__":
    unittest.main(verbosity=2)
