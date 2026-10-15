from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.ci_rebuild import (
    PolicyError,
    check_signer_pin,
    find_entry,
    load_manifest,
    parse_source_metadata,
    resolve_version,
    verify_tag_intent,
)


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "config/ci-rebuild-sources.json"
D9 = "d9b329525fc1ef21c365fab72c10367527cc038297c4f30eaa22b2207429139e"
D4 = "4d26d1c861b41a2cee4515e31f5f5c7eb13b9dd06e7485aa1687bc1d2ac73d90"


def sample_entry() -> dict[str, object]:
    return {
        "versionName": "1.1.54",
        "versionCode": 42,
        "sourceStatus": "verified",
        "sourceCommit": "e3eca1dc5145cd293815d8f176d5c3812169271a",
        "originalApkFileName": "CarPaly-XingyueL-v1.1.54.apk",
        "originalApkSha256": "f244fff2765881b7f7a1b66b1ed44202ca3356730e11636b210b5267da514d3c",
        "signerCertificateSha256": D9,
        "distributionStatus": "blocked-auth-private-key-in-apk",
    }


class CiRebuildManifestTests(unittest.TestCase):
    def assertPolicyCode(self, code: str, operation: object) -> None:
        with self.assertRaises(PolicyError) as caught:
            operation()  # type: ignore[operator]
        self.assertEqual(code, caught.exception.code)

    def test_reviewed_source_map_loads_with_only_two_pinned_sources(self) -> None:
        manifest = load_manifest(MANIFEST)
        self.assertEqual(["1.1.54", "1.1.55", "1.1.56"], [row["versionName"] for row in manifest["versions"]])
        self.assertEqual(2, sum(row["sourceStatus"] == "verified" for row in manifest["versions"]))

    def test_v1155_fails_closed_without_a_source_commit(self) -> None:
        manifest = load_manifest(MANIFEST)
        self.assertPolicyCode("SOURCE_UNVERIFIED", lambda: resolve_version(
                manifest,
                "1.1.55",
                event_name="workflow_dispatch",
                ref="refs/heads/main",
                current_commit="64703e7dced85b81963a85b8b3ff12a7efc56448",
                build_type="release",
            ))

    def test_v1154_dispatch_resolves_to_exact_historical_commit(self) -> None:
        manifest = load_manifest(MANIFEST)
        entry, commit = resolve_version(
            manifest,
            "v1.1.54",
            event_name="workflow_dispatch",
            ref="refs/heads/main",
            current_commit="64703e7dced85b81963a85b8b3ff12a7efc56448",
            build_type="release",
        )
        self.assertEqual("1.1.54", entry["versionName"])
        self.assertEqual("e3eca1dc5145cd293815d8f176d5c3812169271a", commit)

    def test_tag_must_point_at_mapped_source(self) -> None:
        manifest = load_manifest(MANIFEST)
        self.assertPolicyCode("TAG_SOURCE_MISMATCH", lambda: resolve_version(
                manifest,
                "1.1.54",
                event_name="push",
                ref="refs/tags/v1.1.54",
                current_commit="",
                tag_name="v1.1.54",
                tag_sha="6b206c9e6944255a159424522017dca984423e67",
            ))

    def test_signed_dispatch_is_limited_to_main(self) -> None:
        manifest = load_manifest(MANIFEST)
        self.assertPolicyCode("RELEASE_REF_NOT_MAIN", lambda: resolve_version(
                manifest,
                "1.1.54",
                event_name="workflow_dispatch",
                ref="refs/heads/codex/test",
                current_commit="e3eca1dc5145cd293815d8f176d5c3812169271a",
                build_type="release",
            ))

    def test_tag_bound_future_build_uses_only_exact_tag_commit(self) -> None:
        entry = sample_entry()
        entry["sourceStatus"] = "tag-bound"
        entry["sourceCommit"] = None
        manifest = {"versions": [entry]}
        _, source = resolve_version(
            manifest,
            "1.1.54",
            event_name="push",
            ref="refs/tags/v1.1.54",
            current_commit="",
            tag_name="v1.1.54",
            tag_sha="e3eca1dc5145cd293815d8f176d5c3812169271a",
        )
        self.assertEqual(entry["sourceCommit"] or "e3eca1dc5145cd293815d8f176d5c3812169271a", source)

    def test_source_metadata_must_match_gradle_ledger_and_manifest(self) -> None:
        entry = sample_entry()
        gradle = f'''val CARPALY_RELEASE_CERT_SHA256 =\n    "{D9}"
android {{ defaultConfig {{ applicationId = "com.shihab.diplay.hudtest"; versionCode = 42; versionName = "1.1.54" }} }}
'''
        ledger = {
            "applicationId": "com.shihab.diplay.hudtest",
            "releaseCertificateSha256": D9,
            "allocations": [{"versionName": "1.1.54", "versionCode": 42, "signerCertificateSha256": D9}],
        }
        parse_source_metadata(gradle, ledger, entry)
        self.assertPolicyCode(
            "VERSION_MISMATCH",
            lambda: parse_source_metadata(gradle.replace("versionCode = 42", "versionCode = 41"), ledger, entry),
        )

    def test_source_signer_conflict_is_rejected(self) -> None:
        entry = sample_entry()
        gradle = f'''val CARPALY_RELEASE_CERT_SHA256 = "{D9}"
applicationId = "com.shihab.diplay.hudtest"
versionCode = 42
versionName = "1.1.54"
'''
        ledger = {
            "applicationId": "com.shihab.diplay.hudtest",
            "releaseCertificateSha256": D4,
            "allocations": [{"versionName": "1.1.54", "versionCode": 42, "signerCertificateSha256": D9}],
        }
        self.assertPolicyCode("SIGNER_POLICY_MISMATCH", lambda: parse_source_metadata(gradle, ledger, entry))

    def test_environment_fingerprint_normalization_and_mismatch(self) -> None:
        check_signer_pin(D9, D9.upper())
        check_signer_pin(D9, ":".join(D9[index : index + 2] for index in range(0, 64, 2)))
        self.assertPolicyCode("ENVIRONMENT_SIGNER_MISMATCH", lambda: check_signer_pin(D9, D4))
        self.assertPolicyCode("FINGERPRINT_INVALID", lambda: check_signer_pin(D9, "x" + D9[1:]))

    def test_tag_release_requires_enabled_exact_intent_and_main_commit(self) -> None:
        entry = sample_entry()
        sha = "e3eca1dc5145cd293815d8f176d5c3812169271a"
        verify_tag_intent(
            entry,
            tag_name="v1.1.54",
            tag_sha=sha,
            main_sha=sha,
            intent={"enabled": True, "versionName": "1.1.54", "versionCode": 42},
        )
        for intent in (
            {"enabled": False, "versionName": "1.1.54", "versionCode": 42},
            {"enabled": True, "versionName": "1.1.56", "versionCode": 42},
        ):
            with self.assertRaises(PolicyError):
                verify_tag_intent(entry, tag_name="v1.1.54", tag_sha=sha, main_sha=sha, intent=intent)
        self.assertPolicyCode("TAG_NOT_EXACT_MAIN", lambda: verify_tag_intent(
                entry,
                tag_name="v1.1.54",
                tag_sha=sha,
                main_sha="6b206c9e6944255a159424522017dca984423e67",
                intent={"enabled": True, "versionName": "1.1.54", "versionCode": 42},
            ))

    def test_duplicate_version_codes_and_malformed_hashes_are_rejected(self) -> None:
        document = json.loads(MANIFEST.read_text(encoding="utf-8"))
        document["versions"][1]["versionCode"] = 42
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "manifest.json"
            path.write_text(json.dumps(document), encoding="utf-8")
            self.assertPolicyCode("MANIFEST_INVALID", lambda: load_manifest(path))

        document = json.loads(MANIFEST.read_text(encoding="utf-8"))
        document["versions"][0]["originalApkSha256"] = "not-a-sha"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "manifest.json"
            path.write_text(json.dumps(document), encoding="utf-8")
            self.assertPolicyCode("MANIFEST_INVALID", lambda: load_manifest(path))


if __name__ == "__main__":
    unittest.main()
