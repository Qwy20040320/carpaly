#!/usr/bin/env python3
"""Fail-closed release authorization for an exact main commit merged by an allowed human."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Sequence


SHA = re.compile(r"^[0-9a-f]{40}$")
LOGIN = re.compile(r"^[A-Za-z0-9-]{1,39}$")
REQUIRED_CHECK = "Run full CI and gate an explicit release intent"


class ReleaseReviewError(ValueError):
    pass


def _validate_policy(policy: Any) -> tuple[str, set[str], str, int]:
    if not isinstance(policy, dict) or policy.get("schemaVersion") != 1:
        raise ReleaseReviewError("Release review policy is missing or has an unsupported schema")
    mode = policy.get("mode")
    if mode not in {"single_maintainer", "multi_maintainer"}:
        raise ReleaseReviewError("Release review policy must explicitly choose a supported maintainer mode")
    if policy.get("repository") != "Qwy20040320/carpaly" or policy.get("mainBranch") != "main":
        raise ReleaseReviewError("Release review policy targets an unexpected repository or branch")
    raw_mergers = policy.get("authorizedMergers")
    if not isinstance(raw_mergers, list) or not raw_mergers or any(
        not isinstance(login, str) or not LOGIN.fullmatch(login) for login in raw_mergers
    ):
        raise ReleaseReviewError("Release review policy has no valid authorized human merger list")
    mergers = {login.casefold() for login in raw_mergers}
    ruleset_name = policy.get("mainRulesetName")
    if not isinstance(ruleset_name, str) or not ruleset_name.strip():
        raise ReleaseReviewError("Release review policy does not identify the main branch ruleset")
    minimum_approvals = policy.get("minimumIndependentApprovals")
    if isinstance(minimum_approvals, bool) or not isinstance(minimum_approvals, int) or minimum_approvals < 1:
        raise ReleaseReviewError("Multi-maintainer approval threshold must be a positive integer")
    return mode, mergers, ruleset_name, minimum_approvals


def _verify_main_ruleset(ruleset: Any, *, name: str, mode: str, default_branch: str) -> None:
    if not isinstance(ruleset, dict) or ruleset.get("name") != name:
        raise ReleaseReviewError("Could not prove the configured main branch ruleset")
    if default_branch != "main" or ruleset.get("enforcement") != "active" or ruleset.get("target") != "branch":
        raise ReleaseReviewError("Main branch is not covered by an active branch ruleset")
    conditions = ruleset.get("conditions")
    ref_name = conditions.get("ref_name") if isinstance(conditions, dict) else None
    included = ref_name.get("include") if isinstance(ref_name, dict) else None
    excluded = ref_name.get("exclude") if isinstance(ref_name, dict) else None
    if not isinstance(included, list) or "~DEFAULT_BRANCH" not in included or excluded != []:
        raise ReleaseReviewError("Active ruleset does not unambiguously target the default main branch")
    rules = ruleset.get("rules")
    if not isinstance(rules, list):
        raise ReleaseReviewError("Main ruleset does not expose its protected rules")
    pull_rules = [item for item in rules if isinstance(item, dict) and item.get("type") == "pull_request"]
    check_rules = [item for item in rules if isinstance(item, dict) and item.get("type") == "required_status_checks"]
    types = {item.get("type") for item in rules if isinstance(item, dict)}
    if len(pull_rules) != 1 or len(check_rules) != 1 or not {"deletion", "non_fast_forward"}.issubset(types):
        raise ReleaseReviewError("Main ruleset must require PRs and status checks and prohibit delete/force-push")
    pull_parameters = pull_rules[0].get("parameters")
    checks_parameters = check_rules[0].get("parameters")
    if not isinstance(pull_parameters, dict) or not isinstance(checks_parameters, dict):
        raise ReleaseReviewError("Main ruleset parameters are malformed")
    approval_count = pull_parameters.get("required_approving_review_count")
    expected_minimum = 0 if mode == "single_maintainer" else 1
    if isinstance(approval_count, bool) or not isinstance(approval_count, int) \
            or (mode == "single_maintainer" and approval_count != 0) \
            or (mode == "multi_maintainer" and approval_count < expected_minimum):
        raise ReleaseReviewError("Main ruleset approval requirement conflicts with the selected maintainer mode")
    required_checks = checks_parameters.get("required_status_checks")
    if not isinstance(required_checks, list) or REQUIRED_CHECK not in {
        item.get("context") for item in required_checks if isinstance(item, dict)
    }:
        raise ReleaseReviewError("Main ruleset does not require the full Android/release-intent CI context")


def _verify_applied_ruleset(suite: Any, *, commit: str, name: str) -> None:
    """Prove GitHub evaluated the exact main push and did not record a ruleset bypass."""
    after_sha = suite.get("after_sha") if isinstance(suite, dict) else None
    if not isinstance(after_sha, str) or after_sha.lower() != commit \
            or suite.get("ref") != "refs/heads/main" or suite.get("result") != "pass":
        raise ReleaseReviewError("Exact main commit has no successful, non-bypassed GitHub ruleset evaluation")
    evaluations = suite.get("rule_evaluations")
    if not isinstance(evaluations, list):
        raise ReleaseReviewError("Exact main ruleset evaluation details are unavailable")
    matching = []
    for evaluation in evaluations:
        if not isinstance(evaluation, dict):
            continue
        source = evaluation.get("rule_source")
        if isinstance(source, dict) and source.get("name") == name:
            matching.append(evaluation)
    if not matching or any(item.get("enforcement") != "active" or item.get("result") != "pass"
                           for item in matching):
        raise ReleaseReviewError("Exact main ruleset did not pass actively without a bypass")


def _independent_approvals(reviews: Any, *, author: str, head_sha: str) -> set[str]:
    if not isinstance(reviews, list):
        raise ReleaseReviewError("Pull-request review evidence is malformed")
    approvals: set[str] = set()
    for review in reviews:
        if not isinstance(review, dict) or review.get("state") != "APPROVED":
            continue
        user = review.get("user")
        login = user.get("login") if isinstance(user, dict) else None
        if not isinstance(login, str) or login.casefold() == author.casefold():
            continue
        if review.get("commit_id") != head_sha or not isinstance(review.get("submitted_at"), str):
            continue
        approvals.add(login.casefold())
    return approvals


def verify_release_merge(
    *, commit: str,
    associated_pull_requests: Any,
    pull_request_details: Any,
    reviews: Any,
    ruleset: Any,
    ruleset_suite: Any,
    policy: Any,
    default_branch: str,
    ci_conclusion: str,
) -> tuple[int, str]:
    """Require explicit policy, exact merged PR SHA, protected main evidence, and successful CI."""
    if not SHA.fullmatch(commit):
        raise ReleaseReviewError("Release gate requires a full lowercase commit SHA")
    if ci_conclusion != "success":
        raise ReleaseReviewError("Full CI did not succeed for the exact release commit")
    mode, authorized_mergers, ruleset_name, minimum_approvals = _validate_policy(policy)
    _verify_main_ruleset(ruleset, name=ruleset_name, mode=mode, default_branch=default_branch)
    _verify_applied_ruleset(ruleset_suite, commit=commit, name=ruleset_name)
    if not isinstance(associated_pull_requests, list):
        raise ReleaseReviewError("Commit-to-PR API response is not a JSON array")
    matches = [
        item for item in associated_pull_requests
        if isinstance(item, dict)
        and item.get("state") == "closed"
        and item.get("merged_at")
        and item.get("merge_commit_sha", "").lower() == commit
        and isinstance(item.get("base"), dict)
        and item["base"].get("ref") == "main"
        and isinstance(item["base"].get("repo"), dict)
        and item["base"]["repo"].get("full_name", "").casefold() == "qwy20040320/carpaly"
    ]
    if len(matches) != 1:
        raise ReleaseReviewError("Release intent must belong to exactly one merged PR targeting the protected repository main")
    number = matches[0].get("number")
    if isinstance(number, bool) or not isinstance(number, int) or number < 1:
        raise ReleaseReviewError("Associated merged PR has no valid number")
    if not isinstance(pull_request_details, dict):
        raise ReleaseReviewError("Pull-request details are malformed")
    if pull_request_details.get("number") != number:
        raise ReleaseReviewError("Pull-request details belong to a different PR")
    if (
        pull_request_details.get("state") != "closed"
        or pull_request_details.get("merged_at") != matches[0].get("merged_at")
        or pull_request_details.get("merge_commit_sha", "").lower() != commit
        or pull_request_details.get("base", {}).get("ref") != "main"
        or pull_request_details.get("base", {}).get("repo", {}).get("full_name", "").casefold()
        != "qwy20040320/carpaly"
        or pull_request_details.get("head", {}).get("repo", {}).get("full_name", "").casefold()
        != "qwy20040320/carpaly"
        or pull_request_details.get("head", {}).get("ref") in {None, "", "main"}
        or pull_request_details.get("draft") is not False
    ):
        raise ReleaseReviewError("Release PR must be a non-draft same-repository PR merged into main")
    merger = pull_request_details.get("merged_by")
    merger_login = merger.get("login") if isinstance(merger, dict) else None
    if not isinstance(merger_login, str) or merger.get("type") != "User" \
            or merger_login.casefold() not in authorized_mergers:
        raise ReleaseReviewError("Release PR was not manually merged by an explicitly authorized human")
    head = pull_request_details.get("head")
    head_sha = head.get("sha") if isinstance(head, dict) else None
    author_obj = pull_request_details.get("user")
    author = author_obj.get("login") if isinstance(author_obj, dict) else None
    if not isinstance(head_sha, str) or not SHA.fullmatch(head_sha) or not isinstance(author, str):
        raise ReleaseReviewError("Release PR source identity is incomplete")

    if mode == "multi_maintainer":
        if pull_request_details.get("reviewDecision") != "APPROVED":
            raise ReleaseReviewError("Multi-maintainer mode requires GitHub reviewDecision=APPROVED")
        independent = _independent_approvals(reviews, author=author, head_sha=head_sha)
        if len(independent) < minimum_approvals:
            raise ReleaseReviewError("Multi-maintainer mode lacks a current independent approval")
    return number, mode


def _load(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReleaseReviewError("Could not read GitHub release-authorization evidence") from exc


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--pull-requests-file", required=True, type=Path)
    parser.add_argument("--pull-request-file", required=True, type=Path)
    parser.add_argument("--reviews-file", required=True, type=Path)
    parser.add_argument("--ruleset-file", required=True, type=Path)
    parser.add_argument("--ruleset-suite-file", required=True, type=Path)
    parser.add_argument("--policy-file", required=True, type=Path)
    parser.add_argument("--default-branch", required=True)
    parser.add_argument("--ci-conclusion", required=True)
    args = parser.parse_args(argv)
    try:
        number, mode = verify_release_merge(
            commit=args.commit,
            associated_pull_requests=_load(args.pull_requests_file),
            pull_request_details=_load(args.pull_request_file),
            reviews=_load(args.reviews_file),
            ruleset=_load(args.ruleset_file),
            ruleset_suite=_load(args.ruleset_suite_file),
            policy=_load(args.policy_file),
            default_branch=args.default_branch,
            ci_conclusion=args.ci_conclusion,
        )
    except (OSError, ReleaseReviewError) as exc:
        print(f"RELEASE_REVIEW_STATUS=FAIL: {exc}", file=sys.stderr)
        return 1
    print(f"RELEASE_REVIEW_STATUS=PASS pr={number} mode={mode} main=protected ci=success")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
