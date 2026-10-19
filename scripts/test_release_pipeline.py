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
PUBLISHER_PATH = ROOT / ".github/scripts/prepare-release-draft.sh"
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
        if state.get("fail_asset_list"):
            fail("simulated release assets access failure")
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
    def test_authenticated_release_requires_protected_main_intent_and_merge_authorization(self):
        workflow = (ROOT / ".github/workflows/android.yml").read_text(encoding="utf-8")
        self.assertIn(":mobile:lintRelease", workflow)
        self.assertIn(":mobile:verifyStandaloneAuthentication", workflow)
        self.assertIn(":mobile:assembleRelease", workflow)
        self.assertNotIn("MFI_PUBLIC_DISTRIBUTION_REVIEWED", workflow)
        self.assertNotIn("MFI_PUBLIC_DISTRIBUTION_AUTHORIZATION_REF", workflow)
        self.assertNotIn("publish_authenticated_release", workflow)
        self.assertIn("default: false", workflow)
        self.assertIn("release_intent:", workflow)
        self.assertIn("release_authorization:", workflow)
        self.assertIn("environment: release-policy-audit", workflow)
        self.assertIn("needs.check.result == 'success'", workflow)
        self.assertIn("needs.release_authorization.result == 'success'", workflow)
        self.assertIn("github.event_name == 'push' && github.ref == 'refs/heads/main'", workflow)
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
        signer_step = release_job.split("- name: Provision and verify formal Release signer", 1)[1].split(
            "- name: Provision protected MFi inputs after signer verification", 1
        )[0]
        auth_step = release_job.split("- name: Provision protected MFi inputs after signer verification", 1)[1].split(
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


@unittest.skipUnless(shutil.which("bash"), "Release draft integration tests run on Linux CI with Bash")
class PublisherTests(unittest.TestCase):
    tag = "v1.1.51"
    commit = "a" * 40
    signer = "4d26d1c861b41a2cee4515e31f5f5c7eb13b9dd06e7485aa1687bc1d2ac73d90"

    def prepare(self, *, initial_release=None, initial_assets=None, tag_missing=False, tag_commit=None):
        folder = tempfile.TemporaryDirectory()
        root = Path(folder.name)
        state_path = root / "state.json"
        state_path.write_text(json.dumps({
            "release": initial_release,
            "releases": [initial_release] if initial_release else [],
            "assets": initial_assets or [],
            "uploads": 0,
            "patches": 0,
            "creates": 0,
            "tag_missing": tag_missing,
            "tag_created": False,
            "tag_commit": tag_commit or self.commit,
            "fail_release_list": False,
            "fail_asset_list": False,
        }), encoding="utf-8")
        fake_bin = root / "bin"
        fake_bin.mkdir()
        for name, payload in (("gh", FAKE_GH), ("git", FAKE_GIT)):
            executable = fake_bin / name
            executable.write_text(payload, encoding="utf-8", newline="\n")
            executable.chmod(0o755)
        env = os.environ.copy()
        env.update({
            "PATH": str(fake_bin) + os.pathsep + env.get("PATH", ""),
            "FAKE_GH_STATE": str(state_path),
            "GH_TOKEN": "unit-test-token-not-a-credential",
            "GH_REPO": "Qwy20040320/carpaly",
            "RELEASE_TAG": self.tag,
            "RELEASE_COMMIT": self.commit,
            "RELEASE_VERSION_CODE": "39",
            "RELEASE_SIGNING_CERT_SHA256": self.signer,
            "RELEASE_PRERELEASE": "true",
            "AUTO_CREATE_TAG": "true",
        })
        return folder, env, state_path

    def run_publisher(self, env):
        return subprocess.run(
            [shutil.which("bash"), str(PUBLISHER_PATH)],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
        )

    @staticmethod
    def read_state(path):
        return json.loads(path.read_text(encoding="utf-8"))

    def test_new_release_is_created_as_metadata_only_draft(self):
        folder, env, state_path = self.prepare(tag_missing=True)
        with folder:
            result = self.run_publisher(env)
            self.assertEqual(result.returncode, 0, result.stderr)
            state = self.read_state(state_path)
            self.assertTrue(state["release"]["draft"])
            self.assertTrue(state["release"]["prerelease"])
            self.assertEqual(state["uploads"], 0)
            self.assertEqual(state["patches"], 0)
            self.assertEqual(state["creates"], 1)
            self.assertEqual(state["assets"], [])
            self.assertIn("No APK", state["release"]["body"])
            self.assertIn("extractable authentication identity", state["release"]["body"])
            self.assertIn("RELEASE_DRAFT_STATUS=CREATED", result.stdout)

    def test_local_verified_apk_metadata_is_recorded_without_upload(self):
        folder, env, state_path = self.prepare(tag_missing=True)
        env.update({
            "RELEASE_APK_SHA256": "a" * 64,
            "RELEASE_APK_FILE_NAME": "CarPaly-XingyueL-v1.1.51.apk",
            "RELEASE_APK_BYTES": "123456",
        })
        with folder:
            result = self.run_publisher(env)
            self.assertEqual(result.returncode, 0, result.stderr)
            state = self.read_state(state_path)
            self.assertIn("Local APK SHA-256: " + "a" * 64, state["release"]["body"])
            self.assertEqual(state["uploads"], 0)
            self.assertTrue(state["release"]["draft"])

    def test_existing_draft_without_local_apk_hash_is_not_rewritten(self):
        release = {"id": 77, "tag_name": self.tag, "draft": True, "prerelease": True,
                   "name": "Existing draft", "body": "<!-- carpaly-release-draft-v1: metadata-only; reviewed-assets-required -->\nExisting notes"}
        folder, env, state_path = self.prepare(initial_release=release)
        env.update({
            "RELEASE_APK_SHA256": "b" * 64,
            "RELEASE_APK_FILE_NAME": "CarPaly-XingyueL-v1.1.51.apk",
            "RELEASE_APK_BYTES": "123456",
        })
        with folder:
            result = self.run_publisher(env)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("lacks this local APK hash", result.stderr)
            state = self.read_state(state_path)
            self.assertEqual(state["release"], release)
            self.assertEqual(state["patches"], 0)
            self.assertEqual(state["uploads"], 0)

    def test_repeated_run_reuses_existing_draft_without_mutation(self):
        folder, env, state_path = self.prepare(tag_missing=True)
        with folder:
            first = self.run_publisher(env)
            self.assertEqual(first.returncode, 0, first.stderr)
            before = self.read_state(state_path)
            second = self.run_publisher(env)
            self.assertEqual(second.returncode, 0, second.stderr)
            after = self.read_state(state_path)
            self.assertEqual(after["creates"], 1)
            self.assertEqual(after["uploads"], 0)
            self.assertEqual(after["patches"], 0)
            self.assertTrue(after["release"]["draft"])
            self.assertEqual(after["release"]["body"], before["release"]["body"])
            self.assertIn("RELEASE_DRAFT_STATUS=REUSED", second.stdout)

    def test_published_release_is_left_completely_unchanged(self):
        release = {"id": 77, "tag_name": self.tag, "draft": False, "prerelease": False,
                   "name": "Hand-authored published title", "body": "Published notes"}
        asset = {"name": "old-authenticated.apk", "size": 100, "digest": "sha256:" + "0" * 64, "state": "uploaded"}
        folder, env, state_path = self.prepare(initial_release=release, initial_assets=[asset])
        with folder:
            result = self.run_publisher(env)
            self.assertEqual(result.returncode, 0, result.stderr)
            state = self.read_state(state_path)
            self.assertEqual(state["creates"], 0)
            self.assertEqual(state["uploads"], 0)
            self.assertEqual(state["patches"], 0)
            self.assertEqual(state["release"], release)
            self.assertEqual(state["assets"], [asset])
            self.assertIn("PUBLISHED_IMMUTABLE", result.stdout)

    def test_draft_with_any_existing_attachment_fails_without_removing_it(self):
        release = {"id": 77, "tag_name": self.tag, "draft": True, "prerelease": True,
                   "name": "Existing draft", "body": "<!-- carpaly-release-draft-v1: metadata-only; reviewed-assets-required -->\nKeep me"}
        asset = {"name": "candidate.apk", "size": 100, "digest": "sha256:" + "0" * 64, "state": "uploaded"}
        folder, env, state_path = self.prepare(initial_release=release, initial_assets=[asset])
        with folder:
            result = self.run_publisher(env)
            self.assertNotEqual(result.returncode, 0)
            state = self.read_state(state_path)
            self.assertEqual(state["creates"], 0)
            self.assertEqual(state["uploads"], 0)
            self.assertEqual(state["patches"], 0)
            self.assertEqual(state["assets"], [asset])
            self.assertEqual(state["release"], release)

    def test_unrecognized_draft_is_not_reused_or_mutated(self):
        release = {"id": 77, "tag_name": self.tag, "draft": True, "prerelease": True,
                   "name": "Hand-authored draft", "body": "Human notes not reviewed by this helper"}
        folder, env, state_path = self.prepare(initial_release=release)
        with folder:
            result = self.run_publisher(env)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("not created by the metadata-only preparer", result.stderr)
            state = self.read_state(state_path)
            self.assertEqual(state["release"], release)
            self.assertEqual(state["creates"], 0)
            self.assertEqual(state["patches"], 0)
            self.assertEqual(state["uploads"], 0)

    def test_existing_draft_with_wrong_channel_is_not_reused_or_mutated(self):
        release = {"id": 77, "tag_name": self.tag, "draft": True, "prerelease": False,
                   "name": "Existing stable draft", "body": "Keep me"}
        folder, env, state_path = self.prepare(initial_release=release)
        with folder:
            result = self.run_publisher(env)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("channel does not match", result.stderr)
            state = self.read_state(state_path)
            self.assertEqual(state["release"], release)
            self.assertEqual(state["creates"], 0)
            self.assertEqual(state["patches"], 0)
            self.assertEqual(state["uploads"], 0)

    def test_asset_inventory_api_failure_fails_closed(self):
        release = {"id": 77, "tag_name": self.tag, "draft": True, "prerelease": True,
                   "name": "Existing draft", "body": "Keep me"}
        folder, env, state_path = self.prepare(initial_release=release)
        with folder:
            state = self.read_state(state_path)
            state["fail_asset_list"] = True
            state_path.write_text(json.dumps(state), encoding="utf-8")
            result = self.run_publisher(env)
            self.assertNotEqual(result.returncode, 0)
            after = self.read_state(state_path)
            self.assertEqual(after["release"], release)
            self.assertEqual(after["creates"], 0)
            self.assertEqual(after["patches"], 0)
            self.assertEqual(after["uploads"], 0)

    def test_source_commit_mismatch_fails_before_release_mutation(self):
        folder, env, state_path = self.prepare(tag_commit="b" * 40)
        with folder:
            result = self.run_publisher(env)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("does not point to the verified source commit", result.stderr)
            self.assertEqual(self.read_state(state_path)["creates"], 0)

    def test_missing_tag_without_explicit_intent_is_not_created(self):
        folder, env, state_path = self.prepare(tag_missing=True)
        env["AUTO_CREATE_TAG"] = "false"
        with folder:
            result = self.run_publisher(env)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("not authorized to create it", result.stderr)
            self.assertEqual(self.read_state(state_path)["creates"], 0)

    def test_invalid_signer_or_tag_fails_before_github_api(self):
        for variable, value in (("RELEASE_SIGNING_CERT_SHA256", "0" * 63), ("RELEASE_TAG", "v1.1.51/evil")):
            with self.subTest(variable=variable):
                folder, env, state_path = self.prepare()
                env[variable] = value
                with folder:
                    result = self.run_publisher(env)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertEqual(self.read_state(state_path).get("api_calls", []), [])

    def test_workflow_and_helper_contain_no_public_binary_upload_or_publish_transition(self):
        helper = PUBLISHER_PATH.read_text(encoding="utf-8")
        workflow = (ROOT / ".github/workflows/android.yml").read_text(encoding="utf-8")
        self.assertNotIn("gh release upload", helper)
        self.assertNotIn("draft=false", helper)
        self.assertNotIn("--method PATCH", helper)
        self.assertNotIn("gh release upload", helper)
        self.assertIn("api --paginate \"repos/$GH_REPO/releases/$release_id/assets?per_page=100\"", helper)
        self.assertIn("carpaly-release-draft-v1: metadata-only", helper)
        release_job = workflow.split("  authenticated_release:", 1)[1].split("  prepare_release_draft:", 1)[0]
        self.assertNotIn("gh release upload", release_job)
        self.assertNotIn("actions/upload-artifact", release_job)
        draft_job = workflow.split("  prepare_release_draft:", 1)[1]
        self.assertIn("contents: write", draft_job)
        self.assertNotIn("environment:", draft_job)
        self.assertNotIn("secrets.", draft_job)


class ReleaseWorkflowSafetyTests(unittest.TestCase):
    def test_main_signer_pin_is_checked_before_any_secret_mapping(self):
        workflow = (ROOT / ".github/workflows/android.yml").read_text(encoding="utf-8")
        release_job = workflow.split("  authenticated_release:", 1)[1].split("  prepare_release_draft:", 1)[0]
        pin = release_job.index("scripts/check_release_signer_pin.py")
        auth_secret = release_job.index("MFI_IDENTITY_PK8_BASE64:")
        signing_secret = release_job.index("RELEASE_KEYSTORE_BASE64:")
        self.assertLess(pin, auth_secret)
        self.assertLess(pin, signing_secret)
        signer_preflight = release_job.index("scripts/release_signing_preflight.py")
        mfi_mapping = release_job.index("MFI_IDENTITY_PK8_BASE64: ${{ secrets.")
        self.assertLess(signer_preflight, mfi_mapping)
        self.assertIn("permissions:\n      contents: read", release_job)

    def test_pr_and_push_ci_do_not_reference_production_signing_secrets(self):
        workflow = (ROOT / ".github/workflows/android.yml").read_text(encoding="utf-8")
        check_job = workflow.split("  check:", 1)[1].split("  release_intent:", 1)[0]
        intent_job = workflow.split("  release_intent:", 1)[1].split("  release_authorization:", 1)[0]
        self.assertNotIn("secrets.", check_job)
        self.assertNotIn("secrets.", intent_job)

    def test_historical_candidate_only_uploads_sanitized_report_and_pin_precedes_secrets(self):
        workflow = (ROOT / ".github/workflows/carpaly-android-build.yml").read_text(encoding="utf-8")
        candidate = workflow.split("  signed_candidate:", 1)[1].split("  prepare_historical_draft:", 1)[0]
        self.assertLess(candidate.index("Check Environment signer pin before mapping any Secret"),
                        candidate.index("Provision protected runtime authentication inputs"))
        self.assertLess(candidate.index("scripts/release_signing_preflight.py"),
                        candidate.index("Provision protected runtime authentication inputs"))
        self.assertIn("build-report/rebuild.json", candidate)
        artifact_step = candidate.split("- name: Upload safe build report only", 1)[1].split(
            "- name: Remove temporary signing", 1
        )[0]
        self.assertNotIn("outputs/apk", artifact_step)
        self.assertNotIn(".apk", artifact_step)

    def test_debug_user_installable_apk_is_not_uploaded_as_an_artifact(self):
        workflow = (ROOT / ".github/workflows/build-android-tv.yml").read_text(encoding="utf-8")
        self.assertNotIn("actions/upload-artifact", workflow)
        self.assertNotIn("outputs/apk/debug/*.apk", workflow)

if __name__ == "__main__":
    unittest.main(verbosity=2)
