from __future__ import annotations

import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from scripts.verify_ci_rebuild_apk import VerificationError, verify


SIGNER = "d9b329525fc1ef21c365fab72c10367527cc038297c4f30eaa22b2207429139e"


class VerifyCiRebuildApkTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.apk = self.root / "mobile/build/outputs/apk/release/mobile-release.apk"
        self.apk.parent.mkdir(parents=True)
        self.report = self.root / "build-report/rebuild.json"
        self.args = SimpleNamespace(
            apk=self.apk,
            apksigner=Path("apksigner"),
            aapt=Path("aapt"),
            report=self.report,
            version_name="1.1.54",
            version_code=42,
            package="com.shihab.diplay.hudtest",
            expected_signer=SIGNER,
            source_commit="e3eca1dc5145cd293815d8f176d5c3812169271a",
            original_apk_sha256="f" * 64,
            output_name="CarPaly-XingyueL-v1.1.54.apk",
        )
        self.signer_output = "Signer #1 certificate SHA-256 digest: " + SIGNER
        self.badging = (
            "package: name='com.shihab.diplay.hudtest' versionCode='42' versionName='1.1.54'\n"
            "application-label:'CarPaly'\n"
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def write_apk(self, *, include_auth: bool = True) -> None:
        with zipfile.ZipFile(self.apk, "w") as archive:
            archive.writestr("AndroidManifest.xml", b"stub manifest")
            if include_auth:
                archive.writestr("assets/offline-mfi/identity.pk8", b"test-only placeholder")
                archive.writestr("assets/offline-mfi/certificate.p7b", b"test-only placeholder")

    def mock_tools(self, *, signer_output: str | None = None, badging: str | None = None):
        def result(command: list[str]) -> str:
            if command[0] == "apksigner":
                return (signer_output if signer_output is not None else self.signer_output) + "\n"
            return (badging if badging is not None else self.badging) + "\n"

        return patch("scripts.verify_ci_rebuild_apk.run_tool", side_effect=result)

    def test_valid_release_is_reported_but_never_distributable(self) -> None:
        self.write_apk()
        with self.mock_tools():
            report = verify(self.args)
        self.assertEqual("PASS", report["buildResult"])
        self.assertEqual("DISTRIBUTION_BLOCKED", report["distributionStatus"])
        self.assertFalse(report["apkUploaded"])
        self.assertFalse(report["releaseCreated"])
        self.assertFalse(report["otaEnabled"])
        self.assertEqual(report, json.loads(self.report.read_text(encoding="utf-8")))

    def test_missing_runtime_auth_assets_fails_closed(self) -> None:
        self.write_apk(include_auth=False)
        with self.assertRaisesRegex(VerificationError, "required authenticated runtime assets"):
            verify(self.args)

    def test_signer_mismatch_fails_closed(self) -> None:
        self.write_apk()
        with self.mock_tools(signer_output="Signer #1 certificate SHA-256 digest: " + "a" * 64):
            with self.assertRaisesRegex(VerificationError, "signer differs"):
                verify(self.args)

    def test_wrong_package_or_version_fails_closed(self) -> None:
        self.write_apk()
        with self.mock_tools(badging=self.badging.replace("versionCode='42'", "versionCode='41'")):
            with self.assertRaisesRegex(VerificationError, "package or version"):
                verify(self.args)

    def test_debuggable_release_fails_closed(self) -> None:
        self.write_apk()
        with self.mock_tools(badging=self.badging + "application-debuggable\n"):
            with self.assertRaisesRegex(VerificationError, "marked debuggable"):
                verify(self.args)


if __name__ == "__main__":
    unittest.main()
