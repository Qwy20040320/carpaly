#!/usr/bin/env python3
"""Safely copy a verified user APK from any CarPaly worktree to the primary checkout.

This is intentionally a local-only delivery helper. It does not upload artifacts.
The caller must first run verify-release-apk.ps1; this helper validates that
verifier's PASS report again before touching the primary artifacts directory.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any, Iterable


REQUIRED_VERIFIER_CHECKS = (
    "APK_SIGNATURE",
    "PACKAGE_NAME_MATCH",
    "VERSION_CODE_INCREMENT",
    "MIN_SDK",
    "RELEASE_VARIANT_NOT_DEBUGGABLE",
    "AUTH_ASSETS_MATCH_LOCAL_INPUTS",
    "NATIVE_ABI",
    "APK_ZIP_INTEGRITY",
    "SIGNING_CERTIFICATE_MATCH",
)
REPARSE_POINT_FLAG = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)


class DeliveryError(RuntimeError):
    """A fail-closed artifact delivery error."""


def _run_git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode:
        raise DeliveryError(f"Git could not verify the project/worktree ({args[0]}).")
    return result.stdout.strip()


def _canonical(path: Path) -> Path:
    # Keep the original spelling for accurate reports and allow-list matching.
    # pathlib's WindowsPath equality is case-insensitive; use normcase only at
    # explicit string-comparison boundaries.
    return Path(os.path.abspath(os.fspath(path)))


def is_reparse_path(path: Path) -> bool:
    """Return true for symlinks, junctions, and Windows reparse points."""
    try:
        info = path.lstat()
    except FileNotFoundError:
        return False
    attributes = getattr(info, "st_file_attributes", 0)
    return path.is_symlink() or bool(attributes & REPARSE_POINT_FLAG)


def ensure_no_reparse_components(path: Path) -> None:
    """Reject an existing symlink/junction anywhere along a path."""
    absolute = Path(os.path.abspath(os.fspath(path)))
    current = Path(absolute.anchor)
    for part in absolute.parts[1:]:
        current = current / part
        if is_reparse_path(current):
            raise DeliveryError(f"Refusing a reparse-point path component: {current}")


def _ensure_project_root(root: Path) -> Path:
    root = _canonical(root)
    ensure_no_reparse_components(root)
    ensure_no_reparse_components(root / ".git")
    if not root.is_dir() or not (root / "settings.gradle.kts").is_file():
        raise DeliveryError("The selected path is not a CarPaly project checkout.")
    if not (root / "mobile" / "build.gradle.kts").is_file():
        raise DeliveryError("The selected checkout is missing the mobile application module.")
    return root


def _common_git_dir(root: Path) -> Path:
    value = _run_git(root, "rev-parse", "--path-format=absolute", "--git-common-dir")
    path = Path(value)
    if not path.is_absolute():
        path = root / path
    return _canonical(path)


def _remote_matches(root: Path, expected_slug: str) -> bool:
    try:
        remote = _run_git(root, "remote", "get-url", "origin").strip()
    except DeliveryError:
        return False
    remote = remote.removesuffix(".git").rstrip("/").lower()
    expected = expected_slug.lower()
    return remote in {
        f"https://github.com/{expected}",
        f"http://github.com/{expected}",
        f"git@github.com:{expected}",
        f"ssh://git@github.com/{expected}",
    }


def _worktree_paths(root: Path) -> list[Path]:
    output = _run_git(root, "worktree", "list", "--porcelain")
    paths: list[Path] = []
    for line in output.splitlines():
        if line.startswith("worktree "):
            paths.append(Path(line[len("worktree ") :]))
    return paths


def load_delivery_config(project_root: Path) -> dict[str, Any]:
    config_path = project_root / "config" / "artifact-delivery.json"
    if not config_path.is_file():
        raise DeliveryError("Artifact delivery configuration is missing from this source checkout.")
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DeliveryError("Artifact delivery configuration is invalid.") from exc
    if config.get("schemaVersion") != 1 or config.get("resolution") != "primary-standard-worktree-from-git-common-dir":
        raise DeliveryError("Artifact delivery configuration uses an unsupported schema or resolver.")
    if not isinstance(config.get("repository"), str) or "/" not in config["repository"]:
        raise DeliveryError("Artifact delivery repository identity is missing or invalid.")
    if config.get("artifactRoot") != "artifacts" or config.get("versionDirectoryPattern") != "v{versionName}":
        raise DeliveryError("Artifact delivery paths must use the reviewed artifacts/v{versionName} layout.")
    return config


def resolve_primary_root(project_root: Path, explicit_root: Path | None = None) -> Path:
    """Resolve the single standard checkout sharing this worktree's Git common dir."""
    source_root = _ensure_project_root(project_root)
    config = load_delivery_config(source_root)
    expected_slug = config["repository"]
    common = _common_git_dir(source_root)

    if explicit_root is not None:
        candidate = _ensure_project_root(explicit_root)
        if not (candidate / ".git").is_dir():
            raise DeliveryError("Explicit primary root is not a standard Git checkout.")
        if _common_git_dir(candidate) != common or not _remote_matches(candidate, expected_slug):
            raise DeliveryError("Explicit primary root does not match this CarPaly repository/worktree set.")
        if candidate not in {_canonical(p) for p in _worktree_paths(source_root)}:
            raise DeliveryError("Explicit primary root is not registered in this repository's worktree list.")
        return candidate

    candidates: list[Path] = []
    for worktree in _worktree_paths(source_root):
        try:
            candidate = _ensure_project_root(worktree)
            if not (candidate / ".git").is_dir():
                continue
            if _common_git_dir(candidate) != common or not _remote_matches(candidate, expected_slug):
                continue
            candidates.append(candidate)
        except DeliveryError:
            continue

    unique = sorted({_canonical(item) for item in candidates}, key=lambda item: os.path.normcase(str(item)))
    if len(unique) != 1:
        raise DeliveryError(
            "Could not identify exactly one primary standard checkout; explicitly configure a validated primary root."
        )
    return unique[0]


def _load_ledger(project_root: Path) -> tuple[dict[str, Any], dict[str, Any], str]:
    path = project_root / "config" / "android-version-ledger.json"
    try:
        ledger = json.loads(path.read_text(encoding="utf-8"))
        version_name = str(ledger["current"]["versionName"])
        version_code = int(ledger["current"]["versionCode"])
        epochs = [
            epoch
            for epoch in ledger["signingEpochs"]
            if version_code >= int(epoch["minimumVersionCode"])
            and (epoch.get("maximumVersionCode") is None or version_code <= int(epoch["maximumVersionCode"]))
        ]
        if len(epochs) != 1:
            raise ValueError("ambiguous signing epoch")
        epoch = epochs[0]
        signer = str(epoch["certificateSha256"]).replace(":", "").lower()
        if ledger["current"].get("signingEpochId") != epoch["id"]:
            raise ValueError("signing epoch ID mismatch")
        if str(ledger["applicationId"]) != str(ledger["deliveryPolicy"]["applicationId"]):
            raise ValueError("application ID mismatch")
        if str(ledger["releaseCertificateSha256"]).replace(":", "").lower() != signer:
            raise ValueError("active signer mismatch")
        if str(ledger["deliveryPolicy"]["releaseCertificateSha256"]).replace(":", "").lower() != signer:
            raise ValueError("delivery signer mismatch")
        return ledger, {"versionName": version_name, "versionCode": version_code}, signer
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise DeliveryError("The source checkout's version/signing ledger is invalid.") from exc


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _validate_proof(project_root: Path, source_dir: Path) -> tuple[Path, str, dict[str, Any]]:
    ledger, current, expected_signer = _load_ledger(project_root)
    file_name = f"CarPaly-XingyueL-v{current['versionName']}.apk"
    apk = source_dir / file_name
    verification_path = source_dir / f"{file_name}.verification.json"
    checksum_path = source_dir / f"{file_name}.sha256"
    sums_path = source_dir / "SHA256SUMS.txt"
    for path in (apk, verification_path, checksum_path, sums_path):
        ensure_no_reparse_components(path)
        if not path.is_file():
            raise DeliveryError(f"Required verified build input is missing: {path.name}")

    apk_hash = sha256_file(apk)
    try:
        proof = json.loads(verification_path.read_text(encoding="utf-8-sig"))
        code = int(current["versionCode"])
        expected_checks = proof.get("checks", {})
        valid = (
            proof.get("status") == "PASS"
            and proof.get("apk") == file_name
            and proof.get("packageName") == ledger["applicationId"]
            and proof.get("versionName") == current["versionName"]
            and int(proof.get("versionCode")) == code
            and str(proof.get("apkSha256", "")).lower() == apk_hash
            and str(proof.get("signerCertificateSha256", "")).replace(":", "").lower() == expected_signer
            and all(expected_checks.get(name) == "PASS" for name in REQUIRED_VERIFIER_CHECKS)
        )
        allocation = [
            item
            for item in ledger.get("allocations", [])
            if item.get("versionName") == current["versionName"] and int(item.get("versionCode", -1)) == code
        ]
        if len(allocation) != 1:
            valid = False
        else:
            previous_codes = [
                int(item["versionCode"])
                for item in ledger.get("allocations", [])
                if item is not allocation[0]
            ]
            previous_codes.extend(int(item["versionCode"]) for item in ledger.get("verifiedHistoricalDeliveries", []))
            if code <= max(previous_codes, default=0):
                valid = False
            if int(ledger.get("highestObservedVersionCode", -1)) != code:
                valid = False
            if allocation[0].get("status") != "delivered" or str(allocation[0].get("artifactSha256", "")).lower() != apk_hash:
                valid = False
            if str(allocation[0].get("signerCertificateSha256", "")).replace(":", "").lower() != expected_signer:
                valid = False
        if not valid:
            raise DeliveryError("The APK does not match a PASS result from the canonical Release verifier and ledger.")
        sidecar = checksum_path.read_text(encoding="ascii").strip().split()
        sums = sums_path.read_text(encoding="ascii").splitlines()
        expected_line = f"{apk_hash}  {file_name}"
        if len(sidecar) < 2 or sidecar[0].lower() != apk_hash or sidecar[1] != file_name:
            raise DeliveryError("The APK SHA-256 sidecar does not match the verified APK.")
        if expected_line not in sums:
            raise DeliveryError("SHA256SUMS.txt does not include the verified APK hash.")
    except DeliveryError:
        raise
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise DeliveryError("The verifier report or checksum metadata is invalid.") from exc
    return apk, apk_hash, {"ledger": ledger, "current": current, "signer": expected_signer, "proof": proof}


def _ignored_artifact_path(primary_root: Path, relative: str) -> bool:
    result = subprocess.run(
        ["git", "-C", str(primary_root), "check-ignore", "--no-index", "--quiet", "--", relative],
        check=False,
        capture_output=True,
    )
    if result.returncode == 0:
        return True
    if result.returncode == 1:
        return False
    raise DeliveryError("Git could not verify artifact ignore protection.")


def _tracked_artifact_path(primary_root: Path, relative: str) -> bool:
    result = subprocess.run(
        ["git", "-C", str(primary_root), "ls-files", "--error-unmatch", "--", relative],
        check=False,
        capture_output=True,
    )
    if result.returncode == 0:
        return True
    if result.returncode == 1:
        return False
    raise DeliveryError("Git could not verify that the delivery APK is untracked.")


def _validate_report_paths(project_root: Path, report_paths: Iterable[Path]) -> list[Path]:
    allowlist_path = project_root / "config" / "public-markdown-allowlist.json"
    try:
        allowed = set(json.loads(allowlist_path.read_text(encoding="utf-8"))["publicMarkdown"])
    except (OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise DeliveryError("The public Markdown report allowlist is unavailable or invalid.") from exc
    reports: list[Path] = []
    seen: set[str] = set()
    for raw_path in report_paths:
        path = _canonical(raw_path)
        ensure_no_reparse_components(path)
        if not path.is_file() or path.suffix.lower() != ".md":
            raise DeliveryError("Only existing Markdown reports may be copied to the local delivery archive.")
        try:
            relative = path.relative_to(_canonical(project_root)).as_posix()
        except ValueError as exc:
            raise DeliveryError("A report is outside the source checkout and cannot be delivered.") from exc
        if relative.casefold() not in {entry.casefold() for entry in allowed} or path.name.casefold() == "delivery_report.md":
            raise DeliveryError("A report is not present in the reviewed public Markdown allowlist.")
        if path.name.casefold() in seen:
            raise DeliveryError("Report filenames must be unique in the delivery folder.")
        seen.add(path.name.casefold())
        reports.append(path)
    return reports


def _ensure_directory(path: Path) -> None:
    ensure_no_reparse_components(path)
    if path.exists():
        if not path.is_dir():
            raise DeliveryError(f"Expected a directory but found another file type: {path}")
        return
    path.mkdir()
    if is_reparse_path(path):
        raise DeliveryError(f"Refusing a reparse-point delivery directory: {path}")


def _same_existing_file(path: Path, expected_hash: str) -> bool:
    ensure_no_reparse_components(path)
    if not path.exists():
        return False
    if not path.is_file():
        raise DeliveryError(f"A destination path exists but is not a regular file: {path}")
    actual = sha256_file(path)
    if actual != expected_hash:
        raise DeliveryError(f"A different file already exists; refusing to overwrite: {path}")
    return True


def _copy_exclusive(source: Path, destination: Path) -> None:
    ensure_no_reparse_components(destination.parent)
    try:
        with source.open("rb") as input_stream, destination.open("xb") as output_stream:
            shutil.copyfileobj(input_stream, output_stream, length=1024 * 1024)
            output_stream.flush()
            os.fsync(output_stream.fileno())
    except FileExistsError as exc:
        raise DeliveryError(f"Destination appeared during copy; refusing overwrite: {destination}") from exc
    except OSError as exc:
        try:
            if destination.is_file() and not is_reparse_path(destination):
                destination.unlink()
        except OSError:
            pass
        raise DeliveryError(f"Could not copy verified artifact to the local delivery directory: {destination.name}") from exc


def deliver(
    project_root: Path,
    source_dir: Path,
    primary_root: Path | None = None,
    report_paths: Iterable[Path] = (),
) -> dict[str, str]:
    project_root = _ensure_project_root(project_root)
    source_dir = _canonical(source_dir)
    ensure_no_reparse_components(source_dir)
    if not source_dir.is_dir():
        raise DeliveryError("The verified candidate artifact directory does not exist.")
    config = load_delivery_config(project_root)
    primary = resolve_primary_root(project_root, primary_root)
    apk, apk_hash, metadata = _validate_proof(project_root, source_dir)
    reports = _validate_report_paths(project_root, report_paths)
    if not config.get("copyReportsListedInPublicAllowlist", False) and reports:
        raise DeliveryError("Report copying is disabled by the artifact delivery policy.")
    version = metadata["current"]["versionName"]
    file_name = apk.name
    relative_root = Path(config["artifactRoot"]) / config["versionDirectoryPattern"].format(versionName=version)
    target_dir = primary / relative_root
    report_dir = target_dir / "reports"

    # Guard every existing component before creating or writing anything.
    ensure_no_reparse_components(target_dir)
    artifacts_root = primary / config["artifactRoot"]
    ensure_no_reparse_components(artifacts_root)
    if config.get("requireIgnored"):
        probe_rel = f"{relative_root.as_posix()}/{file_name}"
        if _tracked_artifact_path(primary, probe_rel):
            raise DeliveryError("The destination APK is tracked by Git; refusing local delivery.")
        if not _ignored_artifact_path(primary, probe_rel):
            raise DeliveryError("The primary artifacts directory is not ignored by Git; refusing delivery.")

    source_items: list[tuple[Path, Path]] = []
    for name in (file_name, f"{file_name}.sha256", f"{file_name}.verification.json", "SHA256SUMS.txt"):
        source_items.append((source_dir / name, target_dir / name))
    for report in reports:
        source_items.append((report, report_dir / report.name))

    delivery_report = (
        "# Local APK Delivery Report\n\n"
        f"- Version: {version} (versionCode {metadata['current']['versionCode']})\n"
        f"- Package: {metadata['ledger']['applicationId']}\n"
        f"- APK: `{file_name}`\n"
        f"- APK SHA-256: `{apk_hash}`\n"
        f"- Release signer SHA-256: `{metadata['signer']}`\n"
        f"- Central delivery: `{target_dir / file_name}`\n"
        "- Source preservation: the verified staging copy remains in its originating worktree.\n"
        "- Verification: canonical Release APK verification report matched the ledger and checksum sidecars.\n"
        "- Distribution: local-only copy; no GitHub upload, Release, or OTA action was performed.\n"
    )
    generated_report = report_dir / config["generatedReportName"]
    if generated_report.name != "DELIVERY_REPORT.md":
        raise DeliveryError("The generated delivery report name is not the reviewed local-only name.")

    # Preflight all conflicts before the first copy. Existing identical files are immutable and retained.
    for source, destination in source_items:
        ensure_no_reparse_components(source)
        if not source.is_file():
            raise DeliveryError(f"A delivery input is missing: {source.name}")
        _same_existing_file(destination, sha256_file(source))
    report_hash = hashlib.sha256(delivery_report.encode("utf-8")).hexdigest()
    _same_existing_file(generated_report, report_hash)

    _ensure_directory(artifacts_root)
    _ensure_directory(target_dir)
    _ensure_directory(report_dir)
    probe = target_dir / f".delivery-write-probe-{uuid.uuid4().hex}"
    try:
        with probe.open("x", encoding="ascii") as stream:
            stream.write("write-check")
        probe.unlink()
    except OSError as exc:
        try:
            if probe.is_file() and not is_reparse_path(probe):
                probe.unlink()
        except OSError:
            pass
        raise DeliveryError("The primary artifacts directory is not writable.") from exc
    lock = target_dir / ".artifact-delivery.lock"
    try:
        with lock.open("x", encoding="ascii") as stream:
            stream.write(str(os.getpid()))
    except FileExistsError as exc:
        raise DeliveryError("Another artifact delivery is in progress; no files were changed.") from exc

    created: list[Path] = []
    try:
        for source, destination in source_items:
            if _same_existing_file(destination, sha256_file(source)):
                continue
            _copy_exclusive(source, destination)
            created.append(destination)
        if not _same_existing_file(generated_report, report_hash):
            try:
                with generated_report.open("x", encoding="utf-8", newline="\n") as stream:
                    stream.write(delivery_report)
                    stream.flush()
                    os.fsync(stream.fileno())
            except OSError as exc:
                raise DeliveryError("Could not write the local delivery report.") from exc
            created.append(generated_report)

        # Verify every copied asset byte-for-byte by SHA-256 without altering the source.
        for source, destination in source_items:
            if sha256_file(source) != sha256_file(destination):
                raise DeliveryError(f"Post-copy SHA-256 verification failed: {destination.name}")
        return {
            "primaryRoot": str(primary),
            "deliveryApk": str(target_dir / file_name),
            "apkSha256": apk_hash,
            "versionName": str(version),
            "versionCode": str(metadata["current"]["versionCode"]),
            "reportDirectory": str(report_dir),
            "reportsCopied": str(len(reports)),
        }
    except Exception:
        # Roll back only files created by this invocation; never remove pre-existing files.
        for path in reversed(created):
            try:
                if path.is_file() and not is_reparse_path(path):
                    path.unlink()
            except OSError:
                pass
        raise
    finally:
        try:
            lock.unlink()
        except OSError:
            pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--primary-root", type=Path, default=None)
    parser.add_argument("--report", type=Path, action="append", default=[])
    args = parser.parse_args(argv)
    try:
        result = deliver(args.project_root, args.source_dir, args.primary_root, args.report)
    except DeliveryError as exc:
        print(f"ARTIFACT_DELIVERY=BLOCKED reason={exc}", file=sys.stderr)
        return 2
    for key, value in result.items():
        print(f"{key.upper()}={value}")
    print("ARTIFACT_DELIVERY=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
