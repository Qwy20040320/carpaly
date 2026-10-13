#!/usr/bin/env python3
"""Preflight a real public Release for a later, separately protected OTA signing run."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__:
    from . import build_ota_manifests as builder, ota_manifest, sync_release_docs as release_docs
else:
    import build_ota_manifests as builder
    import ota_manifest
    import sync_release_docs as release_docs


def validate(snapshot: Path, release_tag: str) -> None:
    policy = ota_manifest.load_json(ota_manifest.POLICY_PATH)
    ledger = ota_manifest.load_json(ota_manifest.LEDGER_PATH)
    releases, verifications = builder.read_release_snapshot(snapshot)
    for release in release_docs.public_releases(releases):
        tag = str(release.get("tag_name", ""))
        assets = release.get("assets", [])
        has_proof = isinstance(assets, list) and any(
            isinstance(asset, dict) and str(asset.get("name", "")).endswith(".apk.verification.json")
            for asset in assets
        )
        if has_proof and verifications.get(tag) is None:
            raise ota_manifest.ManifestError(f"Release verification evidence could not be read for {tag}")
    tags = builder.fetch_tags()
    main_sha = builder.fetch_main_commit()
    merged = builder.tags_merged_to_main(releases, tags, main_sha)
    checksums = builder.verified_checksum_tags(releases, verifications)
    builder.validate_required_release_tag(
        release_tag, releases=releases, tags=tags, ledger=ledger,
        verifications=verifications, policy=policy, main_verified_tags=merged,
        verified_checksum_tags=checksums,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release-snapshot", required=True, type=Path)
    parser.add_argument("--release-tag", required=True)
    args = parser.parse_args(argv)
    try:
        validate(args.release_snapshot, args.release_tag)
    except (OSError, ota_manifest.ManifestError) as exc:
        print(f"OTA_RELEASE_PREFLIGHT=BLOCKED: {exc}", file=sys.stderr)
        return 2
    print(f"OTA_RELEASE_PREFLIGHT=PASS tag={args.release_tag} private_key=NOT_READ")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
