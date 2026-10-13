from __future__ import annotations

import base64
import unittest

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

from scripts.ota_publisher_policy import PublisherPolicyError, validate_readiness


def trust_for(curve: ec.EllipticCurve):
    key = ec.generate_private_key(curve)
    der = key.public_key().public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
    return {"schemaVersion": 1, "keys": [{
        "keyId": "production-candidate",
        "algorithm": "SHA256withECDSA-P256",
        "status": "active",
        "publicKeyX509Base64": base64.b64encode(der).decode("ascii"),
    }]}


READY_POLICY = {
    "schemaVersion": 1,
    "productionEnabled": True,
    "environment": "ota-manifest-publisher",
    "environmentConfigurationReviewed": True,
    "allowedBranch": "main",
    "minimumRequiredReviewers": 1,
    "keyId": "production-candidate",
}


class OtaPublisherPolicyTests(unittest.TestCase):
    def test_disabled_baseline_fails_closed(self):
        policy = {**READY_POLICY, "productionEnabled": False}
        with self.assertRaisesRegex(PublisherPolicyError, "explicitly disabled"):
            validate_readiness(policy, {"schemaVersion": 1, "keys": []})

    def test_unreviewed_environment_missing_trust_or_missing_reviewer_fails(self):
        valid_trust = trust_for(ec.SECP256R1())
        for policy in (
            {**READY_POLICY, "environmentConfigurationReviewed": False},
            {**READY_POLICY, "minimumRequiredReviewers": 0},
            {**READY_POLICY, "environment": "mfi-public-release"},
            {**READY_POLICY, "allowedBranch": "feature"},
            {**READY_POLICY, "keyId": "missing"},
        ):
            with self.subTest(policy=policy), self.assertRaises(PublisherPolicyError):
                validate_readiness(policy, valid_trust)

    def test_only_active_x509_p256_key_passes(self):
        self.assertEqual(validate_readiness(READY_POLICY, trust_for(ec.SECP256R1())), "production-candidate")
        with self.assertRaisesRegex(PublisherPolicyError, "P-256"):
            validate_readiness(READY_POLICY, trust_for(ec.SECP384R1()))
        p384 = trust_for(ec.SECP384R1())
        with self.assertRaisesRegex(PublisherPolicyError, "active app-pinned"):
            validate_readiness(READY_POLICY, {"schemaVersion": 1, "keys": [
                {**p384["keys"][0], "status": "revoked"},
            ]})

    def test_duplicate_key_ids_fail_closed(self):
        trust = trust_for(ec.SECP256R1())
        trust["keys"].append(dict(trust["keys"][0]))
        with self.assertRaisesRegex(PublisherPolicyError, "one active"):
            validate_readiness(READY_POLICY, trust)


if __name__ == "__main__":
    unittest.main(verbosity=2)
