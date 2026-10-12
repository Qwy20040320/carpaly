from __future__ import annotations

import base64
import unittest

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

from scripts.export_ota_public_key import public_key_record


class OtaPublicKeyExportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.key = ec.generate_private_key(ec.SECP256R1())
        self.pem = self.key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )

    def test_exports_only_expected_x509_public_record(self) -> None:
        record = public_key_record(self.pem, "synthetic-test-key")
        self.assertEqual(
            {"keyId", "algorithm", "status", "publicKeyX509Base64"}, set(record)
        )
        self.assertEqual("SHA256withECDSA-P256", record["algorithm"])
        public_key = serialization.load_der_public_key(
            base64.b64decode(record["publicKeyX509Base64"], validate=True)
        )
        self.assertEqual(self.key.public_key().public_numbers(), public_key.public_numbers())
        self.assertNotIn("private", " ".join(record).lower())

    def test_rejects_wrong_curve_and_bad_key_id(self) -> None:
        wrong_curve = ec.generate_private_key(ec.SECP384R1()).private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
        with self.assertRaisesRegex(ValueError, "P-256"):
            public_key_record(wrong_curve, "synthetic-test-key")
        with self.assertRaisesRegex(ValueError, "key id"):
            public_key_record(self.pem, "invalid key id")


if __name__ == "__main__":
    unittest.main()
