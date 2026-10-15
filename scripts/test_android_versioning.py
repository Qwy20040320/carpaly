import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.android_versioning import (
    allocate,
    check_project,
    check_ci_project,
    historical_versions,
    next_test_name,
    parse_gradle_version,
    parse_version_tuple,
    require_current_delivery_recorded,
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

    def test_repository_reservation_matches_project_version(self):
        root = Path(__file__).resolve().parents[1]
        version = check_ci_project(root)
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
        self.assertEqual("delivered", allocation["status"])
        self.assertRegex(allocation["artifactSha256"], r"^[a-f0-9]{64}$")
        history = {
            item["tag"]: (item["versionName"], item["versionCode"])
            for item in ledger["verifiedHistoricalDeliveries"]
        }
        self.assertEqual(("1.1.4", 36), history["v1.1.4"])
        self.assertEqual(("1.1.5", 37), history["v1.1.5"])

    def test_release_check_enforces_high_water_but_ci_check_accepts_existing_baseline(self):
        root = Path(__file__).resolve().parents[1]
        version = check_ci_project(root)
        previous = historical_versions(root, version)
        highest_previous = max((item.version_code for item in previous), default=0)
        if version.version_code <= highest_previous:
            with self.assertRaisesRegex(ValueError, "must exceed all previous known values"):
                check_project(root)
        else:
            self.assertEqual(version, check_project(root))

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
            ledger["highestObservedVersionCode"] = 38
            ledger["verifiedHistoricalDeliveries"] = [
                item for item in ledger["verifiedHistoricalDeliveries"] if item["versionCode"] <= 38
            ]
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
