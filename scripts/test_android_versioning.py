import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.android_versioning import (
    allocate,
    check_project,
    next_test_name,
    parse_gradle_version,
    parse_version_tuple,
    require_current_delivery_recorded,
    signer_for_version,
    validate_ledger,
)


class AndroidVersioningTests(unittest.TestCase):
    def test_reads_one_base_application_and_version(self):
        parsed = parse_gradle_version(
            'defaultConfig {\n'
            '    applicationId = "com.shihab.diplay.hudtest"\n'
            '    versionCode = 39\n'
            '    versionName = "1.1.51"\n'
            '}\n'
        )
        self.assertEqual("com.shihab.diplay.hudtest", parsed.application_id)
        self.assertEqual("1.1.51", parsed.version_name)
        self.assertEqual(39, parsed.version_code)

    def test_test_versions_increment_without_reusing_the_previous_name(self):
        self.assertEqual("1.1.52", next_test_name("1.1.51"))
        self.assertEqual("1.1.100", next_test_name("1.1.99"))

    def test_next_test_requires_the_test_sequence(self):
        for version in ("1.1.5", "1.1.6", "1.2.51", "not-a-version"):
            with self.subTest(version=version), self.assertRaises(ValueError):
                next_test_name(version)

    def test_numeric_version_parser(self):
        self.assertEqual((1, 1, 51), parse_version_tuple("1.1.51"))
        self.assertIsNone(parse_version_tuple("v1.1.51"))

    def test_repository_reservation_matches_monotonic_project_version(self):
        root = Path(__file__).resolve().parents[1]
        version = check_project(root)
        ledger = json.loads((root / "config/android-version-ledger.json").read_text(encoding="utf-8"))
        current = ledger["current"]
        self.assertEqual(current["versionName"], version.version_name)
        self.assertEqual(current["versionCode"], version.version_code)
        self.assertEqual("com.shihab.diplay.hudtest", version.application_id)
        allocation = next(
            item
            for item in ledger["allocations"]
            if item["versionName"] == version.version_name
            and item["versionCode"] == version.version_code
            and item["channel"] == current["channel"]
        )
        if allocation["status"] == "reserved":
            self.assertIsNone(allocation["artifactSha256"])
        else:
            self.assertEqual("delivered", allocation["status"])
            self.assertRegex(allocation["artifactSha256"], r"^[a-f0-9]{64}$")
        history = {
            item["tag"]: (item["versionName"], item["versionCode"])
            for item in ledger["verifiedHistoricalDeliveries"]
        }
        self.assertEqual(("1.1.4", 36), history["v1.1.4"])
        self.assertEqual(("1.1.5", 37), history["v1.1.5"])

    def test_signing_epochs_keep_legacy_apks_immutable_and_mark_new_epoch_fresh_install_only(self):
        ledger = json.loads((Path(__file__).resolve().parents[1] / "config/android-version-ledger.json")
                            .read_text(encoding="utf-8"))
        legacy = ledger["legacyReleaseCertificateSha256"]
        current = ledger["releaseCertificateSha256"]
        self.assertEqual(legacy, signer_for_version(ledger, "1.1.52", 40))
        self.assertEqual(current, signer_for_version(ledger, "1.1.53", 41))
        self.assertIsNone(signer_for_version(ledger, "1.1.54", 42))
        current_allocation = next(item for item in ledger["allocations"] if item["versionName"] == "1.1.53")
        self.assertEqual("fresh-install-required", current_allocation["upgradePolicy"])
        validate_ledger(ledger)

    def test_signing_epoch_mismatch_fails_closed(self):
        ledger = json.loads((Path(__file__).resolve().parents[1] / "config/android-version-ledger.json")
                            .read_text(encoding="utf-8"))
        ledger["allocations"][-1]["signerCertificateSha256"] = ledger["legacyReleaseCertificateSha256"]
        with self.assertRaisesRegex(ValueError, "inconsistent signer epoch"):
            validate_ledger(ledger)

    def test_overlapping_signing_epochs_fail_closed(self):
        ledger = json.loads((Path(__file__).resolve().parents[1] / "config/android-version-ledger.json")
                            .read_text(encoding="utf-8"))
        ledger["signingEpochs"][0]["maximumVersionCode"] = 41
        with self.assertRaisesRegex(ValueError, "overlap"):
            validate_ledger(ledger)

    def test_next_version_is_blocked_until_current_release_artifact_is_recorded(self):
        ledger = {
            "current": {"versionName": "1.1.51", "versionCode": 39, "channel": "test"},
            "allocations": [
                {
                    "versionName": "1.1.51",
                    "versionCode": 39,
                    "channel": "test",
                    "status": "reserved",
                    "artifactSha256": None,
                }
            ],
        }
        with self.assertRaisesRegex(ValueError, "verified Release APK delivery SHA-256"):
            require_current_delivery_recorded(ledger)

    def test_next_version_requires_a_sha256_record_for_the_delivered_release(self):
        ledger = {
            "current": {"versionName": "1.1.51", "versionCode": 39, "channel": "test"},
            "allocations": [
                {
                    "versionName": "1.1.51",
                    "versionCode": 39,
                    "channel": "test",
                    "status": "delivered",
                    "artifactSha256": "a" * 64,
                }
            ],
        }
        require_current_delivery_recorded(ledger)

    def test_allocator_does_not_advance_reserved_release_version(self):
        project = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(prefix="carpaly-version-reservation-") as temporary:
            root = Path(temporary)
            gradle_path = root / "mobile/build.gradle.kts"
            ledger_path = root / "config/android-version-ledger.json"
            gradle_path.parent.mkdir(parents=True)
            ledger_path.parent.mkdir(parents=True)
            shutil.copyfile(project / gradle_path.relative_to(root), gradle_path)

            ledger = json.loads((project / ledger_path.relative_to(root)).read_text(encoding="utf-8"))
            current = ledger["current"]
            allocation = next(
                item
                for item in ledger["allocations"]
                if item["versionName"] == current["versionName"]
                and item["versionCode"] == current["versionCode"]
                and item["channel"] == current["channel"]
            )
            allocation["status"] = "reserved"
            allocation["artifactSha256"] = None
            ledger_path.write_text(json.dumps(ledger, indent=2) + "\n", encoding="utf-8")

            subprocess.run(["git", "init", "--quiet"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.name", "CarPaly Test"], cwd=root, check=True)
            subprocess.run(
                ["git", "config", "user.email", "carpaly-test@example.invalid"],
                cwd=root,
                check=True,
            )
            subprocess.run(
                ["git", "add", "mobile/build.gradle.kts", "config/android-version-ledger.json"],
                cwd=root,
                check=True,
            )
            subprocess.run(["git", "commit", "--quiet", "-m", "fixture"], cwd=root, check=True)

            before_gradle = gradle_path.read_bytes()
            before_ledger = ledger_path.read_bytes()
            with self.assertRaisesRegex(ValueError, "verified Release APK delivery SHA-256"):
                allocate(root, "test")
            self.assertEqual(before_gradle, gradle_path.read_bytes())
            self.assertEqual(before_ledger, ledger_path.read_bytes())


if __name__ == "__main__":
    unittest.main()
