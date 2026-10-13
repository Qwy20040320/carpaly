#!/usr/bin/env python3
"""Sign Stable/Beta OTA feeds from published, APK-verified CarPaly Releases."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

if __package__:
    from . import ota_manifest, sync_release_docs as release_docs
    from .sync_release_docs import fetch_verifications, release_tag_commits
else:
    import ota_manifest
    import sync_release_docs as release_docs
    from sync_release_docs import fetch_verifications, release_tag_commits


REPOSITORY = "Qwy20040320/carpaly"
API_URL = f"https://api.github.com/repos/{REPOSITORY}/releases?per_page=100"
CANONICAL_APK = re.compile(r"^CarPaly-XingyueL-v(\d+\.\d+\.\d+)\.apk$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
MAX_CHECKSUM_BYTES = 256
ALLOWED_DOWNLOAD_HOSTS = {"github.com", "release-assets.githubusercontent.com", "objects.githubusercontent.com"}


def fetch_releases() -> list[dict[str, Any]]:
    request = urllib.request.Request(
        API_URL,
        headers={"Accept": "application/vnd.github+json", "User-Agent": "CarPaly-OTA-manifest-builder"},
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            raw = response.read(4 * 1024 * 1024 + 1)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as exc:
        raise ota_manifest.ManifestError("Could not read public GitHub Release metadata") from exc
    if len(raw) > 4 * 1024 * 1024:
        raise ota_manifest.ManifestError("Public GitHub Release metadata exceeds the size limit")
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ota_manifest.ManifestError("GitHub Release API returned malformed JSON") from exc
    if not isinstance(value, list):
        raise ota_manifest.ManifestError("GitHub Release API response was not an array")
    return [item for item in value if isinstance(item, dict)]


def fetch_tags() -> list[dict[str, Any]]:
    request = urllib.request.Request(
        f"https://api.github.com/repos/{REPOSITORY}/tags?per_page=100",
        headers={"Accept": "application/vnd.github+json", "User-Agent": "CarPaly-OTA-manifest-builder"},
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            raw = response.read(4 * 1024 * 1024 + 1)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as exc:
        raise ota_manifest.ManifestError("Could not read public Git tag metadata") from exc
    if len(raw) > 4 * 1024 * 1024:
        raise ota_manifest.ManifestError("Public Git tag metadata exceeds the size limit")
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ota_manifest.ManifestError("Git tag API returned malformed JSON") from exc
    if not isinstance(value, list):
        raise ota_manifest.ManifestError("Git tag API response was not an array")
    return [item for item in value if isinstance(item, dict)]


def fetch_main_commit() -> str:
    request = urllib.request.Request(
        f"https://api.github.com/repos/{REPOSITORY}/branches/main",
        headers={"Accept": "application/vnd.github+json", "User-Agent": "CarPaly-OTA-manifest-builder"},
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            raw = response.read(512 * 1024 + 1)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as exc:
        raise ota_manifest.ManifestError("Could not read public main-branch metadata") from exc
    if len(raw) > 512 * 1024:
        raise ota_manifest.ManifestError("Public main-branch metadata exceeds the size limit")
    try:
        value = json.loads(raw.decode("utf-8"))
        return str(value["commit"]["sha"])
    except (UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError) as exc:
        raise ota_manifest.ManifestError("Main-branch API response was malformed") from exc


def tags_merged_to_main(releases: list[dict[str, Any]], tags: list[dict[str, Any]],
                        main_sha: str) -> set[str]:
    tag_shas = release_tag_commits(tags)
    eligible: set[str] = set()
    names = {str(item.get("tag_name", "")) for item in releases}
    for name in names:
        base = tag_shas.get(name)
        if not base:
            continue
        compare_url = (
            f"https://api.github.com/repos/{REPOSITORY}/compare/"
            f"{urllib.parse.quote(base, safe='')}...{urllib.parse.quote(main_sha, safe='')}"
        )
        request = urllib.request.Request(
            compare_url,
            headers={"Accept": "application/vnd.github+json", "User-Agent": "CarPaly-OTA-manifest-builder"},
        )
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                raw = response.read(2 * 1024 * 1024 + 1)
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as exc:
            raise ota_manifest.ManifestError(f"Could not verify whether Release tag {name} is on main") from exc
        if len(raw) > 2 * 1024 * 1024:
            raise ota_manifest.ManifestError("GitHub compare response exceeds the size limit")
        try:
            value = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ota_manifest.ManifestError("GitHub compare API returned malformed JSON") from exc
        if isinstance(value, dict) and value.get("status") in {"ahead", "identical"}:
            eligible.add(name)
    return eligible


def verified_checksum_tags(releases: list[dict[str, Any]],
                           verifications: dict[str, Any]) -> set[str]:
    """Allow an OTA candidate only after reading its public sidecar and matching verified APK proof."""
    verified: set[str] = set()
    for release in release_docs.public_releases(releases):
        tag = str(release.get("tag_name", ""))
        proof = verifications.get(tag)
        if not isinstance(proof, dict) or proof.get("status") != "PASS":
            continue
        apk_name = str(proof.get("apk", ""))
        match = CANONICAL_APK.fullmatch(apk_name)
        digest = str(proof.get("apkSha256", "")).lower()
        if not match or tag != f"v{match.group(1)}" or not SHA256.fullmatch(digest):
            continue
        sidecar_name = apk_name + ".sha256"
        assets = release.get("assets", [])
        matches = [asset for asset in assets if isinstance(asset, dict) and asset.get("name") == sidecar_name]
        if len(matches) != 1:
            continue
        asset = matches[0]
        size = asset.get("size")
        url = release_docs.safe_asset_url(REPOSITORY, tag, asset)
        if not isinstance(size, int) or size not in range(1, MAX_CHECKSUM_BYTES + 1) or not url:
            continue
        request = urllib.request.Request(
            url, headers={"Accept": "application/octet-stream", "User-Agent": "CarPaly-OTA-manifest-builder"},
        )
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                final_url = urllib.parse.urlsplit(response.geturl())
                body = response.read(MAX_CHECKSUM_BYTES + 1)
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as exc:
            raise ota_manifest.ManifestError("Could not read a public Release checksum sidecar") from exc
        if final_url.scheme != "https" or final_url.hostname not in ALLOWED_DOWNLOAD_HOSTS \
                or final_url.username or final_url.password:
            raise ota_manifest.ManifestError("Release checksum request redirected to an untrusted host")
        if ota_manifest.checksum_sidecar_matches(
                body, apk_name=apk_name, expected_sha256=digest, expected_size=size):
            verified.add(tag)
    return verified


def read_release_snapshot(path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Read the single validated public Release snapshot generated by build_site.py."""
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ota_manifest.ManifestError("Could not read the shared Release snapshot") from exc
    if not isinstance(value, dict) or value.get("schemaVersion") != 1 \
            or value.get("repository") != REPOSITORY:
        raise ota_manifest.ManifestError("Shared Release snapshot has an unsupported schema or repository")
    releases = value.get("releases")
    verifications = value.get("verifications")
    if not isinstance(releases, list) or not all(isinstance(item, dict) for item in releases) \
            or not isinstance(verifications, dict):
        raise ota_manifest.ManifestError("Shared Release snapshot is malformed")
    return releases, verifications


def validate_required_release_tag(
    tag: str, *, releases: list[dict[str, Any]], tags: list[dict[str, Any]],
    ledger: dict[str, Any], verifications: dict[str, Any], policy: dict[str, Any],
    main_verified_tags: set[str], verified_checksum_tags: set[str],
) -> None:
    """Require a requested, actually published Release with verified APK proof on current main."""
    if not re.fullmatch(r"v\d+\.\d+\.\d+", tag):
        raise ota_manifest.ManifestError("OTA publication requires a semantic version Release tag")
    public_matches = [release for release in release_docs.public_releases(releases)
                     if release.get("tag_name") == tag]
    if len(public_matches) != 1:
        raise ota_manifest.ManifestError("Requested OTA version is not one unique published GitHub Release")
    proof = verifications.get(tag)
    if not isinstance(proof, dict) or proof.get("status") != "PASS":
        raise ota_manifest.ManifestError("Requested OTA Release lacks matching verified APK and checksum evidence")
    if tag not in main_verified_tags:
        raise ota_manifest.ManifestError("Requested OTA Release tag is not contained in current main")
    if tag not in verified_checksum_tags:
        raise ota_manifest.ManifestError("Requested OTA Release lacks matching verified APK and checksum evidence")
    records = ota_manifest.verified_channel_records(
        releases=releases,
        tags=tags,
        repository=REPOSITORY,
        ledger=ledger,
        verifications=verifications,
        policy=policy,
        main_verified_tags=main_verified_tags,
        verified_checksum_tags=verified_checksum_tags,
    )
    if not any(isinstance(record, dict) and record.get("releaseTag") == tag for record in records.values()):
        raise ota_manifest.ManifestError(
            "Requested OTA Release does not match the immutable version ledger, package, signer, and feed policy"
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("site/updates"))
    parser.add_argument("--release-snapshot", type=Path,
                        help="use the exact public Release evidence snapshot created by build_site.py")
    parser.add_argument("--required-release-tag",
                        help="require this exact published, APK-verified Release to be merged into current main")
    parser.add_argument("--private-key-env", default="OTA_MANIFEST_SIGNING_PRIVATE_KEY_PEM")
    parser.add_argument("--key-id-env", default="OTA_MANIFEST_SIGNING_KEY_ID")
    args = parser.parse_args(argv)

    private_key = os.environ.get(args.private_key_env, "")
    key_id = os.environ.get(args.key_id_env, "")
    try:
        if not private_key or not key_id:
            raise ota_manifest.ManifestError("OTA manifest signing key and key id are not configured")
        policy = ota_manifest.load_json(ota_manifest.POLICY_PATH)
        ledger = ota_manifest.load_json(ota_manifest.LEDGER_PATH)
        trust = ota_manifest.load_json(ota_manifest.TRUST_PATH)
        if args.release_snapshot:
            releases, verifications = read_release_snapshot(args.release_snapshot)
        else:
            releases = fetch_releases()
            verifications = fetch_verifications(releases, REPOSITORY)
        tags = fetch_tags()
        for release in release_docs.public_releases(releases):
            tag = str(release.get("tag_name", ""))
            assets = release.get("assets", [])
            has_proof_asset = isinstance(assets, list) and any(
                isinstance(asset, dict) and str(asset.get("name", "")).endswith(".apk.verification.json")
                for asset in assets
            )
            if has_proof_asset and verifications.get(tag) is None:
                raise ota_manifest.ManifestError(
                    f"Release verification evidence could not be read for {tag}; preserving the previous OTA feed"
                )
        checksum_tags = verified_checksum_tags(releases, verifications)
        merged_tags = tags_merged_to_main(releases, tags, fetch_main_commit())
        if args.required_release_tag:
            validate_required_release_tag(
                args.required_release_tag, releases=releases, tags=tags, ledger=ledger,
                verifications=verifications, policy=policy, main_verified_tags=merged_tags,
                verified_checksum_tags=checksum_tags,
            )
        envelopes = ota_manifest.prepare_signed_channels(
            releases=releases,
            tags=tags,
            repository=REPOSITORY,
            ledger=ledger,
            verifications=verifications,
            policy=policy,
            trust=trust,
            private_key_pem=private_key,
            key_id=key_id,
            main_verified_tags=merged_tags,
            verified_checksum_tags=checksum_tags,
        )
        paths = ota_manifest.write_channels(args.output, envelopes)
        for path in paths:
            try:
                envelope = json.loads(path.read_text(encoding="utf-8"))
                payload = ota_manifest.verify_envelope(envelope, trust)
            except (OSError, json.JSONDecodeError, ota_manifest.ManifestError) as exc:
                raise ota_manifest.ManifestError("Written OTA manifest did not pass its app trust-store check") from exc
            if payload.get("channel") != path.stem:
                raise ota_manifest.ManifestError("Written OTA manifest channel does not match its output name")
    except ota_manifest.ManifestError as exc:
        print(f"OTA_MANIFEST_STATUS=BLOCKED: {exc}", file=sys.stderr)
        return 2
    finally:
        private_key = ""

    for channel in ("stable", "beta"):
        print(f"OTA_{channel.upper()}_STATUS={'WRITTEN' if any(p.name == channel + '.json' for p in paths) else 'NO_OUTPUT'}")
    print(f"OTA_MANIFEST_FILES={len(paths)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
