#!/usr/bin/env python3
"""Check public project documentation against the current app metadata and verified status."""

from __future__ import annotations

import json
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
GRADLE = ROOT / "mobile/build.gradle.kts"
LEDGER = ROOT / "config/android-version-ledger.json"
README_PATHS = (
    ROOT / "README.md",
    ROOT / "README.zh-CN.md",
    ROOT / "docs/geely/README_ZH.md",
)
VERSION_POLICY = ROOT / "docs/VERSIONING_POLICY.md"
SIGNING_POLICY = ROOT / "docs/RELEASE_SIGNING_POLICY.md"
BRANDING_SOURCE = ROOT / "common/src/main/java/com/shilapi/xcertplay/HeadUnitProfile.kt"
RELEASE_BUILDER = ROOT / "scripts/build-release-apk.ps1"
RELEASE_VERIFIER = ROOT / "scripts/verify-release-apk.ps1"
OLD_DELIVERY_SCRIPTS = (
    ROOT / "scripts/build-upgrade-apk.ps1",
    ROOT / "scripts/verify-upgrade-apk.ps1",
)
LOCAL_RELEASE_DOCS = (
    ROOT / "docs/LOCAL_RELEASE_GUIDE.md",
    ROOT / "docs/GITHUB_AUTO_MERGE_GUIDE.md",
    ROOT / "docs/GITHUB_DRAFT_WORKFLOW.md",
    ROOT / "docs/RELEASE_SIGNING_GUIDE.md",
    ROOT / "docs/RELEASE_TROUBLESHOOTING.md",
    ROOT / "docs/RELEASE_AUTOMATION_ARCHITECTURE.md",
)


def check() -> list[str]:
    errors: list[str] = []
    ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
    version = ledger["current"]
    gradle = GRADLE.read_text(encoding="utf-8")
    build_version = re.search(r'^\s*versionName\s*=\s*"([^"]+)"\s*$', gradle, re.M)
    build_code = re.search(r"^\s*versionCode\s*=\s*(\d+)\s*$", gradle, re.M)
    app_id = re.search(r'^\s*applicationId\s*=\s*"([^"]+)"\s*$', gradle, re.M)
    if not build_version or build_version.group(1) != version["versionName"]:
        errors.append("mobile/build.gradle.kts versionName differs from the version ledger")
    if not build_code or int(build_code.group(1)) != version["versionCode"]:
        errors.append("mobile/build.gradle.kts versionCode differs from the version ledger")
    if not app_id or app_id.group(1) != ledger["applicationId"]:
        errors.append("mobile/build.gradle.kts applicationId differs from the version ledger")
    policy = ledger.get("deliveryPolicy", {})
    if policy.get("buildType") != "release":
        errors.append("The version ledger must require the Release build type for user APKs")
    if policy.get("apkFileNamePattern") != "CarPaly-XingyueL-v{versionName}.apk":
        errors.append("The version ledger must require the canonical versioned APK filename")
    if policy.get("debugApkUserDeliverable") is not False:
        errors.append("Debug APKs must not be user-deliverable")
    if policy.get("overwriteDeliveredArtifact") is not False:
        errors.append("Delivered APK artifacts must be immutable")
    if not RELEASE_BUILDER.is_file() or not RELEASE_VERIFIER.is_file():
        errors.append("Canonical Release APK build and verification scripts must both exist")
    if not (ROOT / "build-release.ps1").is_file() or not (ROOT / "scripts/ReleaseSystem.Core.psm1").is_file():
        errors.append("The Windows Release orchestrator and its core module must both exist")
    for path in LOCAL_RELEASE_DOCS:
        if not path.is_file():
            errors.append(f"Missing local Release system guide: {path.relative_to(ROOT).as_posix()}")
    for path in OLD_DELIVERY_SCRIPTS:
        if path.exists():
            errors.append(f"Obsolete Upgrade-Test delivery script remains: {path.relative_to(ROOT).as_posix()}")

    expected_status = (
        "v1.1.4",
        "v1.1.5",
        "v1.1.51",
        "v1.1.52",
        "v1.1.6",
    )
    for path in README_PATHS:
        if not path.is_file():
            errors.append(f"Missing canonical project README: {path.relative_to(ROOT).as_posix()}")
            continue
        text = path.read_text(encoding="utf-8")
        missing = [item for item in expected_status if item not in text]
        if missing:
            errors.append(f"{path.relative_to(ROOT).as_posix()} omits version status: {', '.join(missing)}")
        if "NOT_TESTED" not in text and "未实车验证" not in text and "尚未实测" not in text:
            errors.append(f"{path.relative_to(ROOT).as_posix()} lacks an explicit unverified-vehicle status")

    branding = BRANDING_SOURCE.read_text(encoding="utf-8")
    if 'const val DEFAULT_OEM_LABEL = "GEELY"' not in branding:
        errors.append("CarPlay vehicle button default label must remain GEELY")
    if "R.drawable.ic_geely_auto_2023" not in branding:
        errors.append("CarPlay vehicle button default icon must remain the Geely icon")
    if "GEELY" not in (ROOT / "README.md").read_text(encoding="utf-8"):
        errors.append("Root README must document the GEELY default branding")

    signer = ledger.get("releaseCertificateSha256", "").lower()
    if not re.fullmatch(r"[a-f0-9]{64}", signer):
        errors.append("Version ledger must pin a valid Release certificate SHA-256")
    elif signer not in SIGNING_POLICY.read_text(encoding="utf-8").lower():
        errors.append("Release signing policy does not match the version ledger certificate")

    version_policy = VERSION_POLICY.read_text(encoding="utf-8")
    for required in (
        version["versionName"],
        str(version["versionCode"]),
        "CarPaly-XingyueL-v{versionName}.apk",
        "v1.1.52",
        "v1.1.6",
    ):
        if required not in version_policy:
            errors.append(f"Version policy is missing {required}")
    signing_policy = SIGNING_POLICY.read_text(encoding="utf-8")
    if "no Debug APKs" not in signing_policy and "must not upload Debug APKs" not in signing_policy:
        errors.append("Release signing policy must forbid Debug APK delivery artifacts")
    if "signingEpochs" not in signing_policy or "41+" not in signing_policy:
        errors.append("Release signing policy must document version-code signing epochs")

    return errors


def main() -> int:
    errors = check()
    if errors:
        print("PROJECT_DOCS_STATUS=FAIL")
        for error in errors:
            print(f"- {error}")
        return 1
    ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
    current = ledger["current"]
    print(
        f"PROJECT_DOCS_STATUS=PASS versionName={current['versionName']} "
        f"versionCode={current['versionCode']} brand=GEELY vehicleValidation=NOT_TESTED"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
