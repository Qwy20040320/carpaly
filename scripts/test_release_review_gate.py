from __future__ import annotations

import unittest

from scripts.release_review_gate import ReleaseReviewError, verify_approved_merge


COMMIT = "a" * 40


def pull_request(**overrides):
    return {
        "number": 42,
        "state": "closed",
        "merged_at": "2026-10-12T01:02:03Z",
        "merge_commit_sha": COMMIT,
        "base": {"ref": "main"},
        **overrides,
    }


def details(**overrides):
    return {
        "number": 42,
        "baseRefName": "main",
        "mergedAt": "2026-10-12T01:02:03Z",
        "isDraft": False,
        "reviewDecision": "APPROVED",
        **overrides,
    }


class ReleaseReviewGateTests(unittest.TestCase):
    def test_approved_merged_main_pr_passes(self):
        self.assertEqual(
            verify_approved_merge(
                commit=COMMIT,
                associated_pull_requests=[pull_request()],
                pull_request_details=details(),
            ),
            42,
        )

    def test_direct_main_push_without_associated_pr_fails(self):
        with self.assertRaisesRegex(ReleaseReviewError, "exactly one merged PR"):
            verify_approved_merge(commit=COMMIT, associated_pull_requests=[], pull_request_details=details())

    def test_wrong_commit_or_base_fails(self):
        for item in (
            pull_request(merge_commit_sha="b" * 40),
            pull_request(base={"ref": "release"}),
            pull_request(merged_at=None),
            pull_request(state="open"),
        ):
            with self.subTest(item=item), self.assertRaises(ReleaseReviewError):
                verify_approved_merge(commit=COMMIT, associated_pull_requests=[item], pull_request_details=details())

    def test_unapproved_draft_or_unmerged_pull_request_fails(self):
        for override in (
            {"reviewDecision": "REVIEW_REQUIRED"},
            {"reviewDecision": "CHANGES_REQUESTED"},
            {"isDraft": True},
            {"mergedAt": None},
            {"baseRefName": "feature"},
        ):
            with self.subTest(override=override), self.assertRaises(ReleaseReviewError):
                verify_approved_merge(
                    commit=COMMIT,
                    associated_pull_requests=[pull_request()],
                    pull_request_details=details(**override),
                )

    def test_ambiguous_associated_pull_requests_fail(self):
        with self.assertRaisesRegex(ReleaseReviewError, "exactly one merged PR"):
            verify_approved_merge(
                commit=COMMIT,
                associated_pull_requests=[pull_request(), pull_request(number=43)],
                pull_request_details=details(),
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
