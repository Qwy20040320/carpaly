from __future__ import annotations

import unittest

from scripts.release_review_gate import ReleaseReviewError, verify_release_merge


COMMIT = "a" * 40
HEAD = "b" * 40
REPOSITORY = "Qwy20040320/carpaly"
POLICY = {
    "schemaVersion": 1,
    "repository": REPOSITORY,
    "mainBranch": "main",
    "mainRulesetName": "Protect main - CarPaly",
    "mode": "single_maintainer",
    "authorizedMergers": ["Qwy20040320"],
    "minimumIndependentApprovals": 1,
}


def ruleset(*, approvals: int = 0, enforcement: str = "active") -> dict:
    return {
        "name": "Protect main - CarPaly",
        "enforcement": enforcement,
        "target": "branch",
        "conditions": {"ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []}},
        "rules": [
            {"type": "deletion"},
            {"type": "non_fast_forward"},
            {"type": "pull_request", "parameters": {
                "required_approving_review_count": approvals,
                "required_review_thread_resolution": True,
            }},
            {"type": "required_status_checks", "parameters": {
                "required_status_checks": [{
                    "context": "Run full CI and gate an explicit release intent",
                }],
            }},
        ],
    }


def ruleset_suite(*, after_sha: str = COMMIT, ref: str = "refs/heads/main", result: str = "pass",
                 enforcement: str = "active", rule_result: str = "pass") -> dict:
    return {
        "id": 73,
        "after_sha": after_sha,
        "ref": ref,
        "result": result,
        "rule_evaluations": [{
            "rule_source": {"type": "ruleset", "id": 7, "name": "Protect main - CarPaly"},
            "enforcement": enforcement,
            "result": rule_result,
        }],
    }


def pull_request(**overrides) -> dict:
    return {
        "number": 42,
        "state": "closed",
        "merged_at": "2026-10-12T01:02:03Z",
        "merge_commit_sha": COMMIT,
        "base": {"ref": "main", "repo": {"full_name": REPOSITORY}},
        **overrides,
    }


def details(**overrides) -> dict:
    return {
        "number": 42,
        "state": "closed",
        "merged_at": "2026-10-12T01:02:03Z",
        "merge_commit_sha": COMMIT,
        "base": {"ref": "main", "repo": {"full_name": REPOSITORY}},
        "head": {"ref": "feature/release", "repo": {"full_name": REPOSITORY}, "sha": HEAD},
        "draft": False,
        "user": {"login": "Qwy20040320"},
        "merged_by": {"login": "Qwy20040320", "type": "User"},
        "reviewDecision": "",
        **overrides,
    }


def verify(**overrides) -> tuple[int, str]:
    args = {
        "commit": COMMIT,
        "associated_pull_requests": [pull_request()],
        "pull_request_details": details(),
        "reviews": [],
        "ruleset": ruleset(),
        "ruleset_suite": ruleset_suite(),
        "policy": POLICY,
        "default_branch": "main",
        "ci_conclusion": "success",
    }
    args.update(overrides)
    return verify_release_merge(**args)


class ReleaseReviewGateTests(unittest.TestCase):
    def test_single_maintainer_requires_authorized_manual_merge_but_not_approval(self):
        self.assertEqual(verify(), (42, "single_maintainer"))

    def test_zero_approval_ruleset_is_explicitly_bound_to_single_maintainer_mode(self):
        multi = {**POLICY, "mode": "multi_maintainer"}
        with self.assertRaisesRegex(ReleaseReviewError, "approval requirement"):
            verify(policy=multi)

    def test_multi_maintainer_requires_current_independent_approval(self):
        multi = {**POLICY, "mode": "multi_maintainer"}
        current_ruleset = ruleset(approvals=1)
        approved = [{
            "state": "APPROVED", "user": {"login": "independent-reviewer"},
            "commit_id": HEAD, "submitted_at": "2026-10-12T00:00:00Z",
        }]
        approved_details = details(reviewDecision="APPROVED")
        self.assertEqual(
            verify(policy=multi, ruleset=current_ruleset, reviews=approved,
                   pull_request_details=approved_details),
            (42, "multi_maintainer"),
        )

    def test_multi_maintainer_rejects_self_stale_or_missing_approval(self):
        multi = {**POLICY, "mode": "multi_maintainer"}
        current_ruleset = ruleset(approvals=1)
        approved_details = details(reviewDecision="APPROVED")
        for review in (
            {"state": "APPROVED", "user": {"login": "Qwy20040320"},
             "commit_id": HEAD, "submitted_at": "2026-10-12T00:00:00Z"},
            {"state": "APPROVED", "user": {"login": "independent-reviewer"},
             "commit_id": "c" * 40, "submitted_at": "2026-10-12T00:00:00Z"},
            {"state": "CHANGES_REQUESTED", "user": {"login": "independent-reviewer"},
             "commit_id": HEAD, "submitted_at": "2026-10-12T00:00:00Z"},
        ):
            with self.subTest(review=review), self.assertRaisesRegex(ReleaseReviewError, "independent approval"):
                verify(policy=multi, ruleset=current_ruleset, reviews=[review],
                       pull_request_details=approved_details)
        with self.assertRaisesRegex(ReleaseReviewError, "reviewDecision"):
            verify(policy=multi, ruleset=current_ruleset, reviews=[{
                "state": "APPROVED", "user": {"login": "independent-reviewer"},
                "commit_id": HEAD, "submitted_at": "2026-10-12T00:00:00Z",
            }], pull_request_details=details())

    def test_direct_push_without_associated_pr_fails(self):
        with self.assertRaisesRegex(ReleaseReviewError, "exactly one merged PR"):
            verify(associated_pull_requests=[])

    def test_wrong_commit_base_source_or_ambiguous_pr_fails(self):
        for associated in (
            [pull_request(merge_commit_sha="c" * 40)],
            [pull_request(base={"ref": "release", "repo": {"full_name": REPOSITORY}})],
            [pull_request(merged_at=None)],
            [pull_request(state="open")],
            [pull_request(), pull_request(number=43)],
        ):
            with self.subTest(associated=associated), self.assertRaises(ReleaseReviewError):
                verify(associated_pull_requests=associated)

    def test_draft_fork_or_unauthorized_merge_fails(self):
        for override in (
            {"draft": True},
            {"head": {"ref": "feature/fork", "repo": {"full_name": "attacker/carpaly"}, "sha": HEAD}},
            {"merged_by": {"login": "unlisted-user", "type": "User"}},
            {"merged_by": {"login": "Qwy20040320", "type": "Bot"}},
            {"base": {"ref": "main", "repo": {"full_name": "someone/else"}}},
        ):
            with self.subTest(override=override), self.assertRaises(ReleaseReviewError):
                verify(pull_request_details=details(**override))

    def test_branch_ruleset_and_exact_ci_are_mandatory(self):
        for rule, branch, conclusion in (
            (ruleset(enforcement="evaluate"), "main", "success"),
            (ruleset(approvals=1), "main", "success"),
            (ruleset() | {"conditions": {"ref_name": {"include": ["refs/heads/release"], "exclude": []}}},
             "main", "success"),
            (ruleset() | {"rules": [{"type": "pull_request"}]}, "main", "success"),
            (ruleset(), "develop", "success"),
            (ruleset(), "main", "failure"),
        ):
            with self.subTest(rule=rule, branch=branch, conclusion=conclusion), self.assertRaises(ReleaseReviewError):
                verify(ruleset=rule, default_branch=branch, ci_conclusion=conclusion)

    def test_exact_commit_must_have_active_non_bypassed_ruleset_evaluation(self):
        for suite in (
            ruleset_suite(result="bypass"),
            ruleset_suite(after_sha="c" * 40),
            ruleset_suite(ref="refs/heads/feature"),
            ruleset_suite(enforcement="evaluate"),
            ruleset_suite(rule_result="fail"),
            {"after_sha": COMMIT, "ref": "refs/heads/main", "result": "pass"},
        ):
            with self.subTest(suite=suite), self.assertRaises(ReleaseReviewError):
                verify(ruleset_suite=suite)

    def test_malformed_policy_or_commit_fails_closed(self):
        for policy in (
            {**POLICY, "mode": "automatic"},
            {**POLICY, "authorizedMergers": []},
            {**POLICY, "mainRulesetName": ""},
        ):
            with self.subTest(policy=policy), self.assertRaises(ReleaseReviewError):
                verify(policy=policy)
        with self.assertRaisesRegex(ReleaseReviewError, "full lowercase commit SHA"):
            verify(commit="A" * 40)


if __name__ == "__main__":
    unittest.main(verbosity=2)
