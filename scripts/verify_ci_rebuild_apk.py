#!/usr/bin/env python3
"""Verify a CI-built Release APK and emit a credential-free candidate report."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import zipfile
from pathlib import Path


class VerificationError(ValueError):
    pass


def normalize_sha256(value: str) -> str:
    normalized = re.sub(r"[^0-9a-fA-F]", "", value).lower()
    if not re.fullmatch(r"[0-9a-f]{64}", normalized):
        raise VerificationError("tool output did not include a valid SHA-256 digest")
    return normalized


def run_tool(command: list[str]) -> str:
    result = subprocess.run(command, text=True, capture_output=True, check=False)
    if result.returncode != 0:
        raise VerificationError(f"validation tool failed: {Path(command[0]).name}")
    return result.stdout + "\n" + result.stderr


def verify(args: argparse.Namespace) -> dict[str, object]:
    apk = args.apk.resolve(strict=True)
    if apk.name != "mobile-release.apk" or apk.parent.name.lower() != "release":
        raise VerificationError("APK path is not the expected Release variant output")
    if apk.stat().st_size <= 0:
        raise VerificationError("APK is empty")

    try:
        with zipfile.ZipFile(apk) as archive:
            if archive.testzip() is not None:
                raise VerificationError("APK ZIP CRC check failed")
            entries = {item.filename for item in archive.infolist() if item.file_size > 0}
    except (OSError, zipfile.BadZipFile) as exc:
        raise VerificationError("APK ZIP structure is invalid") from exc

    auth_entries = {
        "assets/offline-mfi/identity.pk8",
        "assets/offline-mfi/certificate.p7b",
    }
    if not auth_entries.issubset(entries):
        raise VerificationError("required authenticated runtime assets are absent")

    signer_output = run_tool([str(args.apksigner), "verify", "--verbose", "--print-certs", str(apk)])
    signer_match = re.search(
        r"Signer\s+#1\s+certificate\s+SHA-256\s+digest:\s*([0-9a-fA-F: ]+)",
        signer_output,
        re.IGNORECASE,
    )
    if not signer_match:
        raise VerificationError("apksigner output did not include signer SHA-256")
    signer = normalize_sha256(signer_match.group(1))
    if signer != normalize_sha256(args.expected_signer):
        raise VerificationError("APK signer differs from the version-pinned signer")

    badging = run_tool([str(args.aapt), "dump", "badging", str(apk)])
    package_match = re.search(
        r"package:\s+name='([^']+)'\s+versionCode='([^']+)'\s+versionName='([^']+)'", badging
    )
    if not package_match:
        raise VerificationError("aapt could not read package and version metadata")
    package, code_text, name = package_match.groups()
    if package != args.package or name != args.version_name or code_text != str(args.version_code):
        raise VerificationError("APK package or version does not match the pinned source metadata")
    if re.search(r"application-debuggable", badging, re.IGNORECASE):
        raise VerificationError("Release APK is marked debuggable")

    apk_sha = hashlib.sha256(apk.read_bytes()).hexdigest()
    report: dict[str, object] = {
        "schemaVersion": 1,
        "buildResult": "PASS",
        "buildVariant": "release",
        "sourceCommit": args.source_commit.lower(),
        "packageName": package,
        "versionName": name,
        "versionCode": int(code_text),
        "apkFileName": args.output_name,
        "apkSizeBytes": apk.stat().st_size,
        "rebuildApkSha256": apk_sha,
        "originalApkSha256": args.original_apk_sha256 if args.original_apk_sha256 != "none" else None,
        "signerCertificateSha256": signer,
        "apkSignatureVerification": "PASS",
        "apkZipIntegrity": "PASS",
        "debuggable": False,
        "runtimeAuthenticationAssetsPresent": True,
        "distributionStatus": "DISTRIBUTION_BLOCKED",
        "distributionReason": "The APK contains assets/offline-mfi/identity.pk8; APK upload is disabled for this public repository.",
        "apkUploaded": False,
        "releaseCreated": False,
        "otaEnabled": False,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apk", required=True, type=Path)
    parser.add_argument("--apksigner", required=True, type=Path)
    parser.add_argument("--aapt", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--version-name", required=True)
    parser.add_argument("--version-code", required=True, type=int)
    parser.add_argument("--package", required=True)
    parser.add_argument("--expected-signer", required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--original-apk-sha256", required=True)
    parser.add_argument("--output-name", required=True)
    args = parser.parse_args(argv)
    try:
        report = verify(args)
    except (OSError, VerificationError) as exc:
        print(f"APK_VALIDATION_STATUS=FAIL reason={exc}", file=sys.stderr)
        return 1
    print(
        "APK_VALIDATION_STATUS=PASS "
        f"version={report['versionName']} code={report['versionCode']} "
        f"sha256={report['rebuildApkSha256']} distribution={report['distributionStatus']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
