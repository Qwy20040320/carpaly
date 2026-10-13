#!/usr/bin/env python3
"""Offline tests for release documentation synchronization and GitHub API safety."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
from typing import Any
from unittest.mock import patch

from scripts import sync_release_docs as sync
from scripts.validate_release_metadata import validate_metadata


ROOT = Path(__file__).resolve().parents[1]
METADATA = json.loads((ROOT / "config/release-documentation.json").read_text(encoding="utf-8"))
LEDGER = json.loads((ROOT / "config/android-version-ledger.json").read_text(encoding="utf-8"))
REPO = "Qwy20040320/carpaly"
SIGNER = LEDGER["releaseCertificateSha256"]
APK_SHA = "a" * 64
COMMIT = "b" * 40
SECRET = "token-value-must-not-be-logged"


def make_release(
    tag: str = "v1.1.51", *, prerelease: bool = False, draft: bool = False,
    published: str = "2026-10-11T11:11:52Z", assets: list[dict[str, Any]] | None = None,
    body: str = "Release notes",
) -> dict[str, Any]:
    tag_part = tag
    return {
        "id": 10,
        "tag_name": tag,
        "name": tag,
        "draft": draft,
        "prerelease": prerelease,
        "published_at": published,
        "html_url": f"https://github.com/{REPO}/releases/tag/{tag_part}",
        "body": body,
        "assets": assets or [
            {
                "name": f"CarPaly-XingyueL-{tag.removeprefix('v')}.apk",
                "size": 123,
                "digest": f"sha256:{APK_SHA}",
                "browser_download_url": f"https://github.com/{REPO}/releases/download/{tag}/CarPaly-XingyueL-{tag.removeprefix('v')}.apk",
            }
        ],
    }


def make_verification(release: dict[str, Any] | None = None) -> dict[str, Any]:
    release = release or make_release()
    apk = release["assets"][0]
    return {
        "status": "PASS",
        "apk": apk["name"],
        "packageName": "com.shihab.diplay.hudtest",
        "versionName": release["tag_name"].removeprefix("v"),
        "versionCode": 39,
        "apkSha256": APK_SHA,
        "signerCertificateSha256": SIGNER,
        "checks": {
            "APK_SIGNATURE": "PASS",
            "PACKAGE_NAME_MATCH": "PASS",
            "SIGNING_CERTIFICATE_MATCH": "PASS",
            "APK_ZIP_INTEGRITY": "PASS",
            "RELEASE_VARIANT_NOT_DEBUGGABLE": "PASS",
        },
    }


class FakeResponse:
    def __init__(self, value: Any = None, raw: bytes | None = None) -> None:
        self.raw = raw if raw is not None else json.dumps(value).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, *_args):
        return self.raw


class QueueTransport:
    def __init__(self, values: list[Any]) -> None:
        self.values = list(values)
        self.calls: list[tuple[str, str, Any]] = []

    def __call__(self, request, timeout):
        payload = json.loads(request.data.decode("utf-8")) if request.data else None
        self.calls.append((request.get_method(), request.full_url, payload))
        value = self.values.pop(0)
        if isinstance(value, BaseException):
            raise value
        return FakeResponse(value)


class MarkerTests(unittest.TestCase):
    def test_replace_single_region_and_preserve_user_text(self):
        source = "before\n<!-- M:START -->\nold\n<!-- M:END -->\nafter\n"
        result = sync.replace_marker_region(source, "M", "new content")
        self.assertIn("before", result)
        self.assertIn("after", result)
        self.assertIn("new content", result)
        self.assertNotIn("old", result)

    def test_missing_markers_fail_closed(self):
        with self.assertRaises(sync.SyncError):
            sync.replace_marker_region("manual text", "M", "generated")

    def test_missing_start_fails_closed(self):
        with self.assertRaises(sync.SyncError):
            sync.replace_marker_region("<!-- M:END -->", "M", "generated")

    def test_duplicate_start_fails_closed(self):
        with self.assertRaises(sync.SyncError):
            sync.replace_marker_region("<!-- M:START --><!-- M:START --><!-- M:END -->", "M", "x")

    def test_duplicate_end_fails_closed(self):
        with self.assertRaises(sync.SyncError):
            sync.replace_marker_region("<!-- M:START --><!-- M:END --><!-- M:END -->", "M", "x")

    def test_reversed_markers_fail_closed(self):
        with self.assertRaises(sync.SyncError):
            sync.replace_marker_region("<!-- M:END --><!-- M:START -->", "M", "x")

    def test_hand_authored_release_notes_without_markers_are_preserved(self):
        body, status = sync._replace_if_managed("hand written release notes", "R", "generated")
        self.assertEqual(body, "hand written release notes")
        self.assertEqual(status, "UNMANAGED_PRESERVED")

    def test_managed_release_notes_preserve_surrounding_manual_text(self):
        body = "author intro\n<!-- R:START -->\nold\n<!-- R:END -->\nauthor close"
        updated, status = sync._replace_if_managed(body, "R", "facts")
        self.assertEqual(status, "MANAGED")
        self.assertTrue(updated.startswith("author intro"))
        self.assertTrue(updated.endswith("author close"))
        self.assertIn("facts", updated)

    def test_release_state_wording_conflict_is_detected_without_mutation(self):
        formal = make_release(prerelease=False, body="发布类型：预发布测试版")
        prerelease = make_release(prerelease=True, body="pre-release")
        self.assertTrue(sync.release_note_state_conflict(formal))
        self.assertFalse(sync.release_note_state_conflict(prerelease))

    def test_unmanaged_release_note_preview_reports_conflict_without_write(self):
        release = make_release(prerelease=False, body="发布类型：预发布测试版")
        record = {"tag": release["tag_name"], "prerelease": False, "publishedDate": "2026-10-11",
                  "apkVerificationStatus": "NOT_VERIFIED", "tagSha": COMMIT}
        statuses = sync.preview_release_note_updates(
            [release], {release["tag_name"]: record}, "CARPALY:RELEASE_NOTES"
        )
        self.assertEqual(statuses, ["v1.1.51: UNMANAGED_PRESERVED_STATUS_CONFLICT"])


class ReleaseSelectionTests(unittest.TestCase):
    def test_draft_release_is_excluded(self):
        self.assertEqual(sync.public_releases([make_release(draft=True)]), [])

    def test_release_without_publish_time_is_excluded(self):
        self.assertEqual(sync.public_releases([make_release(published="")]), [])

    def test_malformed_publish_time_is_excluded(self):
        self.assertEqual(sync.public_releases([make_release(published="not-date")]), [])

    def test_release_times_are_sorted_newest_first(self):
        older = make_release("v1.1.4", published="2026-10-10T00:00:00Z")
        newer = make_release("v1.1.51", published="2026-10-11T00:00:00Z")
        self.assertEqual([r["tag_name"] for r in sync.public_releases([older, newer])], ["v1.1.51", "v1.1.4"])

    def test_latest_formal_release_skips_newer_prerelease(self):
        formal = make_release("v1.1.51", published="2026-10-10T00:00:00Z")
        pre = make_release("v1.1.52", prerelease=True, published="2026-10-12T00:00:00Z")
        self.assertEqual(sync.latest_formal_release([pre, formal])["tag_name"], "v1.1.51")

    def test_no_formal_release_returns_none(self):
        self.assertIsNone(sync.latest_formal_release([make_release(prerelease=True)]))

    def test_unreleased_candidate_never_becomes_latest_release(self):
        self.assertEqual(sync.latest_formal_release([]), None)


class AssetAndVerificationTests(unittest.TestCase):
    def test_asset_url_must_match_repository_tag_and_filename(self):
        release = make_release()
        self.assertEqual(sync.release_assets(release, REPO)[0]["name"], "CarPaly-XingyueL-1.1.51.apk")

    def test_asset_with_other_repository_is_rejected(self):
        asset = make_release()["assets"][0]
        asset["browser_download_url"] = asset["browser_download_url"].replace(REPO, "attacker/repo")
        self.assertIsNone(sync.safe_asset_url(REPO, "v1.1.51", asset))

    def test_asset_with_wrong_tag_is_rejected(self):
        asset = make_release()["assets"][0]
        self.assertIsNone(sync.safe_asset_url(REPO, "v1.1.4", asset))

    def test_asset_with_non_github_host_is_rejected(self):
        asset = make_release()["assets"][0]
        asset["browser_download_url"] = asset["browser_download_url"].replace("github.com", "example.com")
        self.assertIsNone(sync.safe_asset_url(REPO, "v1.1.51", asset))

    def test_asset_name_path_traversal_is_rejected(self):
        asset = make_release()["assets"][0]
        asset["name"] = "../CarPaly.apk"
        self.assertIsNone(sync.safe_asset_url(REPO, "v1.1.51", asset))

    def test_asset_digest_requires_sha256(self):
        self.assertEqual(sync.asset_digest({"digest": f"sha256:{APK_SHA}"}), APK_SHA)
        self.assertIsNone(sync.asset_digest({"digest": "sha1:" + "a" * 40}))

    def test_release_tag_commit_requires_full_commit_sha(self):
        self.assertEqual(sync.release_tag_commits([{"name": "v1.1.51", "commit": {"sha": COMMIT}}]), {"v1.1.51": COMMIT})
        self.assertEqual(sync.release_tag_commits([{"name": "v1.1.51", "commit": {"sha": "short"}}]), {})

    def test_matching_verification_sidecar_passes(self):
        release = make_release()
        record = sync._verified_release_record(release, REPO, make_verification(release), SIGNER, LEDGER["applicationId"])
        self.assertEqual(record["apkVerificationStatus"], "PASS")
        self.assertEqual(record["verifiedApk"]["versionCode"], 39)

    def test_formal_release_note_channel_conflict_is_retained_as_public_fact(self):
        release = make_release(body="发布类型：预发布测试版")
        record = sync._verified_release_record(
            release, REPO, make_verification(release), SIGNER, LEDGER["applicationId"]
        )
        self.assertTrue(record["releaseNoteStateConflict"])
        summary = sync.render_release_summary([record])
        self.assertIn("说明状态冲突", summary)
        self.assertIn("保留原说明", summary)
        self.assertNotIn("预发布 | 2026", summary)

    def test_verification_sidecar_wrong_signer_fails(self):
        release = make_release()
        report = make_verification(release)
        report["signerCertificateSha256"] = "0" * 64
        record = sync._verified_release_record(release, REPO, report, SIGNER, LEDGER["applicationId"])
        self.assertEqual(record["apkVerificationStatus"], "FAIL")

    def test_verification_sidecar_wrong_package_fails(self):
        release = make_release()
        report = make_verification(release)
        report["packageName"] = "other.package"
        self.assertEqual(sync._verified_release_record(release, REPO, report, SIGNER, LEDGER["applicationId"])["apkVerificationStatus"], "FAIL")

    def test_verification_sidecar_wrong_version_fails(self):
        release = make_release()
        report = make_verification(release)
        report["versionName"] = "1.1.50"
        self.assertEqual(sync._verified_release_record(release, REPO, report, SIGNER, LEDGER["applicationId"])["apkVerificationStatus"], "FAIL")

    def test_verification_sidecar_wrong_asset_digest_fails(self):
        release = make_release()
        report = make_verification(release)
        release["assets"][0]["digest"] = "sha256:" + "c" * 64
        self.assertEqual(sync._verified_release_record(release, REPO, report, SIGNER, LEDGER["applicationId"])["apkVerificationStatus"], "FAIL")

    def test_verification_sidecar_requires_all_critical_checks(self):
        release = make_release()
        report = make_verification(release)
        report["checks"]["APK_SIGNATURE"] = "FAIL"
        self.assertEqual(sync._verified_release_record(release, REPO, report, SIGNER, LEDGER["applicationId"])["apkVerificationStatus"], "FAIL")

    def test_missing_verification_sidecar_does_not_claim_signature_verified(self):
        release = make_release()
        record = sync._verified_release_record(release, REPO, None, SIGNER, LEDGER["applicationId"])
        self.assertEqual(record["apkVerificationStatus"], "NOT_VERIFIED")
        self.assertIsNone(record["verifiedApk"])

    def test_verification_fetch_does_not_download_apk(self):
        release = make_release()
        release["assets"].append({
            "name": release["assets"][0]["name"] + ".verification.json",
            "browser_download_url": release["assets"][0]["browser_download_url"] + ".verification.json",
        })
        requested: list[str] = []
        sync.fetch_verifications([release], REPO, downloader=lambda url: requested.append(url) or {"status": "PASS"})
        self.assertEqual(len(requested), 1)
        self.assertTrue(requested[0].endswith(".verification.json"))
        self.assertFalse(requested[0].endswith(".apk"))


class RenderingTests(unittest.TestCase):
    def _records(self):
        release = make_release()
        tags = [{"name": "v1.1.51", "commit": {"sha": COMMIT}}]
        verifications = {"v1.1.51": make_verification(release)}
        return sync._released_records([release], tags, REPO, LEDGER, verifications)

    def test_summary_links_only_verified_latest_apk(self):
        rendered = sync.render_release_summary(self._records())
        self.assertIn("GitHub 最新正式 Release", rendered)
        self.assertIn("CarPaly-XingyueL-1.1.51.apk", rendered)
        self.assertIn(APK_SHA, rendered)

    def test_prerelease_label_is_explicit(self):
        release = make_release("v1.1.5", prerelease=True)
        records = sync._released_records([release], [], REPO, LEDGER, {})
        self.assertIn("预发布", sync.render_release_summary(records))

    def test_candidate_without_tag_has_no_public_download(self):
        rendered = sync.render_candidate(METADATA, LEDGER, set(), set())
        self.assertIn("尚无公开标签或 Release", rendered)
        self.assertNotIn("releases/download", rendered)

    def test_candidate_tag_without_release_is_not_called_published(self):
        tag = f"v{METADATA['candidate']['versionName']}"
        rendered = sync.render_candidate(METADATA, LEDGER, set(), {tag})
        self.assertIn("Git 标签已存在", rendered)
        self.assertNotIn("已存在 GitHub Release", rendered)

    def test_public_candidate_tag_is_not_rendered_as_local(self):
        tag = f"v{METADATA['candidate']['versionName']}"
        rendered = sync.render_candidate(METADATA, LEDGER, {tag}, {tag})
        self.assertIn("已存在 GitHub Release", rendered)

    def test_vehicle_feedback_preserves_user_reported_status(self):
        rendered = sync.render_vehicle_feedback(METADATA)
        self.assertIn("USER_REPORTED_FAIL", str(METADATA["vehicleFeedback"]))
        self.assertIn("未独立复现", rendered)
        self.assertIn("自动暂停", rendered)

    def test_english_vehicle_feedback_does_not_overclaim(self):
        rendered = sync.render_english_vehicle_feedback(METADATA)
        self.assertIn("User reported fail", rendered)
        self.assertIn("not independently reproduced", rendered)
        self.assertIn("NOT_TESTED", rendered)

    def test_downloads_do_not_advertise_local_candidate(self):
        rendered = sync.render_downloads(self._records(), METADATA, LEDGER)
        self.assertIn("CarPaly-XingyueL-1.1.51.apk", rendered)
        self.assertIn("尚未公开发布", rendered)
        self.assertEqual(rendered.count("releases/download"), 1)

    def test_changelog_uses_actual_release_metadata_and_separate_vehicle_status(self):
        rendered = sync.render_changelog(self._records(), METADATA, LEDGER)
        self.assertIn("v1.1.51", rendered)
        self.assertIn("Local Candidate (Not Published)", rendered)
        self.assertIn("NOT_TESTED", rendered)

    def test_release_notes_managed_block_contains_only_verified_artifact_facts(self):
        record = self._records()[0]
        rendered = sync.render_release_notes_managed_block(record)
        self.assertIn("formal Release", rendered)
        self.assertIn("NOT_TESTED", rendered)
        self.assertIn(SIGNER, rendered)

    def test_english_release_summary_reports_formal_note_conflict(self):
        release = make_release(body="Pre-release testing build")
        record = sync._verified_release_record(
            release, REPO, make_verification(release), SIGNER, LEDGER["applicationId"]
        )
        rendered = sync.render_english_releases([record], METADATA, LEDGER)
        self.assertIn("metadata conflict", rendered)
        self.assertIn("notes are preserved", rendered)


class MetadataAndFileTests(unittest.TestCase):
    def test_repository_metadata_and_markers_validate(self):
        self.assertEqual(validate_metadata(ROOT), [])

    def test_change_allowlist_excludes_unapproved_markdown(self):
        allowlist = json.loads((ROOT / "config/public-markdown-allowlist.json").read_text(encoding="utf-8"))["publicMarkdown"]
        self.assertIn("docs/RELEASE_AUTOMATION.md", allowlist)
        self.assertNotIn("docs/geely/vehicle-runtime-evidence.md", allowlist)

    def test_document_updates_replace_only_managed_regions(self):
        blocks = sync.render_blocks(metadata=METADATA, ledger=LEDGER, releases=[], tags=[], verifications={})
        updates = sync.prepare_document_updates(ROOT, METADATA, blocks)
        self.assertEqual(set(path.name for path in updates) - {"README.md", "CHANGELOG.md"}, set())

    def test_document_update_is_idempotent(self):
        blocks = sync.render_blocks(metadata=METADATA, ledger=LEDGER, releases=[], tags=[], verifications={})
        updated = sync.prepare_document_updates(ROOT, METADATA, blocks)
        fake_root = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(fake_root, ignore_errors=True))
        (fake_root / "README.md").write_text((ROOT / "README.md").read_text(encoding="utf-8"), encoding="utf-8")
        (fake_root / "CHANGELOG.md").write_text((ROOT / "CHANGELOG.md").read_text(encoding="utf-8"), encoding="utf-8")
        first = sync.prepare_document_updates(fake_root, METADATA, blocks)
        for path, text in first.items():
            path.write_text(text, encoding="utf-8")
        second = sync.prepare_document_updates(fake_root, METADATA, blocks)
        self.assertEqual(second, {})

    def test_required_marker_missing_fails_before_any_write(self):
        broken = METADATA.copy()
        broken["managedMarkers"] = dict(METADATA["managedMarkers"])
        broken["managedMarkers"]["readmeDownloads"] = "NO_SUCH_MARKER"
        blocks = sync.render_blocks(metadata=METADATA, ledger=LEDGER, releases=[], tags=[], verifications={})
        with self.assertRaises(sync.SyncError):
            sync.prepare_document_updates(ROOT, broken, blocks)


class GitHubApiAndMutationSafetyTests(unittest.TestCase):
    def test_default_transport_passes_timeout_by_keyword(self):
        with patch.object(sync.urllib.request, "urlopen", return_value=FakeResponse({"ok": True})) as urlopen:
            client = sync.GitHubClient(REPO)
            self.assertEqual(client.request("GET", "/repos/Qwy20040320/carpaly"), {"ok": True})
        self.assertEqual(urlopen.call_args.kwargs, {"timeout": sync.TIMEOUT_SECONDS})

    def test_http_error_does_not_echo_server_body_or_token(self):
        transport = QueueTransport([urllib.error.HTTPError("https://api.github.com", 403, "forbidden", {}, None)])
        client = sync.GitHubClient(REPO, token=SECRET, transport=transport)
        with self.assertRaises(sync.GitHubApiError) as raised:
            client.request("GET", "/repos/Qwy20040320/carpaly")
        self.assertNotIn(SECRET, str(raised.exception))
        self.assertIn("HTTP 403", str(raised.exception))

    def test_http_timeout_is_bounded(self):
        transport = QueueTransport([urllib.error.URLError("timeout")])
        client = sync.GitHubClient(REPO, transport=transport)
        with self.assertRaises(sync.SyncError):
            client.request("GET", "/repos/Qwy20040320/carpaly")

    def test_unsafe_api_paths_are_rejected(self):
        client = sync.GitHubClient(REPO, transport=QueueTransport([]))
        with self.assertRaises(sync.SyncError):
            client.request("GET", "/repos/../secrets")

    def test_about_already_in_sync_needs_no_admin_token(self):
        class Reader:
            repository = REPO
            def get_repo(self): return {"description": METADATA["repository"]["description"]}
        status = sync.sync_repository_description(Reader(), METADATA["repository"]["description"], None, allow_write=True)
        self.assertEqual(status, "IN_SYNC")

    def test_about_mismatch_without_token_is_proposed_only(self):
        class Reader:
            repository = REPO
            def get_repo(self): return {"description": "old description"}
        self.assertEqual(
            sync.sync_repository_description(Reader(), "new", None, allow_write=False), "PROPOSED_ONLY"
        )

    def test_about_mismatch_without_admin_secret_fails_closed(self):
        class Reader:
            repository = REPO
            def get_repo(self): return {"description": "old description"}
        self.assertEqual(
            sync.sync_repository_description(Reader(), "new", None, allow_write=True),
            "BLOCKED_ADMIN_TOKEN_MISSING",
        )

    def test_about_patch_changes_description_only(self):
        transport = QueueTransport([{"message": "ok"}])
        write_client = sync.GitHubClient(REPO, token="admin-token", transport=transport)
        class Reader:
            repository = REPO
            def get_repo(self): return {"description": "old"}
        with patch.object(sync, "GitHubClient", return_value=write_client):
            status = sync.sync_repository_description(Reader(), "new", "admin-token", allow_write=True)
        self.assertEqual(status, "UPDATED_DESCRIPTION_ONLY")
        method, _, payload = transport.calls[0]
        self.assertEqual(method, "PATCH")
        self.assertEqual(payload, {"description": "new"})

    def test_existing_docs_pr_is_not_duplicated(self):
        transport = QueueTransport([[{"number": 12, "title": "title", "body": "body"}]])
        client = sync.GitHubClient(REPO, token="test", transport=transport)
        self.assertEqual(sync.ensure_docs_pull_request(client, "automation/docs", "main", "title", "body"), "UNCHANGED #12")
        self.assertEqual(len(transport.calls), 1)

    def test_existing_docs_pr_body_is_updated_idempotently(self):
        transport = QueueTransport([[{"number": 12, "title": "old", "body": "old"}], {"number": 12}])
        client = sync.GitHubClient(REPO, token="test", transport=transport)
        self.assertEqual(sync.ensure_docs_pull_request(client, "automation/docs", "main", "new", "body"), "UPDATED #12")
        self.assertEqual(transport.calls[1][0], "PATCH")

    def test_missing_docs_pr_is_created_once(self):
        transport = QueueTransport([[], {"number": 13}])
        client = sync.GitHubClient(REPO, token="test", transport=transport)
        self.assertEqual(sync.ensure_docs_pull_request(client, "automation/docs", "main", "new", "body"), "CREATED #13")
        self.assertEqual(transport.calls[1][0], "POST")


class WorkflowContractTests(unittest.TestCase):
    def test_android_release_requires_reviewed_main_intent_and_has_no_manual_or_tag_release_path(self):
        workflow = (ROOT / ".github/workflows/android.yml").read_text(encoding="utf-8")
        self.assertNotIn("publish_authenticated_release", workflow)
        self.assertIn("default: false", workflow)
        self.assertIn("needs: [check, release_intent, release_authorization]", workflow)
        self.assertIn("needs.check.result == 'success'", workflow)
        self.assertIn("needs.release_intent.outputs.should_publish == 'true'", workflow)
        self.assertIn("needs.release_authorization.result == 'success'", workflow)
        self.assertIn("github.event_name == 'push' && github.ref == 'refs/heads/main'", workflow)
        self.assertNotIn("tags: ['v1.*']", workflow)

    def test_release_job_uses_protected_environment_and_tag_on_main_check(self):
        workflow = (ROOT / ".github/workflows/android.yml").read_text(encoding="utf-8")
        release_job = workflow.split("  authenticated_release:", 1)[1]
        self.assertIn("environment: mfi-public-release", release_job)
        self.assertIn("git merge-base --is-ancestor", release_job)

    def test_full_ci_runs_for_prs_while_release_intent_remains_main_only(self):
        workflow = (ROOT / ".github/workflows/android.yml").read_text(encoding="utf-8")
        gate = workflow.split("  release_intent:", 1)[1].split("  release_authorization:", 1)[0]
        release_job = workflow.split("  authenticated_release:", 1)[1].split("  publication_follow_up:", 1)[0]
        release_job = workflow.split("  authenticated_release:", 1)[1].split("  publication_follow_up:", 1)[0]
        intent_source = (ROOT / "scripts/release_intent.py").read_text(encoding="utf-8")
        self.assertIn("name: Run full CI and gate an explicit release intent", gate)
        self.assertIn("github.event_name != 'workflow_dispatch'", gate)
        self.assertIn("inputs.verify_release_signer_only != true", gate)
        self.assertIn("./gradlew :shared:testDebugUnitTest", gate)
        self.assertIn("timeout-minutes: 30", gate)
        self.assertIn("event != \"push\" or branch != \"main\"", intent_source)
        self.assertIn("github.event_name == 'push' && github.ref == 'refs/heads/main'", release_job)
        self.assertIn("needs.release_intent.result == 'success'", release_job)
        self.assertNotIn("environment:", gate)
        self.assertNotIn("secrets.", gate)
        self.assertNotIn("inputs.publish_authenticated_release", release_job)
        self.assertIn("persist-credentials: false", gate)

    def test_post_release_workflows_are_dispatched_with_narrow_permissions(self):
        workflow = (ROOT / ".github/workflows/android.yml").read_text(encoding="utf-8")
        follow_up = workflow.split("  publication_follow_up:", 1)[1]
        self.assertIn("actions: write", follow_up)
        self.assertIn("contents: read", follow_up)
        self.assertIn("scripts/dispatch_release_followups.py", follow_up)
        self.assertIn("--timeout-seconds 2400", follow_up)
        self.assertIn('gh api "repos/$GH_REPO/commits/main" --jq .sha', follow_up)
        dispatcher = (ROOT / "scripts/dispatch_release_followups.py").read_text(encoding="utf-8")
        self.assertIn("pages.yml", dispatcher)
        self.assertIn("release-docs-sync.yml", dispatcher)
        self.assertIn("display_title", dispatcher)
        self.assertIn("head_sha", dispatcher)
        self.assertNotIn("secrets.MFI_", follow_up)
        self.assertNotIn("RELEASE_KEYSTORE_BASE64", follow_up)

    def test_follow_up_workflows_accept_correlation_id(self):
        for workflow_path, title in (
            (".github/workflows/pages.yml", "CarPaly Pages deploy"),
            (".github/workflows/release-docs-sync.yml", "CarPaly release docs sync"),
        ):
            workflow = (ROOT / workflow_path).read_text(encoding="utf-8")
            self.assertIn("dispatch_id:", workflow)
            self.assertIn(title, workflow)

    def test_pages_tag_events_do_not_conflict_with_main_restricted_environment(self):
        pages = (ROOT / ".github/workflows/pages.yml").read_text(encoding="utf-8")
        android = (ROOT / ".github/workflows/android.yml").read_text(encoding="utf-8")
        dispatcher = (ROOT / "scripts/dispatch_release_followups.py").read_text(encoding="utf-8")
        self.assertIn("branches: [main]", pages)
        self.assertIn("workflow_dispatch:", pages)
        self.assertNotIn("\n  release:\n", pages)
        self.assertIn("github.ref == 'refs/heads/main'", pages)
        self.assertIn("scripts/dispatch_release_followups.py", android)
        self.assertIn("pages.yml", dispatcher)

    def test_signer_preflight_is_manual_main_only_and_read_only(self):
        workflow = (ROOT / ".github/workflows/android.yml").read_text(encoding="utf-8")
        check_job = workflow.split("jobs:", 1)[1].split("  release_intent:", 1)[0]
        preflight_job = workflow.split("  release_signer_preflight:", 1)[1].split(
            "  authenticated_release:", 1
        )[0]
        self.assertIn("inputs.verify_release_signer_only != true", check_job)
        self.assertIn("inputs.verify_release_signer_only == true", preflight_job)
        self.assertNotIn("publish_authenticated_release", preflight_job)
        self.assertIn("github.ref == 'refs/heads/main'", preflight_job)
        self.assertNotIn("needs: check", preflight_job)
        self.assertIn("environment: mfi-public-release", preflight_job)
        self.assertIn("contents: read", preflight_job)
        self.assertIn("scripts/release_signing_preflight.py", preflight_job)
        for forbidden in (
            "contents: write",
            "GH_TOKEN",
            "secrets.MFI_",
            "release create",
            "assembleRelease",
            "./gradlew",
        ):
            self.assertNotIn(forbidden, preflight_job)
        self.assertIn("default: false", workflow)

    def test_pr_check_job_does_not_read_release_environment_secrets(self):
        workflow = (ROOT / ".github/workflows/android.yml").read_text(encoding="utf-8")
        check_job = workflow.split("jobs:", 1)[1].split("  release_intent:", 1)[0]
        self.assertNotIn("secrets.RELEASE_", check_job)
        self.assertNotIn("secrets.MFI_", check_job)

    def test_docs_sync_is_triggered_by_release_lifecycle_and_schedule(self):
        workflow = (ROOT / ".github/workflows/release-docs-sync.yml").read_text(encoding="utf-8")
        self.assertIn("published, edited, deleted", workflow)
        self.assertIn("schedule:", workflow)
        self.assertIn("workflow_dispatch:", workflow)
        self.assertNotIn("workflow_run:", workflow)
        self.assertIn("dispatch_id:", workflow)

    def test_docs_sync_does_not_trigger_on_its_own_push_or_pr(self):
        workflow = (ROOT / ".github/workflows/release-docs-sync.yml").read_text(encoding="utf-8")
        self.assertNotIn("pull_request:", workflow)
        self.assertNotIn("push:", workflow)

    def test_docs_sync_never_uses_signing_or_mfi_secrets(self):
        workflow = (ROOT / ".github/workflows/release-docs-sync.yml").read_text(encoding="utf-8")
        for secret in ("RELEASE_KEYSTORE_BASE64", "RELEASE_STORE_PASSWORD", "RELEASE_KEY_PASSWORD", "MFI_IDENTITY_PK8_BASE64", "MFI_CERTIFICATE_P7B_BASE64"):
            self.assertNotIn(secret, workflow)
        self.assertNotIn("mfi-public-release", workflow)
        self.assertNotIn("RELEASE_SIGNING_CERT_SHA256", workflow)

    def test_docs_sync_has_only_document_and_pr_write_permissions(self):
        workflow = (ROOT / ".github/workflows/release-docs-sync.yml").read_text(encoding="utf-8")
        self.assertIn("contents: write", workflow)
        self.assertIn("pull-requests: write", workflow)
        self.assertNotIn("actions: write", workflow)

    def test_docs_sync_never_force_pushes_or_auto_merges(self):
        workflow = (ROOT / ".github/workflows/release-docs-sync.yml").read_text(encoding="utf-8")
        self.assertIn("git push --set-upstream", workflow)
        self.assertNotIn("--force", workflow)
        self.assertNotIn("--auto", workflow)
        self.assertNotIn("gh pr merge", workflow)

    def test_docs_sync_uses_dedicated_branch_not_main(self):
        workflow = (ROOT / ".github/workflows/release-docs-sync.yml").read_text(encoding="utf-8")
        self.assertIn("DOCS_BRANCH: automation/release-docs-sync", workflow)
        self.assertIn('git push --set-upstream origin "$DOCS_BRANCH"', workflow)
        self.assertNotIn('git push origin main', workflow)

    def test_docs_sync_stages_only_readme_and_changelog(self):
        workflow = (ROOT / ".github/workflows/release-docs-sync.yml").read_text(encoding="utf-8")
        self.assertIn("git add -- README.md CHANGELOG.md", workflow)
        self.assertIn("Unexpected generated file", workflow)

    def test_docs_check_is_read_only_and_runs_offline_tests(self):
        workflow = (ROOT / ".github/workflows/release-docs-check.yml").read_text(encoding="utf-8")
        self.assertIn("contents: read", workflow)
        self.assertIn("scripts.test_release_docs_sync", workflow)
        self.assertIn("scripts.test_release_signing_preflight", workflow)
        self.assertIn("scripts.test_release_intent", workflow)
        self.assertNotIn("contents: write", workflow)
        self.assertNotIn("secrets.RELEASE_", workflow)
        self.assertNotIn("secrets.MFI_", workflow)
        self.assertIn('ruby -e \'require "yaml"', workflow)

    def test_action_references_remain_immutable(self):
        checker = ROOT / "scripts/check_workflow_action_pins.py"
        self.assertTrue(checker.is_file())
        self.assertEqual(subprocess.run([sys.executable, str(checker)], cwd=ROOT, capture_output=True).returncode, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
