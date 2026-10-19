import unittest

from scripts.release_automation import (
    check_auto_merge,
    classify_changes,
    classify_draft_release,
    public_upload_guard,
    validate_release_intent,
)


REQUIRED = ["android / check", "release-docs-check / check"]


def fixtures():
    return {
        "repository": {"full_name": "Qwy20040320/carpaly", "allow_auto_merge": True},
        "pull_request": {
            "state": "OPEN", "draft": False, "base_ref": "main",
            "head_repo": "Qwy20040320/carpaly", "mergeable": True,
            "head_sha": "abc123", "author_login": "Qwy20040320",
            "author_association": "OWNER", "unresolved_review_threads": False,
            "independent_approvals": [],
        },
        "protection": {
            "active": True, "target": "main", "allows_force_pushes": False,
            "allows_deletions": False, "bypass_actors": [],
            "required_checks": REQUIRED, "required_approving_review_count": 0,
        },
        "checks": {"head_sha": "abc123", "contexts": {
            name: {"status": "completed", "conclusion": "success"} for name in REQUIRED
        }},
        "review_policy": {"mode": "single_maintainer", "authorizedMergers": ["Qwy20040320"]},
    }


class ReleaseAutomationTests(unittest.TestCase):
    def decision(self, paths=None, **overrides):
        data = fixtures()
        data.update(overrides)
        return check_auto_merge(**data, changed_paths=paths or [], expected_head_sha="abc123", requester_login="Qwy20040320")

    def test_auto_merge_allowed_only_for_fully_verified_low_risk_pr(self):
        self.assertTrue(self.decision(paths=["docs/geely/README_ZH.md"]).allowed)

    def test_auto_merge_disabled_repository_fails_closed(self):
        data = fixtures(); data["repository"]["allow_auto_merge"] = False
        self.assertIn("repository-auto-merge-disabled", self.decision(**data).reasons)

    def test_stale_head_or_checks_fail_closed(self):
        data = fixtures(); data["checks"]["head_sha"] = "newer"
        self.assertIn("head-sha-changed-or-checks-stale", self.decision(**data).reasons)

    def test_unfinished_required_check_fails_closed(self):
        data = fixtures(); data["checks"]["contexts"][REQUIRED[0]]["status"] = "in_progress"
        self.assertTrue(any(r.startswith("required-check-not-passed:") for r in self.decision(**data).reasons))

    def test_failed_required_check_fails_closed(self):
        data = fixtures(); data["checks"]["contexts"][REQUIRED[0]]["conclusion"] = "failure"
        self.assertTrue(any(r.startswith("required-check-not-passed:") for r in self.decision(**data).reasons))

    def test_draft_pr_cannot_auto_merge(self):
        data = fixtures(); data["pull_request"]["draft"] = True
        self.assertIn("draft-pull-request", self.decision(**data).reasons)

    def test_fork_pr_cannot_auto_merge(self):
        data = fixtures(); data["pull_request"]["head_repo"] = "unknown/fork"
        self.assertIn("fork-pull-request", self.decision(**data).reasons)

    def test_untrusted_author_cannot_auto_merge(self):
        data = fixtures(); data["pull_request"]["author_login"] = "external"
        self.assertIn("untrusted-pr-author", self.decision(**data).reasons)

    def test_unauthorized_requester_cannot_enable_native_auto_merge(self):
        data = fixtures()
        self.assertIn("unauthorized-auto-merge-requester", check_auto_merge(
            **data, changed_paths=[], expected_head_sha="abc123", requester_login="unknown"
        ).reasons)

    def test_merge_conflict_cannot_auto_merge(self):
        data = fixtures(); data["pull_request"]["mergeable"] = False
        self.assertIn("mergeability-not-confirmed", self.decision(**data).reasons)

    def test_high_risk_paths_require_human_review(self):
        for path in (".github/workflows/android.yml", "mobile/build.gradle.kts", "config/android-version-ledger.json"):
            with self.subTest(path=path):
                self.assertIn("high-risk-changes-require-human-review", self.decision(paths=[path]).reasons)

    def test_multi_maintainer_requires_independent_approval(self):
        data = fixtures(); data["review_policy"] = {"mode": "multi_maintainer", "authorizedMergers": ["Qwy20040320"], "minimumApprovals": 1}
        self.assertIn("independent-approval-missing", self.decision(**data).reasons)

    def test_author_cannot_satisfy_independent_approval(self):
        data = fixtures(); data["review_policy"] = {"mode": "multi_maintainer", "authorizedMergers": ["Qwy20040320"], "minimumApprovals": 1}
        data["pull_request"]["independent_approvals"] = ["Qwy20040320"]
        self.assertIn("independent-approval-missing", self.decision(**data).reasons)

    def test_multi_maintainer_accepts_independent_approval(self):
        data = fixtures(); data["review_policy"] = {"mode": "multi_maintainer", "authorizedMergers": ["Qwy20040320"], "minimumApprovals": 1}
        data["pull_request"]["independent_approvals"] = ["Reviewer"]
        self.assertTrue(self.decision(**data).allowed)

    def test_missing_or_unsafe_main_protection_fails_closed(self):
        data = fixtures(); data["protection"]["allows_force_pushes"] = True
        self.assertIn("main-protection-allows-destructive-update", self.decision(**data).reasons)

    def test_unresolved_or_unavailable_review_threads_block_auto_merge(self):
        data = fixtures(); data["pull_request"]["unresolved_review_threads"] = True
        self.assertIn("review-threads-unresolved-or-unavailable", self.decision(**data).reasons)

    def test_bypass_actor_fails_closed(self):
        data = fixtures(); data["protection"]["bypass_actors"] = ["admin"]
        self.assertIn("main-protection-has-bypass-actors", self.decision(**data).reasons)

    def test_unknown_required_checks_fail_closed(self):
        data = fixtures(); data["protection"]["required_checks"] = ["unknown"]
        self.assertTrue(any(r.endswith(":unknown") for r in self.decision(**data).reasons))

    def test_draft_is_only_reused_when_metadata_only_and_marked(self):
        draft = {"tag_name": "v1.1.57", "draft": True, "target_commitish": "abc123", "body": "marker", "assets": []}
        self.assertEqual("SAFE_DRAFT_REUSE", classify_draft_release(draft, expected_tag="v1.1.57", expected_commit="abc123", marker="marker"))

    def test_published_release_is_immutable(self):
        draft = {"tag_name": "v1.1.57", "draft": False}
        self.assertEqual("PUBLISHED_IMMUTABLE", classify_draft_release(draft, expected_tag="v1.1.57", expected_commit="abc123", marker="marker"))

    def test_wrong_tag_source_marker_or_assets_block_draft_reuse(self):
        base = {"tag_name": "v1.1.57", "draft": True, "target_commitish": "abc123", "body": "marker", "assets": []}
        for field, value, expected in (("tag_name", "v1.1.58", "BLOCKED_TAG_MISMATCH"), ("target_commitish", "wrong", "BLOCKED_SOURCE_MISMATCH"), ("body", "manual", "BLOCKED_UNRECOGNIZED_DRAFT"), ("assets", [{"name": "x.apk"}], "BLOCKED_DRAFT_HAS_ASSETS")):
            with self.subTest(field=field):
                self.assertEqual(expected, classify_draft_release({**base, field: value}, expected_tag="v1.1.57", expected_commit="abc123", marker="marker"))

    def test_no_release_requires_authenticated_publisher_to_create(self):
        self.assertEqual("CREATE_REQUIRED_BY_AUTHENTICATED_PUBLISHER", classify_draft_release(None, expected_tag="v1.1.57", expected_commit="abc123", marker="marker"))

    def test_public_upload_guard_blocks_apk_and_credential_containers(self):
        self.assertFalse(public_upload_guard(["CarPaly.apk"]).allowed)
        self.assertFalse(public_upload_guard(["identity.pk8"]).allowed)
        self.assertTrue(public_upload_guard(["BUILD_REPORT.md", "SHA256SUMS.txt"]).allowed)

    def test_disabled_or_non_main_intent_never_authorizes_publisher(self):
        self.assertFalse(validate_release_intent({"enabled": False}, branch="main", event="push").allowed)
        self.assertFalse(validate_release_intent({"enabled": True}, branch="feature/x", event="push").allowed)
        self.assertFalse(validate_release_intent({"enabled": True}, branch="main", event="pull_request").allowed)

    def test_signing_workflow_and_ledger_paths_are_risky(self):
        self.assertEqual((".github/workflows/android.yml", "mobile/build.gradle.kts"), classify_changes(["mobile/build.gradle.kts", ".github/workflows/android.yml"]))

    def test_release_policy_documentation_requires_human_review(self):
        self.assertTrue(classify_changes(["docs/RELEASE_SIGNING_GUIDE.md"]))

    def test_runtime_code_and_unreviewed_markdown_require_human_review(self):
        self.assertTrue(classify_changes(["common/src/main/A.kt"]))
        self.assertTrue(classify_changes(["docs/local-not-in-allowlist.md"]))


if __name__ == "__main__":
    unittest.main()
