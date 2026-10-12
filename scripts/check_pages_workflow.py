#!/usr/bin/env python3
"""Static security checks for the Pages/OTA workflow's immutable actions and permission split."""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/pages.yml"
FULL_SHA = re.compile(r"^([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)@([0-9a-f]{40})$")
EXPECTED = {
    "actions/checkout": "3d3c42e5aac5ba805825da76410c181273ba90b1",
    "actions/setup-python": "a26af69be951a213d495a4c3e4e4022e16d87065",
    "actions/configure-pages": "983d7736d9b0ae728b81ab479565c72886d7745b",
    "actions/upload-pages-artifact": "56afc609e74202658d3ffba0e8f6dda462b719fa",
    "actions/deploy-pages": "d6db90164ac5ed86f2b6aed7e0febac5b3c0c03e",
}


def main() -> int:
    text = WORKFLOW.read_text(encoding="utf-8")
    references = re.findall(r"^\s*-\s*uses:\s*([^\s#]+)", text, re.MULTILINE)
    found: dict[str, str] = {}
    failures: list[str] = []
    for reference in references:
        match = FULL_SHA.fullmatch(reference)
        if not match:
            failures.append(f"Action is not pinned to a full SHA: {reference}")
            continue
        repository, sha = match.groups()
        found[repository] = sha
    if found != EXPECTED:
        failures.append("Pages Action references differ from the reviewed immutable pin inventory")
    if "types: [published, edited, deleted]" not in text:
        failures.append("Pages workflow does not refresh from Release lifecycle events")
    if "branches: [main]" not in text or "cancel-in-progress: false" not in text:
        failures.append("Pages workflow is not main-scoped or permits deployment cancellation")
    if "environment: ota-manifest-publisher" not in text or "name: github-pages" not in text:
        failures.append("OTA signing and Pages deployment environments are not separated")
    build, separator, deploy = text.partition("  deploy:")
    if not separator or "pages: write" in build or "id-token: write" in build:
        failures.append("The secret-bearing OTA build job has Pages deployment permissions")
    if "contents: read" not in build or "pages: write" not in deploy or "id-token: write" not in deploy:
        failures.append("The Pages permission split is incomplete")
    for forbidden in ("MFI_", "RELEASE_KEYSTORE", "RELEASE_STORE_PASSWORD", "RELEASE_KEY_PASSWORD"):
        if forbidden in text:
            failures.append(f"Pages workflow references forbidden Release credential scope: {forbidden}")
    if "--snapshot-out \"$RUNNER_TEMP/carpaly-release-snapshot.json\"" not in text \
            or "--release-snapshot \"$RUNNER_TEMP/carpaly-release-snapshot.json\"" not in text:
        failures.append("Site and OTA manifests do not share one validated Release snapshot")
    if text.index("python scripts/build_site.py") > text.index("python scripts/build_ota_manifests.py") \
            or text.index("python scripts/build_ota_manifests.py") > text.index("actions/upload-pages-artifact"):
        failures.append("Pages artifact can be uploaded before both site and signed feeds are built")
    if failures:
        print("PAGES_WORKFLOW_STATUS=FAIL")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print("PAGES_WORKFLOW_STATUS=PASS")
    print(f"PAGES_ACTION_PIN_COUNT={len(references)}")
    print("PAGES_SECRET_SCOPE=OTA_MANIFEST_ONLY")
    print("PAGES_DEPLOYMENT_ENVIRONMENT=github-pages")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
