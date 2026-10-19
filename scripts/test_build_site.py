from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts import build_ota_manifests, build_site
from scripts.android_versioning import signer_for_version


class SiteGenerationTests(unittest.TestCase):
    def release(self, *, tag: str, prerelease: bool, verified: bool = True) -> dict:
        record = {
            "tag": tag,
            "title": f"CarPaly {tag}",
            "publishedDate": "2026-10-11",
            "prerelease": prerelease,
            "draft": False,
            "htmlUrl": f"https://github.com/Qwy20040320/carpaly/releases/tag/{tag}",
            "apkVerificationStatus": "PASS" if verified else "NOT_VERIFIED",
            "releaseNoteStateConflict": False,
            "verifiedApk": None,
        }
        if verified:
            version = tag.removeprefix("v")
            record["verifiedApk"] = {
                "name": f"CarPaly-XingyueL-v{version}.apk",
                "url": f"https://github.com/Qwy20040320/carpaly/releases/download/{tag}/CarPaly-XingyueL-v{version}.apk",
                "size": 16_000_000,
                "sha256": "a" * 64,
                "versionName": version,
                "versionCode": 41 if version == "1.1.53" else 40,
                "signerSha256": signer_for_version(
                    build_site.read_json(build_site.LEDGER_PATH), version,
                    41 if version == "1.1.53" else 40,
                ),
            }
        return record

    def content(self) -> dict:
        return build_site.read_json(build_site.CONTENT_PATH)

    def test_only_published_verified_assets_become_download_links(self) -> None:
        records = [
            self.release(tag="v1.1.53", prerelease=False),
            self.release(tag="v1.1.52", prerelease=True),
            self.release(tag="v1.1.99", prerelease=False, verified=False),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            state = build_site.generate_site(
                content=self.content(), records=records, output_dir=output,
                base_url="https://qwy20040320.github.io/carpaly",
            )
            self.assertEqual(state["stable"]["tag"], "v1.1.53")
            self.assertEqual(state["beta"]["tag"], "v1.1.52")
            downloads = (output / "downloads/index.html").read_text(encoding="utf-8")
            history = (output / "history/index.html").read_text(encoding="utf-8")
            self.assertIn("CarPaly-XingyueL-v1.1.53.apk", downloads)
            self.assertIn("CarPaly-XingyueL-v1.1.52.apk", history)
            self.assertNotIn("CarPaly-XingyueL-v1.1.99.apk", history)
            self.assertIn("2024 Tianji", (output / "compatibility/index.html").read_text(encoding="utf-8"))
            self.assertTrue((output / "zh-Hans/guide/index.html").is_file())
            zh_home = (output / "zh-Hans/index.html").read_text(encoding="utf-8")
            self.assertIn("/carpaly/zh-Hans/downloads/", zh_home)

    def test_empty_verified_catalog_never_invents_an_apk(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            state = build_site.generate_site(
                content=self.content(), records=[], output_dir=output,
                base_url="https://qwy20040320.github.io/carpaly",
            )
            self.assertIsNone(state["stable"])
            self.assertIsNone(state["beta"])
            english_home = (output / "index.html").read_text(encoding="utf-8")
            chinese_home = (output / "zh-Hans/index.html").read_text(encoding="utf-8")
            self.assertNotIn("CarPaly-XingyueL-v", english_home + chinese_home)
            self.assertIn("No verified public APK", english_home)

    def test_release_state_conflict_is_reported_without_rewriting_notes(self) -> None:
        record = self.release(tag="v1.1.53", prerelease=False)
        record["releaseNoteStateConflict"] = True
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            build_site.generate_site(
                content=self.content(), records=[record], output_dir=output,
                base_url="https://qwy20040320.github.io/carpaly",
            )
            page = (output / "index.html").read_text(encoding="utf-8")
            self.assertIn("hand-written notes contain preview wording", page)
            self.assertIn("CarPaly-XingyueL-v1.1.53.apk", page)

    def test_release_snapshot_preserves_one_source_for_site_and_ota(self) -> None:
        release = {"tag_name": "v1.1.53", "assets": [{"name": "verified.json"}]}
        verification = {"status": "PASS", "apkSha256": "a" * 64}
        with tempfile.TemporaryDirectory() as tmp:
            snapshot = Path(tmp) / "snapshot" / "releases.json"
            build_site.write_release_snapshot(snapshot, "Qwy20040320/carpaly", [release],
                                              {"v1.1.53": verification})
            releases, verifications = build_ota_manifests.read_release_snapshot(snapshot)
            self.assertEqual(releases, [release])
            self.assertEqual(verifications["v1.1.53"], verification)

    def test_ota_rejects_release_snapshot_for_another_repository(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            snapshot = Path(tmp) / "snapshot.json"
            snapshot.write_text(
                '{"schemaVersion":1,"repository":"someone/else","releases":[],"verifications":{}}',
                encoding="utf-8",
            )
            with self.assertRaises(build_ota_manifests.ota_manifest.ManifestError):
                build_ota_manifests.read_release_snapshot(snapshot)


if __name__ == "__main__":
    unittest.main()
