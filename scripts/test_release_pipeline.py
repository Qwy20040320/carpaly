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
        state.setdefault("patch_fields", []).append([item for item in args if item.startswith(("draft=", "prerelease=", "name=", "body="))])
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
        if state.get("fail_release_list"):
            fail("simulated release list access failure")
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
    prerelease = "--prerelease" in args
    if "--target" in args:
        state["tag_created"] = True
        state["tag_commit"] = args[args.index("--target") + 1]
    state["release"] = {
        "id": 4242,
        "tag_name": tag,
        "draft": True,
        "prerelease": prerelease,
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

FAKE_GIT = r'''#!/usr/bin/env python3
import json
import os
import sys

state = json.loads(open(os.environ["FAKE_GH_STATE"], encoding="utf-8").read())
args = sys.argv[1:]
if args and args[0] == "ls-remote":
    if state.get("fail_tag_lookup"):
        print("simulated remote ref lookup failure", file=sys.stderr)
        raise SystemExit(128)
    if state.get("tag_missing") and not state.get("tag_created"):
        raise SystemExit(2)
    tag = next((item.removeprefix("refs/tags/") for item in args if item.startswith("refs/tags/") and not item.endswith("^{}")), "")
    commit = state.get("tag_commit", "a" * 40)
    print(f"{commit}\trefs/tags/{tag}")
    raise SystemExit(0)
print("unexpected git invocation", file=sys.stderr)
raise SystemExit(1)
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
    def test_authenticated_release_requires_manual_or_reviewed_main_intent(self):
        workflow = (ROOT / ".github/workflows/android.yml").read_text(encoding="utf-8")
        self.assertIn(":mobile:lintRelease", workflow)
        self.assertIn(":mobile:verifyStandaloneAuthentication", workflow)
        self.assertIn(":mobile:assembleRelease", workflow)
        self.assertNotIn("MFI_PUBLIC_DISTRIBUTION_REVIEWED", workflow)
        self.assertNotIn("MFI_PUBLIC_DISTRIBUTION_AUTHORIZATION_REF", workflow)
        self.assertIn("publish_authenticated_release:", workflow)
        self.assertIn("default: false", workflow)
        self.assertIn("github.event_name == 'workflow_dispatch'", workflow)
        self.assertIn("inputs.publish_authenticated_release == true", workflow)
        self.assertIn("release_intent:", workflow)
        self.assertIn("needs.check.result == 'success'", workflow)
        self.assertIn("needs.release_intent.outputs.should_publish == 'true'", workflow)
        self.assertIn("config/release-intent.json", (ROOT / "scripts/release_intent.py").read_text(encoding="utf-8"))
        self.assertNotIn("tags: ['v1.*']", workflow)
        self.assertNotIn("debug-apks-and-sha256", workflow)
        self.assertNotIn("mobile/build/outputs/apk/debug/*.apk", workflow)
        self.assertIn("Debug APK must not contain user authentication identity", workflow)

    def test_release_signer_uses_environment_pin_and_reports_only_public_fingerprints(self):
        workflow = (ROOT / ".github/workflows/android.yml").read_text(encoding="utf-8")
        release_job = workflow.split("  authenticated_release:", 1)[1]
        provision_step = release_job.split("- name: Build authenticated Release APK", 1)[0]

        self.assertIn("environment: mfi-public-release", release_job)
        self.assertIn("RELEASE_KEYSTORE_BASE64: ${{ secrets.RELEASE_KEYSTORE_BASE64 }}", provision_step)
        self.assertIn("RELEASE_STORE_PASSWORD: ${{ secrets.RELEASE_STORE_PASSWORD }}", provision_step)
        self.assertIn("RELEASE_KEY_ALIAS: ${{ secrets.RELEASE_KEY_ALIAS }}", provision_step)
        self.assertIn("RELEASE_SIGNING_CERT_SHA256: ${{ vars.RELEASE_SIGNING_CERT_SHA256 }}", provision_step)
        self.assertIn("scripts/release_signing_preflight.py", provision_step)
        self.assertIn("RELEASE_KEY_PASSWORD: ${{ secrets.RELEASE_KEY_PASSWORD }}", provision_step)
        self.assertNotIn("RELEASE_SIGNING_CERT_SHA256: ${{ secrets.", provision_step)

    def test_release_authentication_and_signer_secrets_are_isolated_by_step(self):
        workflow = (ROOT / ".github/workflows/android.yml").read_text(encoding="utf-8")
        release_job = workflow.split("  authenticated_release:", 1)[1]
        auth_step = release_job.split("- name: Provision and verify formal Release signer", 1)[0]
        signer_step = release_job.split("- name: Provision and verify formal Release signer", 1)[1].split(
            "- name: Build authenticated Release APK", 1
        )[0]
        self.assertIn("MFI_IDENTITY_PK8_BASE64", auth_step)
        self.assertNotIn("RELEASE_KEYSTORE_BASE64", auth_step)
        self.assertIn("RELEASE_KEYSTORE_BASE64", signer_step)
        self.assertNotIn("MFI_IDENTITY_PK8_BASE64", signer_step)

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
                manifest_payload = json.dumps({"schemaVersion": 1, "publicMarkdown": ["README.md"]}).encode()
                manifest = tarfile.TarInfo("CarPaly/config/public-markdown-allowlist.json")
                manifest.size = len(manifest_payload)
                archive.addfile(manifest, fileobj=io.BytesIO(manifest_payload))
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

    def test_real_commit_archive_keeps_only_allowlisted_markdown_and_no_symlinks(self):
        markdown_config = json.loads(
            (ROOT / "config/public-markdown-allowlist.json").read_text(encoding="utf-8")
        )
        allowed_markdown = {
            f"CarPaly/{name}" for name in markdown_config["publicMarkdown"]
        }
        tracked = set(subprocess.check_output(
            ["git", "ls-tree", "-r", "--name-only", "HEAD"], cwd=ROOT, text=True
        ).splitlines())
        if "config/public-markdown-allowlist.json" not in tracked:
            self.skipTest("source-archive integration runs after the public allow-list is committed")
        expected_markdown = {name for name in allowed_markdown if name.removeprefix("CarPaly/") in tracked}
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
                included_markdown = {name for name in names if name.lower().endswith(".md")}
                self.assertEqual(expected_markdown, included_markdown)
                self.assertTrue(all(((item.external_attr >> 16) & 0o170000) != stat.S_IFLNK for item in archive.infolist()))
                self.assertIsNone(archive.testzip())


@unittest.skipUnless(shutil.which("bash"), "publisher integration tests run on Linux CI with Bash")
class PublisherTests(unittest.TestCase):
    tag = "v1.1.51"
    version = "1.1.51"
    apk_name = f"CarPaly-XingyueL-v{version}.apk"
    source_name = f"CarPaly-XingyueL-v{version}-source.zip"
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
            "tag_missing": False,
            "tag_created": False,
            "tag_commit": "a" * 40,
        }
        state_path.write_text(json.dumps(state), encoding="utf-8")
        remote = root / "remote"
        fake_bin = root / "bin"
        fake_bin.mkdir()
        gh = fake_bin / "gh"
        gh.write_text(FAKE_GH, encoding="utf-8", newline="\n")
        gh.chmod(0o755)
        fake_git = fake_bin / "git"
        fake_git.write_text(FAKE_GIT, encoding="utf-8", newline="\n")
        fake_git.chmod(0o755)
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
            "APK_VERSION_CODE": "39",
            "RELEASE_COMMIT": "a" * 40,
            "AUTO_CREATE_TAG": "false",
            "RELEASE_PRERELEASE": "true",
            "RELEASE_SIGNING_CERT_SHA256": "4d26d1c861b41a2cee4515e31f5f5c7eb13b9dd06e7485aa1687bc1d2ac73d90",
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
            self.assertEqual(state["patch_fields"], [["draft=false", "prerelease=true"]])
            self.assertIn("<!-- CARPALY:RELEASE_NOTES:START -->", state["release"]["body"])
            self.assertIn("Tag source commit: " + "a" * 40, state["release"]["body"])
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

    def test_release_list_api_failure_does_not_attempt_release_creation(self):
        folder, env, state_path, *_ = self.prepare()
        with folder:
            state = self.read_state(state_path)
            state["fail_release_list"] = True
            state_path.write_text(json.dumps(state), encoding="utf-8")
            result = self.run_publisher(env)
            self.assertNotEqual(result.returncode, 0)
            state = self.read_state(state_path)
            self.assertEqual(state["creates"], 0)
            self.assertEqual(state["uploads"], 0)

    def test_conflicting_existing_asset_is_preserved_without_upload_or_patch(self):
        wrong_sha = "0" * 64
        release = {"id": 4242, "tag_name": self.tag, "draft": True, "prerelease": True,
                   "body": "Android versionCode: 39\n"}
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
                   "body": "Android versionCode: 39\n"}
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

    def test_existing_draft_handwritten_notes_and_title_are_preserved(self):
        original_body = "Android versionCode: 39\\nMaintainer-authored release notes.\\n"
        release = {"id": 4242, "tag_name": self.tag, "draft": True, "prerelease": True,
                   "name": "Hand-written title", "body": original_body}
        folder, env, state_path, _, _, _ = self.prepare(initial_release=release)
        with folder:
            result = self.run_publisher(env)
            self.assertEqual(result.returncode, 0, result.stderr)
            state = self.read_state(state_path)
            self.assertEqual(state["release"]["name"], "Hand-written title")
            self.assertEqual(state["release"]["body"], original_body)
            self.assertEqual(state["patch_fields"], [["draft=false", "prerelease=true"]])

    def test_existing_published_release_is_read_only_when_assets_match(self):
        original_body = "Android versionCode: 39\\nPublished hand-written notes.\\n"
        release = {"id": 4242, "tag_name": self.tag, "draft": False, "prerelease": False,
                   "name": "Formal title", "body": original_body}
        folder, env, state_path, apk, source, sums = self.prepare(initial_release=release)
        remote = state_path.parent / "remote"
        remote.mkdir()
        assets = []
        for file in (apk, source, sums):
            content = file.read_bytes()
            (remote / file.name).write_bytes(content)
            assets.append({"name": file.name, "size": len(content), "digest": "sha256:" + sha256(content), "state": "uploaded"})
        state = self.read_state(state_path)
        state["assets"] = assets
        state_path.write_text(json.dumps(state), encoding="utf-8")
        env["RELEASE_PRERELEASE"] = "false"
        with folder:
            result = self.run_publisher(env)
            self.assertEqual(result.returncode, 0, result.stderr)
            state = self.read_state(state_path)
            self.assertEqual(state["patches"], 0)
            self.assertEqual(state["release"]["name"], "Formal title")
            self.assertEqual(state["release"]["body"], original_body)
            self.assertFalse(state["release"]["prerelease"])

    def test_auto_release_creates_tag_only_with_verified_draft_assets_ready(self):
        folder, env, state_path, *_ = self.prepare()
        state = self.read_state(state_path)
        state["tag_missing"] = True
        state_path.write_text(json.dumps(state), encoding="utf-8")
        env["AUTO_CREATE_TAG"] = "true"
        with folder:
            result = self.run_publisher(env)
            self.assertEqual(result.returncode, 0, result.stderr)
            state = self.read_state(state_path)
            self.assertTrue(state["tag_created"])
            self.assertEqual(state["tag_commit"], "a" * 40)
            self.assertFalse(state["release"]["draft"])
            self.assertTrue(state["release"]["prerelease"])

    def test_manual_release_refuses_to_create_a_missing_tag(self):
        folder, env, state_path, *_ = self.prepare()
        state = self.read_state(state_path)
        state["tag_missing"] = True
        state_path.write_text(json.dumps(state), encoding="utf-8")
        with folder:
            result = self.run_publisher(env)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("manual tag-based publication requires", result.stderr)
            self.assertEqual(self.read_state(state_path)["creates"], 0)

    def test_auto_release_can_create_a_stable_release_with_stable_notes(self):
        folder, env, state_path, *_ = self.prepare()
        env["RELEASE_PRERELEASE"] = "false"
        with folder:
            result = self.run_publisher(env)
            self.assertEqual(result.returncode, 0, result.stderr)
            state = self.read_state(state_path)
            self.assertFalse(state["release"]["prerelease"])
            self.assertIn("GitHub channel: stable", state["release"]["body"])
            self.assertNotIn("Public Preview", state["release"]["name"])

    def test_existing_tag_for_another_commit_blocks_before_release_api_mutation(self):
        folder, env, state_path, *_ = self.prepare()
        state = self.read_state(state_path)
        state["tag_commit"] = "b" * 40
        state_path.write_text(json.dumps(state), encoding="utf-8")
        with folder:
            result = self.run_publisher(env)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("different source commit", result.stderr)
            self.assertEqual(self.read_state(state_path)["creates"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
