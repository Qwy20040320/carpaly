#!/usr/bin/env python3
"""Static checks for secretless Pages bootstrap and the separately gated production OTA publisher."""

from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PAGE_WORKFLOW = ROOT / ".github/workflows/pages.yml"
OTA_WORKFLOW = ROOT / ".github/workflows/publish-ota-feeds.yml"
FULL_SHA = re.compile(r"^([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)@([0-9a-f]{40})$")
EXPECTED_ACTIONS = {
    "actions/checkout": "3d3c42e5aac5ba805825da76410c181273ba90b1",
    "actions/setup-python": "a26af69be951a213d495a4c3e4e4022e16d87065",
    "actions/configure-pages": "983d7736d9b0ae728b81ab479565c72886d7745b",
    "actions/upload-pages-artifact": "56afc609e74202658d3ffba0e8f6dda462b719fa",
    "actions/deploy-pages": "d6db90164ac5ed86f2b6aed7e0febac5b3c0c03e",
    "actions/upload-artifact": "cf430e030ddbb5b0abf93d22962f4752f3646cd9",
    "actions/download-artifact": "37930b1c2abaa49bbe596cd826c3c89aef350131",
}


def _pinned_references(path: Path, failures: list[str]) -> int:
    text = path.read_text(encoding="utf-8")
    references = re.findall(r"^\s*-\s*uses:\s*([^\s#]+)", text, re.MULTILINE)
    for reference in references:
        match = FULL_SHA.fullmatch(reference)
        if not match:
            failures.append(f"Action in {path.name} is not pinned to a full SHA: {reference}")
            continue
        repository, sha = match.groups()
        if EXPECTED_ACTIONS.get(repository) != sha:
            failures.append(f"Action pin in {path.name} is outside the reviewed inventory: {reference}")
    return len(references)


def main() -> int:
    pages = PAGE_WORKFLOW.read_text(encoding="utf-8")
    ota = OTA_WORKFLOW.read_text(encoding="utf-8")
    intent = json.loads((ROOT / "config/release-intent.json").read_text(encoding="utf-8"))
    publisher = json.loads((ROOT / "config/ota-publisher-policy.json").read_text(encoding="utf-8"))
    failures: list[str] = []
    action_count = _pinned_references(PAGE_WORKFLOW, failures) + _pinned_references(OTA_WORKFLOW, failures)

    if "branches: [main]" not in pages or "workflow_dispatch:" not in pages:
        failures.append("Secretless Pages workflow must build from main and support an explicit main dispatch")
    if "\n  release:\n" in pages:
        failures.append("Pages must not deploy a tag-ref Release event into the main-restricted github-pages Environment")
    android = (ROOT / ".github/workflows/android.yml").read_text(encoding="utf-8")
    dispatcher = (ROOT / "scripts/dispatch_release_followups.py").read_text(encoding="utf-8")
    if "scripts/dispatch_release_followups.py" not in android or "pages.yml" not in dispatcher:
        failures.append("Authenticated Release completion must dispatch the Pages workflow on main")
    if "group: carpaly-pages" not in pages or "cancel-in-progress: false" not in pages:
        failures.append("Pages deployment is not serialized or may cancel an active deployment")
    if "--preserve-existing-ota-feeds" not in pages or "scripts/preserve_ota_feeds.py" not in pages:
        failures.append("Ordinary Pages builds do not validate and preserve already-deployed signed feeds")
    if "allow_initial_static_bootstrap:" not in pages or "default: false" not in pages \
            or "--allow-initial-static-bootstrap" not in pages:
        failures.append("First static Pages deployment is not an explicit manual-only bootstrap")
    if "scripts.test_preserve_ota_feeds" not in pages or "scripts.test_build_site" not in pages:
        failures.append("Pages workflow omits offline static bootstrap/feed-preservation tests")
    if "environment: ota-manifest-publisher" in pages or "build_ota_manifests.py" in pages:
        failures.append("Ordinary Pages build is coupled to the OTA production signer")
    for forbidden in (
        "secrets.", "OTA_MANIFEST_SIGNING_PRIVATE_KEY_PEM", "OTA_MANIFEST_SIGNING_KEY_ID",
        "MFI_", "RELEASE_KEYSTORE", "RELEASE_STORE_PASSWORD", "RELEASE_KEY_PASSWORD",
    ):
        if forbidden in pages:
            failures.append(f"Secretless Pages workflow references a protected signing value: {forbidden}")
    pages_build, separator, pages_deploy = pages.partition("  deploy:")
    if not separator or "name: github-pages" not in pages_deploy:
        failures.append("Static Pages deployment is not isolated in the github-pages Environment")
    if "contents: read" not in pages_build or "pages: write" in pages_build or "id-token: write" in pages_build:
        failures.append("Static Pages build has an invalid permission split")
    if "pages: write" not in pages_deploy or "id-token: write" not in pages_deploy:
        failures.append("Static Pages deploy lacks the minimum Pages/OIDC permission pair")
    if "otaFeedStatus" not in (ROOT / "scripts/build_site.py").read_text(encoding="utf-8"):
        failures.append("Site builder does not expose the actual signed-feed availability state")

    if "workflow_dispatch:" not in ota or any(event in ota for event in ("\n  push:", "\n  pull_request:", "\n  release:")):
        failures.append("Production OTA publisher must be manual-only, not PR/push/tag/event triggered")
    if "group: carpaly-pages" not in ota or "cancel-in-progress: false" not in ota:
        failures.append("Production OTA and ordinary Pages deployments can race")
    if "default: false" not in ota or "publish_production_ota == true" not in ota:
        failures.append("Production OTA signing is not behind an explicit false-by-default input")
    if "allow_initial_static_bootstrap:" not in ota or "--allow-initial-static-bootstrap" not in ota:
        failures.append("First production-feed deployment lacks an explicit bootstrap confirmation")
    if "github.ref == 'refs/heads/main'" not in ota or "github.repository == 'Qwy20040320/carpaly'" not in ota:
        failures.append("Production OTA workflow is not restricted to trusted main in the target repository")
    if "environment: ota-manifest-publisher" not in ota or "environment:\n      name: github-pages" not in ota:
        failures.append("Production signer and Pages deploy jobs do not use separate Environments")
    if "scripts/ota_publisher_policy.py" not in ota or "scripts/validate_ota_release_target.py" not in ota:
        failures.append("Production OTA preflight does not require a reviewed trust root and a real verified Release")
    if "python scripts/verify_ota_environment.py" not in ota or "GITHUB_TOKEN: ${{ github.token }}" not in ota:
        failures.append("Production OTA preflight does not inspect the real Environment branch/reviewer rules")
    preflight_job = ota.partition("  preflight:")[2].partition("  sign_and_stage:")[0]
    if "actions: read" not in preflight_job:
        failures.append("OTA Environment inspection lacks the minimum Actions read permission")
    if "--required-release-tag" not in ota or "build_ota_manifests.py" not in ota:
        failures.append("Production OTA publisher does not bind signing to an exact verified Release tag")
    if "--prior-site-state" not in ota or "--local-ota-feed-dir" not in ota \
            or "--release-snapshot" not in ota:
        failures.append("Signed OTA feeds are not merged into a final site rebuilt from the exact preflight snapshot")
    if "carpaly-ota-final-site" not in ota or "path: ${{ runner.temp }}/carpaly-ota-final-site" not in ota:
        failures.append("OTA deployment artifact is not the final rebuilt site containing its validated signed feeds")
    if "needs: preflight" not in ota or "needs.preflight.result == 'success'" not in ota:
        failures.append("Environment-backed signing can run before the no-secret preflight succeeds")
    if "needs: sign_and_stage" not in ota or "needs.sign_and_stage.result == 'success'" not in ota:
        failures.append("Pages deploy is not blocked after any signing/build failure")
    sign_job = ota.partition("  sign_and_stage:")[2].partition("  deploy:")[0]
    if "OTA_MANIFEST_SIGNING_PRIVATE_KEY_PEM: ${{ secrets." not in sign_job \
            or "OTA_MANIFEST_SIGNING_KEY_ID: ${{ vars." not in sign_job:
        failures.append("Only the OTA signing job may receive the dedicated OTA secret and key-id variable")
    for forbidden in ("MFI_", "RELEASE_KEYSTORE", "RELEASE_STORE_PASSWORD", "RELEASE_KEY_PASSWORD"):
        if forbidden in ota:
            failures.append(f"OTA publishing workflow references an unrelated signing credential: {forbidden}")
    ota_preflight, sep_preflight, ota_tail = ota.partition("  sign_and_stage:")
    ota_sign, sep_deploy, ota_deploy = ota_tail.partition("  deploy:")
    if not sep_preflight or not sep_deploy or "pages: write" in ota_preflight + ota_sign \
            or "id-token: write" in ota_preflight + ota_sign:
        failures.append("Only the isolated Pages deploy job may receive deployment permissions")
    if "contents: read" not in ota_preflight or "contents: read" not in ota_sign \
            or "pages: write" not in ota_deploy or "id-token: write" not in ota_deploy:
        failures.append("OTA publish workflow does not follow least-privilege job permissions")

    if intent.get("schemaVersion") != 1 or intent.get("enabled") is not False:
        failures.append("Phase 10 must preserve the disabled release-intent baseline")
    if publisher.get("schemaVersion") != 1 or publisher.get("productionEnabled") is not False \
            or publisher.get("environmentConfigurationReviewed") is not False:
        failures.append("Phase 10 must leave production OTA publisher policy disabled and unattested")
    if action_count != 14:
        failures.append(f"Expected 14 immutable Action references across Pages workflows; found {action_count}")

    if failures:
        print("PAGES_WORKFLOW_STATUS=FAIL")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print("PAGES_WORKFLOW_STATUS=PASS")
    print(f"PAGES_ACTION_PIN_COUNT={action_count}")
    print("STATIC_PAGES_SECRET_SCOPE=NONE")
    print("PRODUCTION_OTA_SCOPE=DEDICATED_ENVIRONMENT; EXPLICITLY_DISABLED_BASELINE")
    print("FEED_POLICY=VERIFY_AND_PRESERVE_OR_BLOCK_WHOLE_DEPLOYMENT")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
