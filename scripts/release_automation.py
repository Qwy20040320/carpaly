#!/usr/bin/env python3
"""Fail-closed policy helpers for CarPaly's local release orchestration.

This module makes decisions only. It never creates tags/releases, uploads artifacts,
changes repository settings, or accesses signing credentials.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SOURCE_POLICY = Path("config/release-source-policy.json")
REVIEW_POLICY = Path("config/release-review-policy.json")
APK_SUFFIXES = {".apk", ".aab", ".p12", ".pfx", ".jks", ".keystore", ".pk8", ".p7b", ".pem", ".key"}
SAFE_DOCUMENTS = set(json.loads((ROOT / "config/public-markdown-allowlist.json").read_text(encoding="utf-8"))["publicMarkdown"])
HIGH_RISK_PREFIXES = (
    ".github/workflows/",
    ".github/scripts/",
    "config/android-version-ledger.json",
    "config/release-intent.json",
    "config/release-review-policy.json",
    "config/release-source-policy.json",
    "mobile/build.gradle.kts",
    "scripts/android_versioning.py",
    "scripts/build-release-apk.ps1",
    "scripts/verify-release-apk.ps1",
    "scripts/release_automation.py",
    "scripts/release_review_gate.py",
    "scripts/check_release_signer_pin.py",
    "offline-mfi/",
    "AGENTS.md",
    "docs/RELEASE",
    "docs/VERSIONING_POLICY.md",
    "docs/LOCAL_RELEASE_GUIDE.md",
    "docs/GITHUB_AUTO_MERGE_GUIDE.md",
    "docs/GITHUB_DRAFT_WORKFLOW.md",
    "docs/RELEASE_SIGNING_GUIDE.md",
    "docs/RELEASE_TROUBLESHOOTING.md",
    "docs/RELEASE_AUTOMATION_ARCHITECTURE.md",
)


@dataclass(frozen=True)
class Decision:
    allowed: bool
    reasons: tuple[str, ...]


def classify_changes(paths: list[str]) -> tuple[str, ...]:
    """Only allow auto-merge for reviewed public Markdown; treat unknown paths as risky."""
    normalized = []
    for path in paths:
        value = path.replace("\\", "/")
        while value.startswith("./"):
            value = value[2:]
        normalized.append(value)
    risky: list[str] = []
    for path in normalized:
        safe_document = path in SAFE_DOCUMENTS and Path(path).suffix.lower() == ".md"
        policy_sensitive = any(path.startswith(prefix) for prefix in HIGH_RISK_PREFIXES)
        if not safe_document or policy_sensitive:
            risky.append(path)
    return tuple(sorted(risky))


def check_auto_merge(
    *,
    repository: dict[str, Any],
    pull_request: dict[str, Any],
    protection: dict[str, Any],
    checks: dict[str, Any],
    review_policy: dict[str, Any],
    changed_paths: list[str],
    expected_head_sha: str,
    requester_login: str,
) -> Decision:
    """Evaluate native GitHub Auto-merge eligibility without bypassing GitHub rules."""
    reasons: list[str] = []
    if str(repository.get("full_name", "")).lower() != "qwy20040320/carpaly":
        reasons.append("untrusted-repository")
    if repository.get("allow_auto_merge") is not True:
        reasons.append("repository-auto-merge-disabled")
    if pull_request.get("state") != "OPEN":
        reasons.append("pull-request-not-open")
    if pull_request.get("draft") is not False:
        reasons.append("draft-pull-request")
    if pull_request.get("base_ref") != "main":
        reasons.append("base-branch-is-not-main")
    if pull_request.get("head_repo") != "Qwy20040320/carpaly":
        reasons.append("fork-pull-request")
    if pull_request.get("mergeable") is not True:
        reasons.append("mergeability-not-confirmed")
    if pull_request.get("unresolved_review_threads") is not False:
        reasons.append("review-threads-unresolved-or-unavailable")
    if pull_request.get("head_sha") != expected_head_sha or checks.get("head_sha") != expected_head_sha:
        reasons.append("head-sha-changed-or-checks-stale")
    trusted = {str(value).casefold() for value in review_policy.get("authorizedMergers", [])}
    if str(pull_request.get("author_login", "")).casefold() not in trusted:
        reasons.append("untrusted-pr-author")
    if pull_request.get("author_association") not in {"OWNER", "MEMBER", "COLLABORATOR"}:
        reasons.append("author-not-trusted-collaborator")
    if review_policy.get("mode") not in {"single_maintainer", "multi_maintainer"}:
        reasons.append("unknown-review-policy")
    if str(requester_login or "").casefold() not in trusted:
        reasons.append("unauthorized-auto-merge-requester")
    if review_policy.get("mode") == "multi_maintainer":
        required_reviews = review_policy.get("minimumIndependentApprovals", 1)
        approvals = pull_request.get("independent_approvals", [])
        author = str(pull_request.get("author_login", "")).casefold()
        independent = {
            str(login).casefold() for login in approvals
            if str(login).casefold() != author
        }
        if len(independent) < max(1, int(required_reviews)):
            reasons.append("independent-approval-missing")

    if protection.get("active") is not True or protection.get("target") != "main":
        reasons.append("main-protection-not-confirmed")
    if protection.get("allows_force_pushes") is not False or protection.get("allows_deletions") is not False:
        reasons.append("main-protection-allows-destructive-update")
    if protection.get("bypass_actors"):
        reasons.append("main-protection-has-bypass-actors")
    if not protection.get("required_checks"):
        reasons.append("required-checks-not-configured")
    check_rows = checks.get("contexts", {})
    for context in protection.get("required_checks", []):
        row = check_rows.get(context)
        if not isinstance(row, dict) or row.get("status") != "completed" or row.get("conclusion") != "success":
            reasons.append(f"required-check-not-passed:{context}")
    risky = classify_changes(changed_paths)
    if risky:
        reasons.append("high-risk-changes-require-human-review")
    if review_policy.get("mode") == "single_maintainer" and int(protection.get("required_approving_review_count", -1)) < 0:
        reasons.append("single-maintainer-protection-unreadable")
    return Decision(not reasons, tuple(reasons))


def classify_draft_release(
    release: dict[str, Any] | None,
    *,
    expected_tag: str,
    expected_commit: str,
    marker: str,
) -> str:
    """Classify only safe metadata-only draft states; never mutates GitHub."""
    if release is None:
        return "CREATE_REQUIRED_BY_AUTHENTICATED_PUBLISHER"
    if release.get("tag_name") != expected_tag:
        return "BLOCKED_TAG_MISMATCH"
    if release.get("draft") is not True:
        return "PUBLISHED_IMMUTABLE"
    if release.get("target_commitish") not in (expected_commit, ""):
        return "BLOCKED_SOURCE_MISMATCH"
    if marker not in str(release.get("body", "")):
        return "BLOCKED_UNRECOGNIZED_DRAFT"
    if release.get("assets"):
        return "BLOCKED_DRAFT_HAS_ASSETS"
    return "SAFE_DRAFT_REUSE"


def public_upload_guard(paths: list[str]) -> Decision:
    """Public release tooling is metadata-only; binary and credential assets are forbidden."""
    blocked = [path for path in paths if Path(path).suffix.lower() in APK_SUFFIXES]
    return Decision(not blocked, tuple(f"public-asset-forbidden:{Path(path).suffix.lower()}" for path in blocked))


def source_baseline_status(root: Path, commit: str | None = None) -> tuple[bool, str]:
    """Require the build commit to descend from the newest verified public release source."""
    try:
        policy = json.loads((root / SOURCE_POLICY).read_text(encoding="utf-8"))
        baseline = policy["minimumSourceCommit"]
        candidate = commit or subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=root, text=True, capture_output=True, check=True
        ).stdout.strip()
        result = subprocess.run(
            ["git", "merge-base", "--is-ancestor", baseline, candidate],
            cwd=root, text=True, capture_output=True,
        )
        if result.returncode == 0:
            return True, f"SOURCE_BASELINE=PASS baseline={baseline} commit={candidate}"
        if result.returncode == 1:
            return False, f"SOURCE_BASELINE=BLOCKED latest_verified_release_source={baseline} is_not_ancestor_of={candidate}"
        return False, "SOURCE_BASELINE=UNKNOWN git ancestry could not be established"
    except (OSError, KeyError, json.JSONDecodeError, subprocess.CalledProcessError):
        return False, "SOURCE_BASELINE=UNKNOWN policy or Git evidence is unavailable"


def validate_release_intent(intent: dict[str, Any], *, branch: str, event: str) -> Decision:
    if intent.get("enabled") is not True:
        return Decision(False, ("release-intent-disabled",))
    if branch != "main" or event != "push":
        return Decision(False, ("release-intent-requires-main-push",))
    return Decision(True, ())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("source-check", "upload-guard", "auto-merge-check"))
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--commit")
    parser.add_argument("--path", action="append", default=[])
    parser.add_argument("--input", type=Path)
    args = parser.parse_args()
    if args.command == "source-check":
        passed, message = source_baseline_status(args.root.resolve(), args.commit)
        print(message)
        return 0 if passed else 1
    if args.command == "upload-guard":
        result = public_upload_guard(args.path)
        if result.allowed:
            print("PUBLIC_UPLOAD_GUARD=PASS metadata-only-assets")
            return 0
        print("PUBLIC_UPLOAD_GUARD=BLOCKED " + ",".join(result.reasons), file=sys.stderr)
        return 1
    if args.input is None:
        parser.error("auto-merge-check requires --input JSON evidence")
    try:
        evidence = json.loads(args.input.read_text(encoding="utf-8"))
        decision = check_auto_merge(
            repository=evidence["repository"],
            pull_request=evidence["pull_request"],
            protection=evidence["protection"],
            checks=evidence["checks"],
            review_policy=evidence["review_policy"],
            changed_paths=evidence["changed_paths"],
            expected_head_sha=evidence["expected_head_sha"],
            requester_login=evidence["requester_login"],
        )
    except (OSError, KeyError, json.JSONDecodeError, TypeError, ValueError) as exc:
        print(f"AUTO_MERGE_DECISION=BLOCKED evidence-invalid:{type(exc).__name__}", file=sys.stderr)
        return 1
    if decision.allowed:
        print("AUTO_MERGE_DECISION=ALLOW native_auto_merge_only")
        return 0
    print("AUTO_MERGE_DECISION=BLOCKED " + ",".join(decision.reasons))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
