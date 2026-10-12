#!/usr/bin/env python3
"""Require an approved, merged main PR for an automatic release-intent commit."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Sequence


SHA = re.compile(r"^[0-9a-f]{40}$")


class ReleaseReviewError(ValueError):
    pass


def verify_approved_merge(
    *, commit: str, associated_pull_requests: Any, pull_request_details: Any,
) -> int:
    if not SHA.fullmatch(commit):
        raise ReleaseReviewError("Release review gate requires a full lowercase commit SHA")
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
    ]
    if len(matches) != 1:
        raise ReleaseReviewError("Release intent must belong to exactly one merged PR targeting main")
    candidate = matches[0]
    number = candidate.get("number")
    if isinstance(number, bool) or not isinstance(number, int) or number < 1:
        raise ReleaseReviewError("Associated merged PR has no valid number")
    if not isinstance(pull_request_details, dict):
        raise ReleaseReviewError("Pull request review response is malformed")
    if pull_request_details.get("number", number) != number:
        raise ReleaseReviewError("Pull request review response belongs to a different PR")
    if (
        pull_request_details.get("baseRefName") != "main"
        or not pull_request_details.get("mergedAt")
        or pull_request_details.get("isDraft") is not False
        or pull_request_details.get("reviewDecision") != "APPROVED"
    ):
        raise ReleaseReviewError("Merged release-intent PR must be approved, non-draft, and based on main")
    return number


def _load(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReleaseReviewError("Could not read GitHub pull-request review metadata") from exc


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--pull-requests-file", required=True, type=Path)
    parser.add_argument("--pull-request-file", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        number = verify_approved_merge(
            commit=args.commit,
            associated_pull_requests=_load(args.pull_requests_file),
            pull_request_details=_load(args.pull_request_file),
        )
    except ReleaseReviewError as exc:
        print(f"RELEASE_REVIEW_STATUS=FAIL: {exc}", file=sys.stderr)
        return 1
    print(f"RELEASE_REVIEW_STATUS=PASS pr={number} base=main review=APPROVED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
