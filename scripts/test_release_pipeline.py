#!/usr/bin/env python3
"""Offline safety tests for source packaging and the authenticated release publisher."""

from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest import mock
from zipfile import ZIP_DEFLATED, ZipFile


ROOT = Path(__file__).resolve().parents[1]
ARCHIVER_PATH = ROOT / "scripts/package_source_archive.py"
PUBLISHER_PATH = ROOT / ".github/scripts/publish-authenticated-apk-release.sh"
FAKE_GH = r'''#!/usr/bin/env python3
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys

state_path = Path(os.environ["FAKE_GH_STATE"])
state = json.loads(state_path.read_text(encoding="utf-8"))
args = sys.argv[1:]

def save():
    state_path.write_text(json.dumps(state), encoding="utf-8")

def fail(message):
    print(message, file=sys.stderr)
    save()
    raise SystemExit(1)

if not args:
    fail("missing gh arguments")

if args[0] == "api":
    state.setdefault("api_calls", []).append(args)
    method = "GET"
    if "--method" in args:
        method = args[args.index("--method") + 1]
    endpoint = next((part for part in args if part.startswith("repos/")), "")
    if method == "PATCH":
        for item in args:
            if item.startswith("draft="):
                state["release"]["draft"] = item.split("=", 1)[1] == "true"
            elif item.startswith("prerelease="):
                state["release"]["prerelease"] = item.split("=", 1)[1] == "true"
            elif item.startswith("name="):
                state["release"]["name"] = item.split("=", 1)[1]
            elif item.startswith("body="):
                state["release"]["body"] = item.split("=", 1)[1]
        state["patches"] = state.get("patches", 0) + 1
        save()
        print(json.dumps(state["release"]))
    elif endpoint.endswith("/releases?per_page=100"):
        print(json.dumps(state.get("releases", [])))
    elif "/releases/" in endpoint and endpoint.endswith("/assets?per_page=100"):
        print(json.dumps(state.get("assets", [])))
    elif "/releases/tags/" in endpoint:
        if state.get("release") is None:
            fail("release not found")
        print(json.dumps(state["release"]))
    elif "/git/ref/tags/" in endpoint:
        print(json.dumps({"object": {"sha": "a" * 40, "type": "commit"}}))
    else:
        fail("unhandled API endpoint: " + endpoint)
elif args[0] == "release" and len(args) > 1 and args[1] == "create":
    tag = args[2]
    notes = args[args.index("--notes") + 1]
    state["release"] = {
        "id": 4242,
        "tag_name": tag,
        "draft": True,
        "prerelease": True,
        "name": args[args.index("--title") + 1],
        "body": notes,
    }
    state.setdefault("releases", []).append(state["release"])
    state["assets"] = []
    state["creates"] = state.get("creates", 0) + 1
    save()
elif args[0] == "release" and len(args) > 1 and args[1] == "upload":
    tag = args[2]
    local = Path(args[3])
    if state.get("fail_upload_name") == local.name:
        fail("simulated upload failure")
    payload = local.read_bytes()
    remote = Path(os.environ["FAKE_GH_REMOTE"]) / local.name
    remote.parent.mkdir(parents=True, exist_ok=True)
    remote.write_bytes(payload)
    state.setdefault("assets", []).append({
        "name": local.name,
        "size": len(payload),
        "digest": "sha256:" + hashlib.sha256(payload).hexdigest(),
        "state": "uploaded",
    })
    state["uploads"] = state.get("uploads", 0) + 1
    save()
elif args[0] == "release" and len(args) > 1 and args[1] == "download":
    patterns = [args[index + 1] for index, item in enumerate(args[:-1]) if item == "--pattern"]
    destination = Path(args[args.index("--dir") + 1])
    remote_dir = Path(os.environ["FAKE_GH_REMOTE"])
    destination.mkdir(parents=True, exist_ok=True)
    for name in patterns:
        payload = (remote_dir / name).read_bytes()
        if state.get("corrupt_download") and state.get("downloads", 0) == 0 and name.endswith(".apk"):
            payload += b"tampered"
        (destination / name).write_bytes(payload)
    state["downloads"] = state.get("downloads", 0) + 1
    save()
else:
    fail("unhandled gh command: " + repr(args))
'''


def load_archiver():
    spec = importlib.util.spec_from_file_location("package_source_archive", ARCHIVER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load source archive module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


class SourceArchiveTests(unittest.TestCase):
    def test_release_workflow_follows_authenticated_release_build_steps_without_local_policy_flags(self):
        workflow = (ROOT / ".github/workflows/android.yml").read_text(encoding="utf-8")
        self.assertIn(":mobile:lintRelease", workflow)
        self.assertIn(":mobile:verifyStandaloneAuthentication", workflow)
        self.assertIn(":mobile:assembleRelease", workflow)
        self.assertNotIn("MFI_PUBLIC_DISTRIBUTION_REVIEWED", workflow)
        self.assertNotIn("MFI_PUBLIC_DISTRIBUTION_AUTHORIZATION_REF", workflow)
        self.assertIn("verify distribution rights before tagging", workflow)

    def test_member_paths_reject_absolute_parent_and_windows_paths(self):
        archiver = load_archiver()
        for name in ("../outside", "/absolute", "CarPaly/../../outside", "CarPaly\\outside"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                archiver.safe_member_name(name)

    def test_archive_rejects_symlink_even_with_traversal_target(self):
        archiver = load_archiver()
        with tempfile.SpooledTemporaryFile() as tar_bytes:
            with tarfile.open(fileobj=tar_bytes, mode="w") as archive:
                for name, payload in (("CarPaly/README.md", b"readme"), ("CarPaly/LICENSE", b"license")):
                    entry = tarfile.TarInfo(name)
                    entry.size = len(payload)
                    archive.addfile(entry, fileobj=io.BytesIO(payload))
                link = tarfile.TarInfo("CarPaly/docs/outside")
                link.type = tarfile.SYMTYPE
                link.linkname = "../../../../outside"
                archive.addfile(link)
            tar_bytes.seek(0)
            archive_payload = tar_bytes.read()
        calls = 0

        def fake_git(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 1:
                return subprocess.CompletedProcess(args[0], 0, stdout="b" * 40 + "\n", stderr="")
            kwargs["stdout"].write(archive_payload)
            return subprocess.CompletedProcess(args[0], 0)

        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "source.zip"
            with mock.patch.object(archiver.subprocess, "run", side_effect=fake_git):
                with self.assertRaisesRegex(ValueError, "Symbolic links are forbidden"):
                    archiver.build_archive("HEAD", output)
            self.assertFalse(output.exists())

    def test_real_commit_archive_keeps_only_home_markdown_and_no_symlinks(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "source.zip"
            subprocess.run(
                [sys.executable, str(ARCHIVER_PATH), "--ref", "HEAD", "--output", str(output)],
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            with ZipFile(output) as archive:
                names = set(archive.namelist())
                self.assertIn("CarPaly/README.md", names)
                self.assertIn("CarPaly/LICENSE", names)
                self.assertFalse(any(name.lower().endswith(".md") and name != "CarPaly/README.md" for name in names))
                self.assertTrue(all(((item.external_attr >> 16) & 0o170000) != stat.S_IFLNK for item in archive.infolist()))
                self.assertIsNone(archive.testzip())


@unittest.skipUnless(shutil.which("bash"), "publisher integration tests run on Linux CI with Bash")
class PublisherTests(unittest.TestCase):
    tag = "v1.1.4"
    version = "1.1.4"
    apk_name = f"CarPaly-XingyueL{version}.apk"
    source_name = f"CarPaly-XingyueL{version}-source.zip"
    sums_name = "SHA256SUMS.txt"

    def prepare(self, *, initial_release=None, initial_assets=None, corrupt_download=False, fail_upload_name=None):
        folder = tempfile.TemporaryDirectory()
        root = Path(folder.name)
        artifacts = root / "artifacts"
        artifacts.mkdir()
        apk = artifacts / self.apk_name
        apk.write_bytes(b"source-only release APK fixture\x00\x01")
        source = artifacts / self.source_name
        with ZipFile(source, "w", ZIP_DEFLATED) as archive:
            archive.writestr("CarPaly/README.md", "test fixture")
            archive.writestr("CarPaly/LICENSE", "GPL-3.0")
        apk_sha = sha256(apk.read_bytes())
        source_sha = sha256(source.read_bytes())
        sums = artifacts / self.sums_name
        sums.write_text(f"{apk_sha}  {self.apk_name}\n{source_sha}  {self.source_name}\n", encoding="ascii")
        state_path = root / "state.json"
        state = {
            "release": initial_release,
            "releases": [initial_release] if initial_release else [],
            "assets": initial_assets or [],
            "uploads": 0,
            "patches": 0,
            "creates": 0,
            "downloads": 0,
            "corrupt_download": corrupt_download,
            "fail_upload_name": fail_upload_name,
        }
        state_path.write_text(json.dumps(state), encoding="utf-8")
        remote = root / "remote"
        fake_bin = root / "bin"
        fake_bin.mkdir()
        gh = fake_bin / "gh"
        gh.write_text(FAKE_GH, encoding="utf-8", newline="\n")
        gh.chmod(0o755)
        env = os.environ.copy()
        env.update({
            "PATH": str(fake_bin) + os.pathsep + env.get("PATH", ""),
            "FAKE_GH_STATE": str(state_path),
            "FAKE_GH_REMOTE": str(remote),
            "GH_TOKEN": "test-token-not-a-credential",
            "GH_REPO": "Qwy20040320/carpaly",
            "RELEASE_TAG": self.tag,
            "APK_PATH": str(apk),
            "APK_NAME": self.apk_name,
            "APK_SHA256": apk_sha,
            "APK_SIZE": str(apk.stat().st_size),
            "APK_VERSION_CODE": "36",
            "SOURCE_ZIP_PATH": str(source),
            "SOURCE_ZIP_NAME": self.source_name,
            "SOURCE_ZIP_SHA256": source_sha,
            "SOURCE_ZIP_SIZE": str(source.stat().st_size),
            "SHA256SUMS_PATH": str(sums),
            "SHA256SUMS_SHA256": sha256(sums.read_bytes()),
            "SHA256SUMS_SIZE": str(sums.stat().st_size),
            "RUNNER_TEMP": str(root / "runner"),
        })
        return folder, env, state_path, apk, source, sums

    def run_publisher(self, env):
        return subprocess.run(
            [shutil.which("bash"), str(PUBLISHER_PATH)],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
        )

    def read_state(self, path):
        return json.loads(path.read_text(encoding="utf-8"))

    def test_success_publishes_only_three_matching_assets_after_remote_verification(self):
        folder, env, state_path, _, _, _ = self.prepare()
        with folder:
            result = self.run_publisher(env)
            self.assertEqual(result.returncode, 0, result.stderr)
            state = self.read_state(state_path)
            self.assertFalse(state["release"]["draft"])
            self.assertTrue(state["release"]["prerelease"])
            self.assertEqual(state["patches"], 1)
            self.assertEqual(state["downloads"], 2)
            self.assertEqual({asset["name"] for asset in state["assets"]}, {self.apk_name, self.source_name, self.sums_name})
            self.assertEqual(len(state["assets"]), 3)

    def test_checksum_mismatch_fails_before_any_github_api_call(self):
        folder, env, state_path, _, _, _ = self.prepare()
        with folder:
            env["APK_SHA256"] = "0" * 64
            result = self.run_publisher(env)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("SHA256SUMS.txt does not list", result.stderr)
            self.assertEqual(self.read_state(state_path).get("api_calls", []), [])

    def test_conflicting_existing_asset_is_preserved_without_upload_or_patch(self):
        wrong_sha = "0" * 64
        release = {"id": 4242, "tag_name": self.tag, "draft": True, "prerelease": True,
                   "body": "Android versionCode: 36\n"}
        asset = {"name": self.apk_name, "size": 32, "digest": "sha256:" + wrong_sha, "state": "uploaded"}
        folder, env, state_path, _, _, _ = self.prepare(initial_release=release, initial_assets=[asset])
        with folder:
            result = self.run_publisher(env)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("refusing replacement", result.stderr)
            state = self.read_state(state_path)
            self.assertEqual(state["uploads"], 0)
            self.assertEqual(state["patches"], 0)

    def test_upload_failure_leaves_release_draft(self):
        folder, env, state_path, _, _, _ = self.prepare(fail_upload_name=self.source_name)
        with folder:
            result = self.run_publisher(env)
            self.assertNotEqual(result.returncode, 0)
            state = self.read_state(state_path)
            self.assertTrue(state["release"]["draft"])
            self.assertEqual(state["patches"], 0)

    def test_downloaded_asset_mismatch_leaves_release_draft(self):
        folder, env, state_path, _, _, _ = self.prepare(corrupt_download=True)
        with folder:
            result = self.run_publisher(env)
            self.assertNotEqual(result.returncode, 0)
            state = self.read_state(state_path)
            self.assertTrue(state["release"]["draft"])
            self.assertEqual(state["patches"], 0)

    def test_public_release_missing_asset_is_not_mutated(self):
        release = {"id": 4242, "tag_name": self.tag, "draft": False, "prerelease": True,
                   "body": "Android versionCode: 36\n"}
        folder, env, state_path, apk, _, _ = self.prepare(initial_release=release)
        state = self.read_state(state_path)
        state["assets"] = [{"name": self.apk_name, "size": apk.stat().st_size,
                            "digest": "sha256:" + sha256(apk.read_bytes()), "state": "uploaded"}]
        state_path.write_text(json.dumps(state), encoding="utf-8")
        with folder:
            result = self.run_publisher(env)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("missing an asset", result.stderr)
            state = self.read_state(state_path)
            self.assertEqual(state["uploads"], 0)
            self.assertEqual(state["patches"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
