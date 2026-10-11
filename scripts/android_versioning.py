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


APPLICATION_ID = "com.shihab.diplay.hudtest"
RELEASE_CERT_SHA256 = "4d26d1c861b41a2cee4515e31f5f5c7eb13b9dd06e7485aa1687bc1d2ac73d90"
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


def next_test_name(current_name: str) -> str:
    version = parse_version_tuple(current_name)
    if version is None or version[:2] != (1, 1) or version[2] < 51:
        raise ValueError("The current version is not in the 1.1.51+ test sequence")
    return f"1.1.{version[2] + 1}"


def historical_versions(root: Path, current: AndroidVersion) -> list[AndroidVersion]:
    versions: list[AndroidVersion] = []
    commits = git(root, "log", "--format=%H", "HEAD", "--", str(GRADLE_PATH)).splitlines()
    for commit in commits:
        source = git(root, "show", f"{commit}:{GRADLE_PATH}", check=False)
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
        source = git(root, "show", f"{tag}:{GRADLE_PATH}", check=False)
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
    allocations = ledger.get("allocations", [])
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
    if (
        policy.get("buildType") != "release"
        or policy.get("apkFileNamePattern") != "CarPaly-XingyueL-v{versionName}.apk"
        or policy.get("applicationId") != APPLICATION_ID
        or policy.get("releaseCertificateSha256", "").lower() != RELEASE_CERT_SHA256
        or policy.get("debugApkUserDeliverable") is not False
        or policy.get("overwriteDeliveredArtifact") is not False
    ):
        raise ValueError("Version ledger does not enforce the permanent Release APK delivery policy")
    historical = ledger.get("verifiedHistoricalDeliveries", [])
    historical_names = [item["versionName"] for item in historical]
    historical_codes = [item["versionCode"] for item in historical]
    if len(historical_names) != len(set(historical_names)) or len(historical_codes) != len(set(historical_codes)):
        raise ValueError("Verified historical deliveries reuse a versionName or versionCode")
    if set(historical_names).intersection(names) or set(historical_codes).intersection(codes):
        raise ValueError("An allocated versionName or versionCode conflicts with a published historical version")
    if any(item.get("status") != "published" for item in historical):
        raise ValueError("Historical version records must describe verified published deliveries")
    if ledger.get("highestObservedVersionCode", 0) < max(historical_codes, default=0):
        raise ValueError("The Android version-code high-water mark is below a published historical version")


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


def check_project(root: Path) -> AndroidVersion:
    source = (root / GRADLE_PATH).read_text(encoding="utf-8")
    version = parse_gradle_version(source)
    ledger = read_ledger(root)
    validate_ledger(ledger)
    current = ledger["current"]

    if version.application_id != APPLICATION_ID or ledger.get("applicationId") != APPLICATION_ID:
        raise ValueError("CarPaly applicationId changed; upgrade continuity is not verified")
    if (version.version_name, version.version_code) != (current["versionName"], current["versionCode"]):
        raise ValueError("Gradle versionName/versionCode differs from the reserved version ledger")
    if ledger.get("releaseCertificateSha256", "").lower() != RELEASE_CERT_SHA256:
        raise ValueError("Version ledger signer does not match the fixed v1.1.4 Release identity")
    if re.search(r"(?m)^\s*applicationIdSuffix\s*=", source) or re.search(
        r"(?m)^\s*versionNameSuffix\s*=", source
    ):
        raise ValueError("Unexpected applicationId/versionName suffix can break upgrade identity")
    if RELEASE_CERT_SHA256 not in source:
        raise ValueError("Gradle Release signer pin is missing")

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
    if version.version_code <= highest_previous:
        raise ValueError(
            f"versionCode {version.version_code} must exceed all previous known values ({highest_previous})"
        )
    return version


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
    update_gradle_version(root, version.version_name, version.version_code)
    allocation = {
        "versionName": version.version_name,
        "versionCode": version.version_code,
        "channel": channel,
        "status": "reserved",
        "artifactSha256": None,
    }
    ledger["current"] = {
        "versionName": version.version_name,
        "versionCode": version.version_code,
        "channel": channel,
    }
    ledger["allocations"].append(allocation)
    write_ledger(root, ledger)
    return version


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("check", "next-test", "final-release"))
    parser.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    root = args.project_root.resolve()

    try:
        if args.command == "check":
            version = check_project(root)
            print(
                f"VERSIONING_STATUS=PASS versionName={version.version_name} "
                f"versionCode={version.version_code} applicationId={version.application_id}"
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
