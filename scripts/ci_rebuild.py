#!/usr/bin/env python3
"""Resolve and validate immutable historical CarPaly build sources."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


SHA1 = re.compile(r"^[0-9a-f]{40}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
VERSION = re.compile(r"^\d+\.\d+\.\d+$")
APP_ID = "com.shihab.diplay.hudtest"


class PolicyError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def normalize_version(value: str) -> str:
    version = value[1:] if value.startswith("v") else value
    if not VERSION.fullmatch(version):
        raise PolicyError("VERSION_INVALID", "version must use numeric dotted form")
    return version


def normalize_sha256(value: str, *, label: str) -> str:
    # Accept only common fingerprint presentation differences. Silently
    # dropping arbitrary characters could turn malformed input into a match.
    normalized = re.sub(r"[:\s]", "", value).lower()
    if not SHA256.fullmatch(normalized):
        raise PolicyError("FINGERPRINT_INVALID", f"{label} must be a SHA-256 hex digest")
    return normalized


def load_manifest(path: Path) -> dict[str, Any]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PolicyError("MANIFEST_INVALID", "build source manifest cannot be read") from exc
    if document.get("schemaVersion") != 1 or document.get("packageName") != APP_ID:
        raise PolicyError("MANIFEST_INVALID", "unsupported schema or package name")
    versions = document.get("versions")
    if not isinstance(versions, list) or not versions:
        raise PolicyError("MANIFEST_INVALID", "versions must be a non-empty array")

    names: set[str] = set()
    codes: set[int] = set()
    for entry in versions:
        if not isinstance(entry, dict):
            raise PolicyError("MANIFEST_INVALID", "version entry must be an object")
        name = normalize_version(str(entry.get("versionName", "")))
        code = entry.get("versionCode")
        if name in names or not isinstance(code, int) or isinstance(code, bool) or code <= 0 or code in codes:
            raise PolicyError("MANIFEST_INVALID", "version names and codes must be unique and positive")
        names.add(name)
        codes.add(code)
        state = entry.get("sourceStatus")
        source = entry.get("sourceCommit")
        if state not in {"verified", "source-unverified", "tag-bound"}:
            raise PolicyError("MANIFEST_INVALID", f"unsupported source status for {name}")
        if state == "verified" and (not isinstance(source, str) or not SHA1.fullmatch(source)):
            raise PolicyError("MANIFEST_INVALID", f"verified source for {name} needs an immutable commit SHA")
        if state in {"source-unverified", "tag-bound"} and source is not None:
            raise PolicyError("MANIFEST_INVALID", f"{state} source for {name} must not claim a commit SHA")
        original_sha = entry.get("originalApkSha256")
        if original_sha is not None and not SHA256.fullmatch(str(original_sha)):
            raise PolicyError("MANIFEST_INVALID", f"original APK hash for {name} is malformed")
        signer = entry.get("signerCertificateSha256")
        if not isinstance(signer, str) or not SHA256.fullmatch(signer):
            raise PolicyError("MANIFEST_INVALID", f"signer fingerprint for {name} is malformed")

    return document


def find_entry(document: dict[str, Any], version: str) -> dict[str, Any]:
    normalized = normalize_version(version)
    for entry in document["versions"]:
        if entry["versionName"] == normalized:
            return entry
    raise PolicyError("VERSION_NOT_MAPPED", f"{normalized} is not in the reviewed rebuild source map")


def parse_source_metadata(gradle_text: str, ledger: dict[str, Any], entry: dict[str, Any]) -> None:
    app_match = re.search(r'applicationId\s*=\s*["\']([^"\']+)["\']', gradle_text)
    code_match = re.search(r"versionCode\s*=\s*(\d+)", gradle_text)
    name_match = re.search(r'versionName\s*=\s*["\']([^"\']+)["\']', gradle_text)
    signer_match = re.search(
        r'CARPALY_RELEASE_CERT_SHA256\s*=\s*[\r\n\s]*["\']([0-9a-fA-F]{64})["\']',
        gradle_text,
    )
    if not all((app_match, code_match, name_match, signer_match)):
        raise PolicyError("SOURCE_METADATA_MISSING", "Gradle source lacks package, version, or signer metadata")

    app_id = app_match.group(1)
    code = int(code_match.group(1))
    name = name_match.group(1)
    signer = normalize_sha256(signer_match.group(1), label="Gradle signer")
    expected_signer = normalize_sha256(entry["signerCertificateSha256"], label="manifest signer")
    if app_id != APP_ID or app_id != ledger.get("applicationId"):
        raise PolicyError("PACKAGE_MISMATCH", "source package name differs from the pinned application ID")
    if name != entry["versionName"] or code != entry["versionCode"]:
        raise PolicyError("VERSION_MISMATCH", "Gradle version differs from the rebuild manifest")
    if signer != expected_signer or signer != normalize_sha256(
        str(ledger.get("releaseCertificateSha256", "")), label="ledger signer"
    ):
        raise PolicyError("SIGNER_POLICY_MISMATCH", "Gradle and version-ledger signer identities disagree")

    allocations = ledger.get("allocations", [])
    allocation = next(
        (item for item in allocations if item.get("versionName") == name and item.get("versionCode") == code),
        None,
    )
    if allocation is None:
        raise PolicyError("LEDGER_ALLOCATION_MISSING", "version allocation is absent from the source ledger")
    allocated_signer = allocation.get("signerCertificateSha256")
    if not isinstance(allocated_signer, str) or normalize_sha256(
        allocated_signer, label="allocated signer"
    ) != expected_signer:
        raise PolicyError("SIGNER_POLICY_MISMATCH", "version allocation signer differs from the rebuild manifest")


def git_text(repo: Path, revision: str, file_path: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), "show", f"{revision}:{file_path}"],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise PolicyError("SOURCE_COMMIT_UNAVAILABLE", "pinned source commit or required file is unavailable")
    return result.stdout


def verify_pinned_git_source(repo: Path, entry: dict[str, Any]) -> None:
    commit = entry.get("sourceCommit")
    if entry.get("sourceStatus") != "verified" or not isinstance(commit, str):
        raise PolicyError("SOURCE_UNVERIFIED", "this version has no verified immutable source commit")
    exists = subprocess.run(
        ["git", "-C", str(repo), "cat-file", "-e", f"{commit}^{{commit}}"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if exists.returncode != 0:
        raise PolicyError("SOURCE_COMMIT_UNAVAILABLE", "pinned source commit is not present in this checkout")
    gradle = git_text(repo, commit, "mobile/build.gradle.kts")
    ledger_text = git_text(repo, commit, "config/android-version-ledger.json")
    try:
        ledger = json.loads(ledger_text)
    except json.JSONDecodeError as exc:
        raise PolicyError("SOURCE_METADATA_INVALID", "source version ledger is not valid JSON") from exc
    parse_source_metadata(gradle, ledger, entry)


def verify_checked_out_source(repo: Path, entry: dict[str, Any], expected_commit: str) -> None:
    head = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        text=True,
        capture_output=True,
        check=False,
    )
    actual_commit = head.stdout.strip().lower() if head.returncode == 0 else ""
    if actual_commit != expected_commit.lower():
        raise PolicyError("SOURCE_CHECKOUT_MISMATCH", "checked-out source does not match the resolved commit")
    try:
        gradle = (repo / "mobile/build.gradle.kts").read_text(encoding="utf-8")
        ledger = json.loads((repo / "config/android-version-ledger.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PolicyError("SOURCE_METADATA_INVALID", "checked-out source metadata cannot be read") from exc
    parse_source_metadata(gradle, ledger, entry)


def resolve_version(
    document: dict[str, Any],
    version: str,
    *,
    event_name: str,
    ref: str,
    current_commit: str,
    tag_name: str = "",
    tag_sha: str = "",
    build_type: str = "verify",
) -> tuple[dict[str, Any], str]:
    entry = find_entry(document, version)
    state = entry["sourceStatus"]
    if state == "source-unverified":
        raise PolicyError("SOURCE_UNVERIFIED", f"no exact source commit is proven for {entry['versionName']}")

    if event_name == "push" and ref.startswith("refs/tags/"):
        expected_tag = f"v{entry['versionName']}"
        if tag_name != expected_tag or not SHA1.fullmatch(tag_sha.lower()):
            raise PolicyError("TAG_SOURCE_MISMATCH", "tag name or commit is invalid for this version")
        source_commit = entry.get("sourceCommit") if state == "verified" else tag_sha.lower()
        if state == "verified" and source_commit != tag_sha.lower():
            raise PolicyError("TAG_SOURCE_MISMATCH", "tag does not point to the reviewed source commit")
    elif event_name == "workflow_dispatch":
        if build_type == "release" and ref != "refs/heads/main":
            raise PolicyError("RELEASE_REF_NOT_MAIN", "signed candidate builds may only be dispatched from main")
        if state == "verified":
            source_commit = entry["sourceCommit"]
        else:
            if ref != "refs/heads/main" or not SHA1.fullmatch(current_commit.lower()):
                raise PolicyError("TAG_BOUND_SOURCE_REQUIRES_MAIN", "tag-bound builds require a main-branch dispatch")
            source_commit = current_commit.lower()
    else:
        raise PolicyError("BUILD_EVENT_UNSUPPORTED", "historical builds require workflow_dispatch or a version tag")

    return entry, source_commit


def verify_tag_intent(
    entry: dict[str, Any], *, tag_name: str, tag_sha: str, main_sha: str, intent: dict[str, Any]
) -> None:
    version = entry["versionName"]
    if tag_name != f"v{version}" or not SHA1.fullmatch(tag_sha.lower()) or tag_sha.lower() != main_sha.lower():
        raise PolicyError("TAG_NOT_EXACT_MAIN", "release tag must point to the exact current main commit")
    if intent.get("enabled") is not True:
        raise PolicyError("RELEASE_INTENT_DISABLED", "release-intent.enabled is not true on the tagged main commit")
    if intent.get("versionName") != version or intent.get("versionCode") != entry["versionCode"]:
        raise PolicyError("RELEASE_INTENT_MISMATCH", "release intent does not match the tagged version")


def check_signer_pin(expected: str, actual: str) -> None:
    expected_normalized = normalize_sha256(expected, label="source signer")
    actual_normalized = normalize_sha256(actual, label="Environment signer pin")
    if expected_normalized != actual_normalized:
        raise PolicyError(
            "ENVIRONMENT_SIGNER_MISMATCH",
            f"source requires {expected_normalized}; mfi-public-release is pinned to {actual_normalized}",
        )


def write_output(entry: dict[str, Any], source_commit: str, output: Path | None) -> None:
    values = {
        "version_name": entry["versionName"],
        "version_code": str(entry["versionCode"]),
        "source_commit": source_commit,
        "original_apk_sha256": entry.get("originalApkSha256") or "none",
        "expected_signer_sha256": entry["signerCertificateSha256"],
        "package_name": APP_ID,
    }
    text = "".join(f"{key}={value}\n" for key, value in values.items())
    if output is None:
        sys.stdout.write(text)
    else:
        with output.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(text)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=Path("config/ci-rebuild-sources.json"))
    commands = parser.add_subparsers(dest="command", required=True)

    check = commands.add_parser("check-manifest")
    check.add_argument("--verify-sources", action="store_true")
    check.add_argument("--repo", type=Path, default=Path.cwd())

    resolve = commands.add_parser("resolve")
    resolve.add_argument("--version", required=True)
    resolve.add_argument("--event-name", required=True)
    resolve.add_argument("--ref", required=True)
    resolve.add_argument("--current-commit", default="")
    resolve.add_argument("--tag-name", default="")
    resolve.add_argument("--tag-sha", default="")
    resolve.add_argument("--build-type", choices=("verify", "release"), default="verify")
    resolve.add_argument("--output", type=Path)

    source = commands.add_parser("verify-source")
    source.add_argument("--version", required=True)
    source.add_argument("--source-commit", required=True)
    source.add_argument("--repo", type=Path, required=True)

    gate = commands.add_parser("verify-tag-intent")
    gate.add_argument("--version", required=True)
    gate.add_argument("--tag-name", required=True)
    gate.add_argument("--tag-sha", required=True)
    gate.add_argument("--main-sha", required=True)
    gate.add_argument("--repo", type=Path, required=True)

    pin = commands.add_parser("check-signer-pin")
    pin.add_argument("--expected", required=True)
    pin.add_argument("--actual", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        document = load_manifest(args.manifest)
        if args.command == "check-manifest":
            verified = [entry for entry in document["versions"] if entry["sourceStatus"] == "verified"]
            if args.verify_sources:
                for entry in verified:
                    verify_pinned_git_source(args.repo, entry)
            print(
                "CI_REBUILD_MANIFEST_STATUS=PASS "
                f"versions={len(document['versions'])} verified_sources={len(verified)}"
            )
            return 0
        if args.command == "resolve":
            entry, source_commit = resolve_version(
                document,
                args.version,
                event_name=args.event_name,
                ref=args.ref,
                current_commit=args.current_commit,
                tag_name=args.tag_name,
                tag_sha=args.tag_sha,
                build_type=args.build_type,
            )
            write_output(entry, source_commit, args.output)
            return 0
        if args.command == "verify-source":
            entry = find_entry(document, args.version)
            verify_checked_out_source(args.repo, entry, args.source_commit)
            print(f"SOURCE_METADATA_STATUS=PASS version={entry['versionName']} source_commit={args.source_commit}")
            return 0
        if args.command == "verify-tag-intent":
            entry = find_entry(document, args.version)
            verify_checked_out_source(args.repo, entry, args.tag_sha)
            intent = json.loads((args.repo / "config/release-intent.json").read_text(encoding="utf-8"))
            verify_tag_intent(
                entry,
                tag_name=args.tag_name,
                tag_sha=args.tag_sha,
                main_sha=args.main_sha,
                intent=intent,
            )
            print(f"TAG_RELEASE_GATE=PASS version={entry['versionName']} commit={args.tag_sha}")
            return 0
        if args.command == "check-signer-pin":
            check_signer_pin(args.expected, args.actual)
            print(f"ENVIRONMENT_SIGNER_PIN=PASS sha256={normalize_sha256(args.actual, label='pin')}")
            return 0
        raise PolicyError("COMMAND_INVALID", "unknown command")
    except (PolicyError, OSError, json.JSONDecodeError) as exc:
        code = exc.code if isinstance(exc, PolicyError) else "VALIDATION_ERROR"
        print(f"{code}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
