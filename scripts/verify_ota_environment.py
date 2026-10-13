#!/usr/bin/env python3
"""Read-only fail-closed validation of the production OTA GitHub Environment."""

from __future__ import annotations

import json
import os
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "config/ota-publisher-policy.json"
EXPECTED_REPOSITORY = "Qwy20040320/carpaly"
ENVIRONMENT = "ota-manifest-publisher"


class EnvironmentGateError(ValueError):
    pass


def validate_configuration(environment: Any, branch_response: Any, minimum_reviewers: int) -> None:
    if not isinstance(environment, dict) or environment.get("name") != ENVIRONMENT:
        raise EnvironmentGateError("The dedicated OTA Environment is missing or misidentified")
    branch_mode = environment.get("deployment_branch_policy")
    if not isinstance(branch_mode, dict) or branch_mode.get("protected_branches") is not False \
            or branch_mode.get("custom_branch_policies") is not True:
        raise EnvironmentGateError("OTA Environment must use an explicit custom deployment branch allow-list")
    policies = branch_response.get("branch_policies") if isinstance(branch_response, dict) else None
    if not isinstance(policies, list) or policies != [{"name": "main", "type": "branch"}]:
        raise EnvironmentGateError("OTA Environment must allow only the main branch")
    rules = environment.get("protection_rules")
    reviewer_rules = [rule for rule in rules if isinstance(rule, dict) and rule.get("type") == "required_reviewers"] \
        if isinstance(rules, list) else []
    if len(reviewer_rules) != 1:
        raise EnvironmentGateError("OTA Environment must have exactly one required-reviewers protection rule")
    reviewer_rule = reviewer_rules[0]
    reviewers = reviewer_rule.get("reviewers")
    if not isinstance(reviewers, list) or len(reviewers) < minimum_reviewers:
        raise EnvironmentGateError("OTA Environment has fewer configured reviewers than policy requires")
    if reviewer_rule.get("prevent_self_review") is not True:
        raise EnvironmentGateError("OTA Environment must prevent the deployment initiator from self-approving")


def _github_json(path: str, token: str) -> Any:
    request = Request(
        f"https://api.github.com{path}",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        # Never echo response bodies or auth headers into Actions logs.
        raise EnvironmentGateError("Could not read the OTA Environment configuration from GitHub") from exc


def main() -> int:
    repository = os.environ.get("GITHUB_REPOSITORY", "")
    token = os.environ.get("GITHUB_TOKEN", "")
    if repository != EXPECTED_REPOSITORY or not token:
        print("OTA_ENVIRONMENT_GUARD=BLOCKED: expected the target repository and a read-only Actions token",
              file=sys.stderr)
        return 2
    try:
        policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
        minimum_reviewers = policy.get("minimumRequiredReviewers")
        if isinstance(minimum_reviewers, bool) or not isinstance(minimum_reviewers, int) or minimum_reviewers < 1:
            raise EnvironmentGateError("OTA publisher policy has an invalid reviewer minimum")
        encoded_name = ENVIRONMENT.replace("/", "%2F")
        environment = _github_json(f"/repos/{repository}/environments/{encoded_name}", token)
        branches = _github_json(
            f"/repos/{repository}/environments/{encoded_name}/deployment-branch-policies?per_page=100", token,
        )
        validate_configuration(environment, branches, minimum_reviewers)
    except (OSError, json.JSONDecodeError, EnvironmentGateError) as exc:
        print(f"OTA_ENVIRONMENT_GUARD=BLOCKED: {exc}", file=sys.stderr)
        return 2
    print("OTA_ENVIRONMENT_GUARD=PASS branch=main required_reviewers=verified self_review=disabled")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
