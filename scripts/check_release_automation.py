#!/usr/bin/env python3
"""Static guardrails for protected Release builds and metadata-only Draft preparation."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    android_path = ROOT / ".github/workflows/android.yml"
    history_path = ROOT / ".github/workflows/carpaly-android-build.yml"
    tv_path = ROOT / ".github/workflows/build-android-tv.yml"
    draft_path = ROOT / ".github/scripts/prepare-release-draft.sh"
    android = android_path.read_text(encoding="utf-8")
    history = history_path.read_text(encoding="utf-8")
    tv = tv_path.read_text(encoding="utf-8")
    draft = draft_path.read_text(encoding="utf-8")
    intent = json.loads((ROOT / "config/release-intent.json").read_text(encoding="utf-8"))
    review_policy = json.loads((ROOT / "config/release-review-policy.json").read_text(encoding="utf-8"))
    review_gate = (ROOT / "scripts/release_review_gate.py").read_text(encoding="utf-8")
    local_entry = (ROOT / "build-release.ps1").read_text(encoding="utf-8")
    local_policy = (ROOT / "scripts/release_automation.py").read_text(encoding="utf-8")
    failures: list[str] = []

    if intent.get("schemaVersion") != 1 or intent.get("enabled") is not False:
        failures.append("Checked-in release intent must remain a disabled schema-1 baseline")
    if "pull_request:" not in android or "github.event_name == 'push' && github.ref == 'refs/heads/main'" not in android:
        failures.append("Android CI and the main-only release intent gate are not both configured")
    if "scripts/test_release_pipeline.py" not in android or "./gradlew :shared:testDebugUnitTest" not in android:
        failures.append("Always-on Android and release pipeline test coverage is missing")
    check = android.partition("  check:")[2].partition("  release_intent:")[0]
    for marker in (
        "scripts.test_release_signer_pin",
        "scripts/test_release_pipeline.py",
        "check_workflow_action_pins.py",
        "check_release_automation.py",
        "gitleaks",
        "actionlint",
    ):
        if marker not in check:
            failures.append(f"Always-on CI is missing {marker}")
    if "secrets." in check:
        failures.append("Ordinary push/PR CI must not reference production Secrets")

    gate = android.partition("  release_intent:")[2].partition("  release_signer_pin:")[0]
    if not gate or "secrets." in gate or "environment:" in gate:
        failures.append("The release-intent gate must not access an Environment or Secret")
    if "scripts/release_intent.py" not in android or "config/release-intent.json" not in (ROOT / "scripts/release_intent.py").read_text(encoding="utf-8"):
        failures.append("Release intent must be read from the reviewed repository policy")

    pin_job = android.partition("  release_signer_pin:")[2].partition("  release_authorization:")[0]
    if (
        "needs: [check, release_intent]" not in pin_job
        or "environment: mfi-public-release" not in pin_job
        or "scripts/check_release_signer_pin.py" not in pin_job
        or "secrets." in pin_job
    ):
        failures.append("Full CI and the intent gate must pass before the Environment signer policy is checked")

    authorization = android.partition("  release_authorization:")[2].partition("  release_signer_preflight:")[0]
    if (
        "environment: release-policy-audit" not in authorization
        or "pull-requests: read" not in authorization
        or "needs.release_signer_pin.result == 'success'" not in authorization
        or "scripts/release_review_gate.py" not in authorization
        or "rulesets/rule-suites/$suite_id" not in authorization
        or "RELEASE_POLICY_READ_TOKEN" not in authorization
    ):
        failures.append("Human merge authorization must verify exact protected-main review evidence")

    build = android.partition("  authenticated_release:")[2].partition("  prepare_release_draft:")[0]
    if (
        "needs: [check, release_intent, release_authorization, release_signer_pin]" not in android
        or "needs.release_signer_pin.result == 'success'" not in build
        or "needs.release_intent.outputs.should_publish == 'true'" not in build
        or "github.event_name == 'push' && github.ref == 'refs/heads/main'" not in build
        or "environment: mfi-public-release" not in build
    ):
        failures.append("Signed Release build must require current main, full CI, human authorization, and release intent")
    if "permissions:\n      contents: read" not in build:
        failures.append("Signing/build job must not have write access to Release metadata")
    if ":mobile:verifyStandaloneAuthentication" not in build or ":mobile:assembleRelease" not in build:
        failures.append("Protected Release candidate must run authentication verification and Release assembly")
    pin_marker = "scripts/check_release_signer_pin.py"
    if pin_marker not in build:
        failures.append("Environment signer pin must be checked against reviewed policy")
    elif "MFI_IDENTITY_PK8_BASE64: ${{ secrets." in build and build.index(pin_marker) > build.index("MFI_IDENTITY_PK8_BASE64: ${{ secrets."):
        failures.append("Signer pin mismatch must fail before mapping any MFi credential")
    elif "RELEASE_KEYSTORE_BASE64: ${{ secrets." in build and build.index(pin_marker) > build.index("RELEASE_KEYSTORE_BASE64: ${{ secrets."):
        failures.append("Signer pin mismatch must fail before mapping the Release keystore")
    elif (
        "scripts/release_signing_preflight.py" not in build
        or "MFI_IDENTITY_PK8_BASE64: ${{ secrets." not in build
        or build.index("scripts/release_signing_preflight.py") > build.index("MFI_IDENTITY_PK8_BASE64: ${{ secrets.")
    ):
        failures.append("The actual Release signer must pass before any MFi authentication Secret is mapped")

    draft_job = android.partition("  prepare_release_draft:")[2]
    if (
        "contents: write" not in draft_job
        or "needs.authenticated_release.result == 'success'" not in draft_job
        or "needs.release_intent.outputs.should_publish == 'true'" not in draft_job
        or "github.event_name == 'push' && github.ref == 'refs/heads/main'" not in draft_job
        or "bash .github/scripts/prepare-release-draft.sh" not in draft_job
    ):
        failures.append("Release Draft job must be downstream of the verified main build and intent")
    if "environment:" in draft_job or "secrets." in draft_job or "actions/upload-artifact" in draft_job:
        failures.append("Draft preparation must use no production Environment, Secret, or binary Artifact")
    if "gh release upload" in build or "publish-authenticated-apk-release.sh" in android:
        failures.append("Android workflow still contains an automatic Release asset upload path")

    if "gh release upload" in draft or "draft=false" in draft or "--method PATCH" in draft:
        failures.append("Draft preparer must never upload assets or mutate a Release publication state")
    if "gh release create" in local_entry or "gh release upload" in local_entry or "AUTO_CREATE_TAG = 'true'" in local_entry:
        failures.append("The local orchestrator must not create tags/releases or upload binaries")
    if "prepare-release-draft.sh" in local_entry:
        failures.append("Local Draft mode must verify, not invoke the remote Draft mutator")
    for mode in ("CheckOnly", "SkipTests", "PrepareGitHub", "PrepareDraft", "Status", "FullPrepare"):
        if f"$switch) ${mode}" not in local_entry and f"${mode}" not in local_entry:
            failures.append(f"Local Release orchestrator is missing mode {mode}")
    if "unauthorized-auto-merge-requester" not in local_policy or "high-risk-changes-require-human-review" not in local_policy:
        failures.append("Native Auto-merge policy must bind the authenticated requester and block high-risk changes")
    if "--draft" not in draft or "assets=0" not in draft or "PUBLISHED_IMMUTABLE" not in draft:
        failures.append("Draft preparer must create drafts, verify zero assets, and leave published Releases untouched")
    if "AUTO_CREATE_TAG" not in draft or "--target \"$RELEASE_COMMIT\"" not in draft:
        failures.append("A newly created tag must be bound to the verified source commit")
    if "--force" in draft or "--delete-tag" in draft:
        failures.append("Draft preparer must not force-push or delete tags")

    # Historical jobs may build a private candidate, but publish only a credential-free report.
    history_candidate = history.partition("  signed_candidate:")[2].partition("  prepare_historical_draft:")[0]
    history_draft = history.partition("  prepare_historical_draft:")[2]
    history_report_upload = history_candidate.partition("- name: Upload safe build report only")[2].partition(
        "- name: Remove temporary signing and authentication material"
    )[0]
    if (
        "Check Environment signer pin before mapping any Secret" not in history_candidate
        or history_candidate.index("Check Environment signer pin before mapping any Secret")
        > history_candidate.index("Provision protected runtime authentication inputs")
        or "scripts/release_signing_preflight.py" not in history_candidate
        or history_candidate.index("scripts/release_signing_preflight.py")
        > history_candidate.index("Provision protected runtime authentication inputs")
        or "build-report/rebuild.json" not in history_candidate
        or "build-report/rebuild.json" not in history_report_upload
        or ".apk" in history_report_upload
        or "outputs/apk" in history_report_upload
    ):
        failures.append("Historical candidate must pin-check before secrets and persist only its sanitized report")
    if (
        "needs.signed_candidate.result == 'success'" not in history_draft
        or "contents: write" not in history_draft
        or "bash .github/scripts/prepare-release-draft.sh" not in history_draft
        or "environment:" in history_draft
        or "secrets." in history_draft
    ):
        failures.append("Historical Draft preparation must follow the verified candidate without production credentials")
    if "github.event_name == 'push' && github.ref_type == 'tag'" in history_candidate:
        # Tag-triggered signing is permitted only after the separate exact-main enabled-intent check.
        if "Require enabled exact-main intent for tag-triggered signing" not in history:
            failures.append("Tag-triggered signer job lacks an exact-main release-intent gate")

    if "actions/upload-artifact" in tv or "outputs/apk/debug/*.apk" in tv:
        failures.append("Android TV workflow must not upload a user-installable Debug APK")
    for workflow_path in (android_path, history_path, tv_path):
        workflow = workflow_path.read_text(encoding="utf-8")
        if "draft=false" in workflow or "gh release upload" in workflow:
            failures.append(f"{workflow_path.name} contains a forbidden publication transition or asset upload")

    if (
        review_policy.get("schemaVersion") != 1
        or review_policy.get("mode") not in {"single_maintainer", "multi_maintainer"}
        or not review_policy.get("authorizedMergers")
        or "single_maintainer" not in review_gate
        or "multi_maintainer" not in review_gate
        or 'suite.get("result") != "pass"' not in review_gate
    ):
        failures.append("Release authorization policy must preserve explicit single/multi-maintainer proof")

    if failures:
        print("RELEASE_AUTOMATION_STATUS=FAIL")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print("RELEASE_AUTOMATION_STATUS=PASS")
    print("RELEASE_GATE=full-ci+reviewed-main-intent+signer-pin-before-secrets")
    print("RELEASE_ASSETS=WITHHELD; metadata-only Draft, manual publication only")
    print("PR_SECRETS=NOT_EXPOSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
