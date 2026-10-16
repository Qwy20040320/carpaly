from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import artifact_delivery


SIGNER = "d9b329525fc1ef21c365fab72c10367527cc038297c4f30eaa22b2207429139e"
VERSION_NAME = "9.9.9"
VERSION_CODE = 999
APK_NAME = f"CarPaly-XingyueL-v{VERSION_NAME}.apk"


def run_git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return result.stdout.strip()


class ArtifactDeliveryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="carpaly artifact delivery ")
        self.base = Path(self.temp.name)
        self.primary = self.base / "primary checkout"
        self.primary.mkdir()
        self._create_project(self.primary)
        self.source_dir = self.base / "build staging" / f"v{VERSION_NAME}"
        self.source_dir.mkdir(parents=True)
        self.apk_bytes = b"synthetic-release-apk-test-fixture"
        self.apk_hash = hashlib.sha256(self.apk_bytes).hexdigest()
        (self.source_dir / APK_NAME).write_bytes(self.apk_bytes)
        (self.source_dir / f"{APK_NAME}.sha256").write_text(f"{self.apk_hash}  {APK_NAME}\n", encoding="ascii")
        (self.source_dir / "SHA256SUMS.txt").write_text(f"{self.apk_hash}  {APK_NAME}\n", encoding="ascii")
        (self.source_dir / f"{APK_NAME}.verification.json").write_text(
            json.dumps(self._proof(), indent=2), encoding="utf-8"
        )
        self.report = self.primary / "docs" / f"v{VERSION_NAME}" / "TEST_REPORT.md"
        self.report.parent.mkdir(parents=True)
        self.report.write_text("Synthetic public-safe report fixture.\n", encoding="utf-8")
        run_git(self.primary, "init", "--initial-branch=main")
        run_git(self.primary, "config", "user.name", "CarPaly Test")
        run_git(self.primary, "config", "user.email", "test@example.invalid")
        run_git(self.primary, "remote", "add", "origin", "https://github.com/Qwy20040320/carpaly.git")
        run_git(self.primary, "add", "settings.gradle.kts", "mobile/build.gradle.kts", "config", "docs", ".gitignore")
        run_git(self.primary, "commit", "-m", "fixture")
        self.linked = self.base / "linked feature worktree"
        run_git(self.primary, "worktree", "add", "--detach", str(self.linked), "HEAD")
        # Artifacts are ignored, so the linked worktree uses its own candidate staging directory.
        self.linked_source = self.linked / "artifacts" / f"v{VERSION_NAME}"
        self.linked_source.mkdir(parents=True)
        for source in self.source_dir.iterdir():
            if source.is_file():
                (self.linked_source / source.name).write_bytes(source.read_bytes())

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _create_project(self, root: Path) -> None:
        (root / "settings.gradle.kts").write_text("rootProject.name = \"CarPaly\"\n", encoding="utf-8")
        (root / "mobile").mkdir()
        (root / "mobile" / "build.gradle.kts").write_text("plugins {}\n", encoding="utf-8")
        (root / "config").mkdir()
        (root / ".gitignore").write_text("/artifacts/\n", encoding="utf-8")
        (root / "config" / "artifact-delivery.json").write_text(
            json.dumps(
                {
                    "schemaVersion": 1,
                    "repository": "Qwy20040320/carpaly",
                    "artifactRoot": "artifacts",
                    "versionDirectoryPattern": "v{versionName}",
                    "resolution": "primary-standard-worktree-from-git-common-dir",
                    "requireIgnored": True,
                    "copyReportsListedInPublicAllowlist": True,
                    "generatedReportName": "DELIVERY_REPORT.md",
                }
            ),
            encoding="utf-8",
        )
        (root / "config" / "public-markdown-allowlist.json").write_text(
            json.dumps({"publicMarkdown": [f"docs/v{VERSION_NAME}/TEST_REPORT.md"]}), encoding="utf-8"
        )
        ledger = {
            "applicationId": "com.shihab.diplay.hudtest",
            "releaseCertificateSha256": SIGNER,
            "deliveryPolicy": {
                "applicationId": "com.shihab.diplay.hudtest",
                "releaseCertificateSha256": SIGNER,
            },
            "signingEpochs": [
                {
                    "id": "test-epoch",
                    "minimumVersionCode": 900,
                    "maximumVersionCode": None,
                    "certificateSha256": SIGNER,
                }
            ],
            "current": {
                "versionName": VERSION_NAME,
                "versionCode": VERSION_CODE,
                "signingEpochId": "test-epoch",
            },
            "highestObservedVersionCode": VERSION_CODE,
            "allocations": [
                {
                    "versionName": VERSION_NAME,
                    "versionCode": VERSION_CODE,
                    "status": "delivered",
                    "signerCertificateSha256": SIGNER,
                    "artifactSha256": hashlib.sha256(b"synthetic-release-apk-test-fixture").hexdigest(),
                }
            ],
        }
        (root / "config" / "android-version-ledger.json").write_text(json.dumps(ledger), encoding="utf-8")

    def _proof(self, **overrides: object) -> dict[str, object]:
        value: dict[str, object] = {
            "status": "PASS",
            "apk": APK_NAME,
            "packageName": "com.shihab.diplay.hudtest",
            "versionName": VERSION_NAME,
            "versionCode": VERSION_CODE,
            "apkSha256": hashlib.sha256(b"synthetic-release-apk-test-fixture").hexdigest(),
            "signerCertificateSha256": SIGNER,
            "checks": {name: "PASS" for name in artifact_delivery.REQUIRED_VERIFIER_CHECKS},
        }
        value.update(overrides)
        return value

    def _deliver(self) -> dict[str, str]:
        return artifact_delivery.deliver(
            self.linked,
            self.linked_source,
            report_paths=[self.linked / "docs" / f"v{VERSION_NAME}" / "TEST_REPORT.md"],
        )

    def test_primary_standard_checkout_resolves_from_linked_worktree(self) -> None:
        self.assertEqual(self.primary, artifact_delivery.resolve_primary_root(self.linked))
        self.assertEqual(self.primary, artifact_delivery.resolve_primary_root(self.primary))

    def test_resolution_fails_closed_when_primary_is_not_discoverable(self) -> None:
        with patch.object(artifact_delivery, "_worktree_paths", return_value=[]):
            with self.assertRaisesRegex(artifact_delivery.DeliveryError, "exactly one primary"):
                artifact_delivery.resolve_primary_root(self.linked)

    def test_delivers_into_primary_version_folder_and_preserves_source(self) -> None:
        source_hash = artifact_delivery.sha256_file(self.linked_source / APK_NAME)
        result = self._deliver()
        delivered = self.primary / "artifacts" / f"v{VERSION_NAME}" / APK_NAME
        self.assertEqual(str(delivered), result["deliveryApk"])
        self.assertEqual(source_hash, artifact_delivery.sha256_file(delivered))
        self.assertEqual(source_hash, artifact_delivery.sha256_file(self.linked_source / APK_NAME))
        self.assertTrue((delivered.parent / "reports" / "TEST_REPORT.md").is_file())
        self.assertTrue((delivered.parent / "reports" / "DELIVERY_REPORT.md").is_file())

    def test_repeat_with_same_hash_is_idempotent(self) -> None:
        first = self._deliver()
        second = self._deliver()
        self.assertEqual(first["apkSha256"], second["apkSha256"])
        self.assertEqual((self.primary / "artifacts" / f"v{VERSION_NAME}" / APK_NAME).read_bytes(), self.apk_bytes)

    def test_versions_are_delivered_to_separate_folders_and_history_is_untouched(self) -> None:
        historical = self.primary / "artifacts" / "v9.9.8" / "CarPaly-XingyueL-v9.9.8.apk"
        historical.parent.mkdir(parents=True)
        historical_bytes = b"previous-delivered-version"
        historical.write_bytes(historical_bytes)

        first_result = self._deliver()
        second_name = "9.9.10"
        second_code = VERSION_CODE + 1
        second_bytes = b"second synthetic version candidate"
        second_hash = hashlib.sha256(second_bytes).hexdigest()
        second_dir = self.linked / "artifacts" / f"v{second_name}"
        second_dir.mkdir(parents=True)
        second_apk_name = f"CarPaly-XingyueL-v{second_name}.apk"
        (second_dir / second_apk_name).write_bytes(second_bytes)
        (second_dir / f"{second_apk_name}.sha256").write_text(f"{second_hash}  {second_apk_name}\n", encoding="ascii")
        (second_dir / "SHA256SUMS.txt").write_text(f"{second_hash}  {second_apk_name}\n", encoding="ascii")
        second_proof = self._proof(
            apk=second_apk_name,
            versionName=second_name,
            versionCode=second_code,
            apkSha256=second_hash,
        )
        (second_dir / f"{second_apk_name}.verification.json").write_text(json.dumps(second_proof), encoding="utf-8")

        ledger_path = self.linked / "config" / "android-version-ledger.json"
        ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
        ledger["current"].update(versionName=second_name, versionCode=second_code)
        ledger["highestObservedVersionCode"] = second_code
        ledger["allocations"].append(
            {
                "versionName": second_name,
                "versionCode": second_code,
                "status": "delivered",
                "signerCertificateSha256": SIGNER,
                "artifactSha256": second_hash,
            }
        )
        ledger_path.write_text(json.dumps(ledger), encoding="utf-8")

        result = artifact_delivery.deliver(self.linked, second_dir)
        self.assertEqual(f"v{VERSION_NAME}", Path(first_result["deliveryApk"]).parent.name)
        self.assertEqual(f"v{second_name}", Path(result["deliveryApk"]).parent.name)
        self.assertEqual(historical_bytes, historical.read_bytes())
        self.assertFalse((self.primary / "artifacts" / "v9.9.8" / second_apk_name).exists())

    def test_conflicting_same_name_file_is_never_overwritten(self) -> None:
        target = self.primary / "artifacts" / f"v{VERSION_NAME}"
        target.mkdir(parents=True)
        existing = target / APK_NAME
        existing.write_bytes(b"different historical bytes")
        with self.assertRaisesRegex(artifact_delivery.DeliveryError, "refusing to overwrite"):
            self._deliver()
        self.assertEqual(b"different historical bytes", existing.read_bytes())
        self.assertFalse((target / f"{APK_NAME}.sha256").exists())

    def test_missing_source_apk_fails_closed(self) -> None:
        (self.linked_source / APK_NAME).unlink()
        with self.assertRaises(artifact_delivery.DeliveryError):
            self._deliver()
        self.assertFalse((self.primary / "artifacts" / f"v{VERSION_NAME}").exists())

    def test_signer_mismatch_fails_closed(self) -> None:
        proof_path = self.linked_source / f"{APK_NAME}.verification.json"
        proof = self._proof(signerCertificateSha256="0" * 64)
        proof_path.write_text(json.dumps(proof), encoding="utf-8")
        with self.assertRaisesRegex(artifact_delivery.DeliveryError, "canonical Release verifier"):
            self._deliver()

    def test_wrong_version_fails_closed(self) -> None:
        proof_path = self.linked_source / f"{APK_NAME}.verification.json"
        proof_path.write_text(json.dumps(self._proof(versionCode=VERSION_CODE - 1)), encoding="utf-8")
        with self.assertRaisesRegex(artifact_delivery.DeliveryError, "canonical Release verifier"):
            self._deliver()

    def test_wrong_hash_in_checksum_fails_closed(self) -> None:
        (self.linked_source / "SHA256SUMS.txt").write_text(f"{'0' * 64}  {APK_NAME}\n", encoding="ascii")
        with self.assertRaisesRegex(artifact_delivery.DeliveryError, "SHA256SUMS"):
            self._deliver()

    def test_unallowlisted_report_fails_closed(self) -> None:
        private_note = self.linked / "private-note.md"
        private_note.write_text("must not copy\n", encoding="utf-8")
        with self.assertRaisesRegex(artifact_delivery.DeliveryError, "allowlist"):
            artifact_delivery.deliver(self.linked, self.linked_source, report_paths=[private_note])

    def test_reparse_destination_is_rejected(self) -> None:
        artifacts_root = self.primary / "artifacts"
        with patch.object(
            artifact_delivery,
            "is_reparse_path",
            side_effect=lambda path: os.path.normcase(os.path.abspath(path))
            == os.path.normcase(os.path.abspath(artifacts_root)),
        ):
            with self.assertRaisesRegex(artifact_delivery.DeliveryError, "reparse-point"):
                self._deliver()

    def test_non_ignored_primary_destination_is_rejected(self) -> None:
        (self.primary / ".gitignore").write_text("", encoding="utf-8")
        with self.assertRaisesRegex(artifact_delivery.DeliveryError, "not ignored by Git"):
            self._deliver()

    def test_tracked_destination_apk_is_rejected_even_if_ignore_rule_matches(self) -> None:
        tracked = self.primary / "artifacts" / f"v{VERSION_NAME}" / APK_NAME
        tracked.parent.mkdir(parents=True)
        tracked.write_bytes(self.apk_bytes)
        run_git(self.primary, "add", "-f", str(tracked.relative_to(self.primary)))
        run_git(self.primary, "commit", "-m", "test tracked artifact guard")
        with self.assertRaisesRegex(artifact_delivery.DeliveryError, "tracked by Git"):
            self._deliver()
        self.assertEqual(self.apk_bytes, tracked.read_bytes())

    def test_invalid_explicit_primary_root_is_rejected(self) -> None:
        unrelated = self.base / "unrelated"
        unrelated.mkdir()
        with self.assertRaises(artifact_delivery.DeliveryError):
            artifact_delivery.resolve_primary_root(self.linked, unrelated)


if __name__ == "__main__":
    unittest.main()
