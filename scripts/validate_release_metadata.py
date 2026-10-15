#!/usr/bin/env python3
"""Validate the public release-documentation metadata against the version ledger."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
LEDGER_PATH = ROOT / "config/android-version-ledger.json"
METADATA_PATH = ROOT / "config/release-documentation.json"
ALLOWLIST_PATH = ROOT / "config/public-markdown-allowlist.json"
README_PATH = ROOT / "README.md"
CHANGELOG_PATH = ROOT / "CHANGELOG.md"
SHA256 = re.compile(r"^[0-9a-f]{64}$")
VEHICLE_STATES = {
    "PASS",
    "FAIL",
    "BLOCKED",
    "NOT_TESTED",
    "USER_REPORTED_PASS",
    "USER_REPORTED_FAIL",
    "USER_REPORTED_ISSUE",
}


class MetadataError(ValueError):
    pass


def _read_json(path: Path) -> dict[str, Any]:
    try:
        display_path = path.relative_to(ROOT).as_posix()
    except ValueError:
        display_path = path.name
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise MetadataError(f"Cannot read valid JSON from {display_path}: {error}") from error
    if not isinstance(value, dict):
        raise MetadataError(f"Expected an object in {display_path}")
    return value


def validate_metadata(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    try:
        ledger = _read_json(root / LEDGER_PATH.relative_to(ROOT))
        metadata = _read_json(root / METADATA_PATH.relative_to(ROOT))
        allowlist = _read_json(root / ALLOWLIST_PATH.relative_to(ROOT))
    except MetadataError as error:
        return [str(error)]

    if metadata.get("schemaVersion") != 1:
        errors.append("release-documentation schemaVersion must be 1")
    repository = metadata.get("repository", {})
    description = repository.get("description", "")
    maximum = repository.get("descriptionMaxLength", 0)
    if not isinstance(description, str) or not description.strip():
        errors.append("repository.description must be a non-empty string")
    elif len(description) > maximum or maximum > 350 or maximum < 1:
        errors.append("repository.description exceeds the configured GitHub limit")
    if not isinstance(repository.get("topics"), list) or not repository.get("topics"):
        errors.append("repository.topics must preserve a non-empty topic list")
    if not isinstance(repository.get("homepage"), str) or not repository["homepage"].startswith("https://"):
        errors.append("repository.homepage must be an HTTPS URL")

    candidate = metadata.get("candidate", {})
    current = ledger.get("current", {})
    if candidate.get("status") != "ledger_allocation":
        errors.append("candidate.status must identify the ledger allocation; public Release state comes from GitHub")
    if candidate.get("versionName") != current.get("versionName"):
        errors.append("candidate.versionName must match the current version ledger entry")
    allocation = next(
        (
            item
            for item in ledger.get("allocations", [])
            if item.get("versionName") == candidate.get("versionName")
            and item.get("versionCode") == current.get("versionCode")
        ),
        None,
    )
    if allocation is None:
        errors.append("candidate version must have an immutable versionCode allocation")
    elif allocation.get("status") != "delivered" or not SHA256.fullmatch(
        str(allocation.get("artifactSha256", "")).lower()
    ):
        errors.append("ledger allocation must have delivered status and an artifact SHA-256")
    if current.get("channel") != "test":
        errors.append("this metadata candidate must not be marked as a stable release")
    if candidate.get("vehicleStatus") != "NOT_TESTED":
        errors.append("candidate vehicleStatus must remain NOT_TESTED until vehicle retest evidence is recorded")
    if candidate.get("releaseClaims") != []:
        errors.append("candidate releaseClaims must be empty unless verified release evidence is added")

    feedback = metadata.get("vehicleFeedback", [])
    ids = [item.get("id") for item in feedback]
    if len(ids) != len(set(ids)):
        errors.append("vehicleFeedback ids must be unique")
    for item in feedback:
        if item.get("status") not in VEHICLE_STATES:
            errors.append(f"vehicleFeedback {item.get('id')} uses an unknown status")
        if not item.get("labelZh") or not item.get("labelEn"):
            errors.append(f"vehicleFeedback {item.get('id')} needs Chinese and English labels")
        if not item.get("detailZh") or not item.get("detailEn"):
            errors.append(f"vehicleFeedback {item.get('id')} needs evidence-qualified descriptions")

    public_markdown = set(allowlist.get("publicMarkdown", []))
    if "docs/RELEASE_AUTOMATION.md" not in public_markdown:
        errors.append("docs/RELEASE_AUTOMATION.md must be explicitly allow-listed")
    readme_markers = {
        key: marker
        for key, marker in metadata.get("managedMarkers", {}).items()
        if key.startswith("readme")
    }
    for path, markers in (
        (root / "README.md", readme_markers),
        (root / "CHANGELOG.md", {"changelog": metadata.get("managedMarkers", {}).get("changelog")}),
    ):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            errors.append(f"Missing {path.relative_to(root).as_posix()}")
            continue
        for marker in markers.values():
            if not marker:
                continue
            start = f"<!-- {marker}:START -->"
            end = f"<!-- {marker}:END -->"
            if text.count(start) != 1 or text.count(end) != 1 or text.index(start) >= text.index(end):
                errors.append(
                    f"{path.relative_to(root).as_posix()} needs exactly one ordered marker pair for {marker}"
                )

    return errors


def main() -> int:
    errors = validate_metadata()
    if errors:
        print("RELEASE_METADATA_STATUS=FAIL")
        for error in errors:
            print(f"- {error}")
        return 1
    current = _read_json(LEDGER_PATH)["current"]
    print(
        "RELEASE_METADATA_STATUS=PASS "
        f"candidate={current['versionName']} code={current['versionCode']} vehicle=NOT_TESTED"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
