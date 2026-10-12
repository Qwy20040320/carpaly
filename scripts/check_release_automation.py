#!/usr/bin/env python3
"""Static guardrails for the main-CI release-intent orchestration."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    android = (ROOT / ".github/workflows/android.yml").read_text(encoding="utf-8")
    publisher = (ROOT / ".github/scripts/publish-authenticated-apk-release.sh").read_text(encoding="utf-8")
    intent = json.loads((ROOT / "config/release-intent.json").read_text(encoding="utf-8"))
    failures: list[str] = []

    if intent.get("schemaVersion") != 1 or intent.get("enabled") is not False:
        failures.append("Checked-in release intent must be a disabled schema-1 baseline")
    if "pull_request:" not in android or "github.event_name == 'push' && github.ref == 'refs/heads/main'" not in android:
        failures.append("Android CI and the main-only release-intent gate are not both configured")
    if "name: Run full CI and gate an explicit release intent" not in android or "github.event_name != 'workflow_dispatch'" not in android:
        failures.append("Full Android CI must run for PR/push events and skip only signer-only dispatches")
    if "./gradlew :shared:testDebugUnitTest" not in android or "scripts/test_release_pipeline.py" not in android:
        failures.append("Full Android and Bash publisher CI is not present in the always-on CI job")
    if (
        "needs: [check, release_intent]" not in android
        or "needs.check.result == 'success'" not in android
        or "needs.release_intent.result == 'success'" not in android
    ):
        failures.append("Authenticated publication is not gated on successful full CI and intent validation")
    if "needs.release_intent.outputs.should_publish == 'true'" not in android:
        failures.append("Main publication does not require an enabled release-intent output")
    if "environment: mfi-public-release" not in android:
        failures.append("Authenticated Release job is not scoped to mfi-public-release")
    if "permissions:\n      contents: write" not in android:
        failures.append("Authenticated Release job lacks the minimum Release asset write permission")
    gate = android.partition("  release_intent:")[2].partition("  release_signer_preflight:")[0]
    if not gate or "secrets." in gate or "environment:" in gate:
        failures.append("The no-secret release-intent gate must not access an Environment or Secrets")
    check = android.partition("  check:")[2].partition("  release_intent:")[0]
    required_checks = (
        "scripts.test_release_intent",
        "scripts.test_release_review_gate",
        "scripts.test_release_followups",
        "scripts.test_ota_manifest",
        "scripts.test_build_site",
        "scripts/test_release_pipeline.py",
        "check_workflow_action_pins.py",
        "check_pages_workflow.py",
        "check_release_automation.py",
        "gitleaks",
        "actionlint",
    )
    for marker in required_checks:
        if marker not in check:
            failures.append(f"Full main CI is missing release validation: {marker}")
    if "pull-requests: read" not in gate or "reviewDecision" not in gate or "RELEASE_REVIEW_STATUS=PASS" not in (
        ROOT / "scripts/release_review_gate.py"
    ).read_text(encoding="utf-8"):
        failures.append("Automatic publication does not require an approved merged PR for the exact release commit")
    follow_up = android.partition("  publication_follow_up:")[2]
    if "actions: write" not in follow_up or "contents: read" not in follow_up:
        failures.append("Post-release workflow dispatch does not use the narrow Actions permission split")
    if "scripts/dispatch_release_followups.py" not in follow_up or "--timeout-seconds 2400" not in follow_up:
        failures.append("Post-release follow-up does not wait for correlated downstream workflow results")
    if 'gh api "repos/$GH_REPO/commits/main" --jq .sha' not in follow_up:
        failures.append("Post-release follow-up is not correlated to the dispatched main revision")
    dispatcher = (ROOT / "scripts/dispatch_release_followups.py").read_text(encoding="utf-8")
    for workflow in ("pages.yml", "release-docs-sync.yml"):
        if workflow not in dispatcher or "display_title" not in dispatcher or "head_sha" not in dispatcher:
            failures.append(f"Post-release follow-up cannot correlate the {workflow} run to this release")
    for workflow_path, title in (
        (".github/workflows/pages.yml", "CarPaly Pages deploy"),
        (".github/workflows/release-docs-sync.yml", "CarPaly release docs sync"),
    ):
        workflow_source = (ROOT / workflow_path).read_text(encoding="utf-8")
        if "dispatch_id:" not in workflow_source or title not in workflow_source:
            failures.append(f"{workflow_path} lacks a correlated workflow_dispatch input and run name")
    docs_sync = (ROOT / ".github/workflows/release-docs-sync.yml").read_text(encoding="utf-8")
    if "workflow_run:" in docs_sync:
        failures.append("Release docs workflow has a duplicate workflow_run path alongside explicit dispatch")
    if "AUTO_CREATE_TAG" not in publisher or '--target "$RELEASE_COMMIT"' not in publisher:
        failures.append("Automatic tag creation is not bound to the already verified source commit")
    if "RELEASE_PRERELEASE" not in publisher or "preserving it without mutation" not in publisher:
        failures.append("Release channel intent and immutable existing Release protection are incomplete")
    if "--force" in publisher or "--delete-tag" in publisher:
        failures.append("Publisher must not force-push or delete version tags")

    if failures:
        print("RELEASE_AUTOMATION_STATUS=FAIL")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print("RELEASE_AUTOMATION_STATUS=PASS")
    print("RELEASE_GATE=full-ci-on-pr-and-push; publication-requires-main+successful-ci+same-commit-intent")
    print("PR_SECRETS=NOT_EXPOSED")
    print("FOLLOW_UP=correlated-workflow_dispatch; waits for Pages and docs CI results")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
