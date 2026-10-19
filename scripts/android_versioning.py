#!/usr/bin/env python3
"""Validate and allocate monotonic CarPaly Android versions."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

try:
    from scripts.release_signing_policy import (
        LEGACY_RELEASE_CERT_SHA256,
        approved_epoch_for_version_code,
        normalize_sha256,
        signer_for_ledger_version,
        signing_epoch_for_version_code,
        validate_signing_epoch_configuration,
    )
except ModuleNotFoundError:  # Direct `python scripts/android_versioning.py ...` execution.
    from release_signing_policy import (
        LEGACY_RELEASE_CERT_SHA256,
        approved_epoch_for_version_code,
        normalize_sha256,
        signer_for_ledger_version,
        signing_epoch_for_version_code,
        validate_signing_epoch_configuration,
    )


APPLICATION_ID = "com.shihab.diplay.hudtest"
GRADLE_PATH = Path("mobile/build.gradle.kts")
LEDGER_PATH = Path("config/android-version-ledger.json")
VERSION_FIELDS = {
    "applicationId": re.compile(r'^\s*applicationId\s*=\s*"([^"]+)"\s*$', re.M),
    "versionCode": re.compile(r"^\s*versionCode\s*=\s*(\d+)\s*$", re.M),
    "versionName": re.compile(r'^\s*versionName\s*=\s*"([^"]+)"\s*$', re.M),
}


@dataclass(frozen=True)
class AndroidVersion:
    application_id: str
    version_name: str
    version_code: int


def parse_gradle_version(source: str) -> AndroidVersion:
    values: dict[str, str] = {}
    for name, pattern in VERSION_FIELDS.items():
        found = pattern.findall(source)
        if len(found) != 1:
            raise ValueError(f"Expected exactly one {name} declaration in mobile/build.gradle.kts")
        values[name] = found[0]
    return AndroidVersion(values["applicationId"], values["versionName"], int(values["versionCode"]))


def git(root: Path, *args: str, check: bool = True) -> str:
    result = subprocess.run(
        ["git", *args], cwd=root, check=check, text=True, capture_output=True
    )
    return result.stdout.strip()


def read_ledger(root: Path) -> dict:
    return json.loads((root / LEDGER_PATH).read_text(encoding="utf-8"))


def write_ledger(root: Path, ledger: dict) -> None:
    (root / LEDGER_PATH).write_text(
        json.dumps(ledger, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def parse_version_tuple(name: str) -> tuple[int, int, int] | None:
    match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", name)
    return tuple(map(int, match.groups())) if match else None


def signing_epoch_for_version(ledger: dict, version_code: int) -> dict | None:
    """Return the unique signer epoch covering a versionCode, or fail closed."""
    return signing_epoch_for_version_code(ledger.get("signingEpochs"), version_code)


def signer_for_version(ledger: dict, version_name: str, version_code: int) -> str | None:
    """Return a signer's public fingerprint only when the ledger record agrees with its epoch."""
    return signer_for_ledger_version(ledger, version_name, version_code)


def next_test_name(current_name: str) -> str:
    version = parse_version_tuple(current_name)
    if version is None or version[:2] != (1, 1) or version[2] < 51:
        raise ValueError("The current version is not in the 1.1.51+ test sequence")
    return f"1.1.{version[2] + 1}"


def historical_versions(root: Path, current: AndroidVersion) -> list[AndroidVersion]:
    versions: list[AndroidVersion] = []
    git_gradle_path = GRADLE_PATH.as_posix()
    commits = git(root, "log", "--format=%H", "HEAD", "--", git_gradle_path).splitlines()
    for commit in commits:
        source = git(root, "show", f"{commit}:{git_gradle_path}", check=False)
        if not source:
            continue
        try:
            version = parse_gradle_version(source)
        except ValueError:
            continue
        if (version.version_name, version.version_code) != (current.version_name, current.version_code):
            versions.append(version)

    # A release tag can be outside the current branch ancestry; include this project's v1.x tags.
    for tag in git(root, "tag", "--list", "v1.*").splitlines():
        if not re.fullmatch(r"v1\.\d+\.\d+", tag):
            continue
        source = git(root, "show", f"{tag}:{git_gradle_path}", check=False)
        if not source:
            continue
        try:
            version = parse_gradle_version(source)
        except ValueError:
            continue
        if (version.version_name, version.version_code) != (current.version_name, current.version_code):
            versions.append(version)
    return versions


def validate_ledger(ledger: dict) -> None:
    if not isinstance(ledger, dict):
        raise ValueError("The Android version ledger must be a JSON object")
    validate_signing_epoch_configuration(ledger)
    allocations = ledger.get("allocations", [])
    if not isinstance(allocations, list) or not all(isinstance(item, dict) for item in allocations):
        raise ValueError("The Android version ledger allocations are malformed")
    names = [item["versionName"] for item in allocations]
    codes = [item["versionCode"] for item in allocations]
    if len(names) != len(set(names)):
        raise ValueError("The version ledger reuses a versionName")
    if len(codes) != len(set(codes)):
        raise ValueError("The version ledger reuses a versionCode")
    current = ledger.get("current", {})
    if not any(
        item["versionName"] == current.get("versionName")
        and item["versionCode"] == current.get("versionCode")
        and item["channel"] == current.get("channel")
        for item in allocations
    ):
        raise ValueError("The current version assignment is absent from the immutable allocation ledger")
    policy = ledger.get("deliveryPolicy", {})
    if not isinstance(policy, dict):
        raise ValueError("The Android version delivery policy is malformed")
    if (
        policy.get("buildType") != "release"
        or policy.get("apkFileNamePattern") != "CarPaly-XingyueL-v{versionName}.apk"
        or policy.get("applicationId") != APPLICATION_ID
        or policy.get("legacyReleaseCertificateSha256", "").lower() != LEGACY_RELEASE_CERT_SHA256
        or policy.get("debugApkUserDeliverable") is not False
        or policy.get("overwriteDeliveredArtifact") is not False
    ):
        raise ValueError("Version ledger does not enforce the permanent Release APK delivery policy")
    historical = ledger.get("verifiedHistoricalDeliveries", [])
    if not isinstance(historical, list) or not all(isinstance(item, dict) for item in historical):
        raise ValueError("The verified historical delivery records are malformed")
    historical_names = [item["versionName"] for item in historical]
    historical_codes = [item["versionCode"] for item in historical]
    if len(historical_names) != len(set(historical_names)) or len(historical_codes) != len(set(historical_codes)):
        raise ValueError("Verified historical deliveries reuse a versionName or versionCode")
    if set(historical_names).intersection(names) or set(historical_codes).intersection(codes):
        raise ValueError("An allocated versionName or versionCode conflicts with a published historical version")
    if any(item.get("status") != "published" for item in historical):
        raise ValueError("Historical version records must describe verified published deliveries")
    all_record_codes = codes + historical_codes
    if ledger.get("highestObservedVersionCode", 0) < max(all_record_codes, default=0):
        raise ValueError("The Android version-code high-water mark is below a known allocation or delivery")

    for record in [*allocations, *historical]:
        if signer_for_version(ledger, record["versionName"], record["versionCode"]) is None:
            raise ValueError(
                f"Version {record['versionName']} has missing or mismatched signing-epoch evidence"
            )

    epoch = signing_epoch_for_version(ledger, current["versionCode"])
    current_signer = signer_for_version(ledger, current["versionName"], current["versionCode"])
    if (
        epoch is None
        or current.get("signingEpochId") != epoch.get("id")
        or current_signer is None
        or normalize_sha256(ledger.get("releaseCertificateSha256")) != current_signer
        or normalize_sha256(policy.get("releaseCertificateSha256")) != current_signer
    ):
        raise ValueError("Current version signer and active Release signer policy do not match its signing epoch")


def require_current_delivery_recorded(ledger: dict) -> None:
    current = ledger["current"]
    allocation = next(
        (
            item
            for item in ledger["allocations"]
            if item["versionName"] == current["versionName"]
            and item["versionCode"] == current["versionCode"]
            and item["channel"] == current["channel"]
        ),
        None,
    )
    if allocation is None or allocation.get("status") != "delivered" or not re.fullmatch(
        r"[a-f0-9]{64}", (allocation.get("artifactSha256") or "").lower()
    ):
        raise ValueError(
            "The current version must have a verified Release APK delivery SHA-256 before another version is allocated"
        )


def check_project(root: Path, *, enforce_historical_high_water: bool = True) -> AndroidVersion:
    source = (root / GRADLE_PATH).read_text(encoding="utf-8")
    version = parse_gradle_version(source)
    ledger = read_ledger(root)
    validate_ledger(ledger)
    current = ledger["current"]

    if version.application_id != APPLICATION_ID or ledger.get("applicationId") != APPLICATION_ID:
        raise ValueError("CarPaly applicationId changed; upgrade continuity is not verified")
    if (version.version_name, version.version_code) != (current["versionName"], current["versionCode"]):
        raise ValueError("Gradle versionName/versionCode differs from the reserved version ledger")
    expected_signer = signer_for_version(ledger, current["versionName"], current["versionCode"])
    epoch = signing_epoch_for_version(ledger, current["versionCode"])
    if (
        expected_signer is None
        or epoch is None
        or current.get("signingEpochId") != epoch.get("id")
        or normalize_sha256(ledger.get("releaseCertificateSha256")) != expected_signer
        or normalize_sha256(ledger.get("deliveryPolicy", {}).get("releaseCertificateSha256")) != expected_signer
    ):
        raise ValueError("Current version does not match its reviewed signing epoch")
    if re.search(r"(?m)^\s*applicationIdSuffix\s*=", source) or re.search(
        r"(?m)^\s*versionNameSuffix\s*=", source
    ):
        raise ValueError("Unexpected applicationId/versionName suffix can break upgrade identity")
    if "releaseSignerForVersion(configuredVersionCode)" not in source or "signingEpochs" not in source:
        raise ValueError("Gradle Release signing preflight does not resolve the current signing epoch")

    if current["channel"] == "test":
        parsed = parse_version_tuple(version.version_name)
        if parsed is None or parsed[:2] != (1, 1) or parsed[2] < 51:
            raise ValueError("Test builds must use the 1.1.51+ version sequence")
    elif current["channel"] == "release":
        if version.version_name != "1.1.6":
            raise ValueError("The planned stable release version must be 1.1.6")
    else:
        raise ValueError("Version channel must be test or release")

    history = historical_versions(root, version)
    allocated_codes = [
        item["versionCode"]
        for item in ledger["allocations"]
        if (item["versionName"], item["versionCode"])
        != (version.version_name, version.version_code)
    ]
    highest_previous = max(
        [ledger.get("highestObservedVersionCode", 0)]
        + [item.version_code for item in history]
        + [item["versionCode"] for item in ledger.get("verifiedHistoricalDeliveries", [])]
        + allocated_codes
    )
    if enforce_historical_high_water and version.version_code < highest_previous:
        raise ValueError(
            f"versionCode {version.version_code} is below the highest observed value ({highest_previous})"
        )
    return version


def check_ci_project(root: Path) -> AndroidVersion:
    """Check branch metadata consistency without treating rebuild-only tags as a new allocation.

    Release builds and version allocation must continue to use ``check_project`` so a stale
    source version cannot be delivered or used to allocate another version.
    """
    return check_project(root, enforce_historical_high_water=False)


def update_gradle_version(root: Path, version_name: str, version_code: int) -> None:
    path = root / GRADLE_PATH
    source = path.read_text(encoding="utf-8")
    updated, code_count = re.subn(
        r"(?m)^(\s*versionCode\s*=\s*)\d+(\s*)$",
        rf"\g<1>{version_code}\g<2>",
        source,
    )
    if code_count != 1:
        raise ValueError("Could not update exactly one Gradle versionCode")
    updated, name_count = re.subn(
        r'(?m)^(\s*versionName\s*=\s*)"[^"]+"(\s*)$',
        rf'\g<1>"{version_name}"\g<2>',
        updated,
    )
    if name_count != 1:
        raise ValueError("Could not update exactly one Gradle versionName")
    path.write_text(updated, encoding="utf-8")


def allocate(root: Path, channel: str) -> AndroidVersion:
    current_version = check_project(root)
    ledger = read_ledger(root)
    require_current_delivery_recorded(ledger)
    if channel == "test":
        version_name = next_test_name(current_version.version_name)
    else:
        if current_version.version_name == "1.1.6":
            raise ValueError("The final 1.1.6 release version is already reserved")
        version_name = "1.1.6"

    if any(item["versionName"] == version_name for item in ledger["allocations"]):
        raise ValueError(f"Version {version_name} has already been allocated")
    history = historical_versions(root, current_version)
    highest = max(
        [ledger.get("highestObservedVersionCode", 0), current_version.version_code]
        + [item.version_code for item in history]
        + [item["versionCode"] for item in ledger.get("verifiedHistoricalDeliveries", [])]
        + [item["versionCode"] for item in ledger["allocations"]]
    )
    version = AndroidVersion(APPLICATION_ID, version_name, highest + 1)
    epoch = approved_epoch_for_version_code(version.version_code)
    if epoch is None:
        raise ValueError(f"No reviewed Release signing epoch covers versionCode {version.version_code}")
    update_gradle_version(root, version.version_name, version.version_code)
    allocation = {
        "versionName": version.version_name,
        "versionCode": version.version_code,
        "channel": channel,
        "status": "reserved",
        "artifactSha256": None,
        "signerCertificateSha256": epoch["certificateSha256"],
        "signingEpochId": epoch["id"],
        "upgradePolicy": "fresh-install-required" if version.version_code == 41 else "same-signer-upgrade-only",
    }
    ledger["current"] = {
        "versionName": version.version_name,
        "versionCode": version.version_code,
        "channel": channel,
        "signingEpochId": epoch["id"],
    }
    ledger["highestObservedVersionCode"] = version.version_code
    ledger["releaseCertificateSha256"] = epoch["certificateSha256"]
    ledger["deliveryPolicy"]["releaseCertificateSha256"] = epoch["certificateSha256"]
    ledger["allocations"].append(allocation)
    write_ledger(root, ledger)
    return version


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("check", "check-ci", "next-test", "final-release"))
    parser.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    root = args.project_root.resolve()

    try:
        if args.command in ("check", "check-ci"):
            version = check_project(
                root, enforce_historical_high_water=args.command == "check"
            )
            print(
                f"VERSIONING_STATUS=PASS versionName={version.version_name} "
                f"versionCode={version.version_code} applicationId={version.application_id} "
                f"historicalHighWater={'enforced' if args.command == 'check' else 'release-gated'}"
            )
        else:
            channel = "test" if args.command == "next-test" else "release"
            version = allocate(root, channel)
            print(
                f"VERSION_RESERVED versionName={version.version_name} "
                f"versionCode={version.version_code}; run the signing and APK verification gates before delivery"
            )
        return 0
    except (OSError, ValueError, KeyError, json.JSONDecodeError, subprocess.CalledProcessError) as error:
        print(f"VERSIONING_STATUS=FAIL {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
