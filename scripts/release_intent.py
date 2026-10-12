#!/usr/bin/env python3
"""Fail-closed gate for an explicitly reviewed release intent on a main commit."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


ROOT = Path(__file__).resolve().parents[1]
INTENT_PATH = "config/release-intent.json"
VERSION = re.compile(r"^\d+\.\d+\.\d+$")
SHA = re.compile(r"^[0-9a-f]{40}$")
GRADLE_VERSION_NAME = re.compile(r'^\s*versionName\s*=\s*"([^\"]+)"\s*$', re.MULTILINE)
GRADLE_VERSION_CODE = re.compile(r"^\s*versionCode\s*=\s*(\d+)\s*$", re.MULTILINE)


class ReleaseIntentError(ValueError):
    """A malformed or conflicting release intent must stop publication."""


@dataclass(frozen=True)
class Decision:
    publish: bool
    reason: str
    release_tag: str = ""
    version_name: str = ""
    version_code: int = 0
    prerelease: bool = True


def _git(root: Path, *args: str) -> str:
    try:
        result = subprocess.run(
            ["git", *args], cwd=root, check=True, capture_output=True, text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ReleaseIntentError("Could not inspect the release commit safely") from exc
    return result.stdout.strip()


def _intent_changed_in_commit(root: Path, commit: str) -> bool:
    if not SHA.fullmatch(commit):
        raise ReleaseIntentError("Release intent requires a full lowercase commit SHA")
    parents = _git(root, "rev-list", "--parents", "-n", "1", commit).split()
    if len(parents) < 2:
        return False
    changed = _git(root, "diff", "--name-only", f"{commit}^1", commit, "--", INTENT_PATH)
    return changed == INTENT_PATH


def _read_json(root: Path, relative: str) -> dict:
    try:
        value = json.loads((root / relative).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReleaseIntentError(f"Could not read valid JSON: {relative}") from exc
    if not isinstance(value, dict):
        raise ReleaseIntentError(f"Expected a JSON object: {relative}")
    return value


def evaluate(
    root: Path,
    *,
    commit: str,
    event: str,
    branch: str,
    conclusion: str,
    main_sha: str,
) -> Decision:
    """Return publish only for a successful, current main push changing an armed intent."""
    if event != "push" or branch != "main":
        return Decision(False, "not-a-main-push")
    if conclusion != "success":
        return Decision(False, "main-ci-not-successful")
    if not SHA.fullmatch(commit) or not SHA.fullmatch(main_sha):
        raise ReleaseIntentError("Release gate requires full lowercase commit SHAs")
    if commit != main_sha:
        return Decision(False, "main-advanced-since-ci")
    if not _intent_changed_in_commit(root, commit):
        return Decision(False, "release-intent-not-changed-by-this-commit")

    intent = _read_json(root, INTENT_PATH)
    if intent.get("schemaVersion") != 1:
        raise ReleaseIntentError("Unsupported release-intent schema")
    enabled = intent.get("enabled")
    if not isinstance(enabled, bool):
        raise ReleaseIntentError("release-intent enabled must be a boolean")
    if not enabled:
        return Decision(False, "release-intent-disabled")

    version_name = intent.get("versionName")
    version_code = intent.get("versionCode")
    channel = intent.get("channel")
    if not isinstance(version_name, str) or not VERSION.fullmatch(version_name):
        raise ReleaseIntentError("Enabled release intent must contain a semantic versionName")
    if isinstance(version_code, bool) or not isinstance(version_code, int) or version_code < 1:
        raise ReleaseIntentError("Enabled release intent must contain a positive integer versionCode")
    if channel not in {"stable", "beta"}:
        raise ReleaseIntentError("Enabled release intent channel must be stable or beta")

    ledger = _read_json(root, "config/android-version-ledger.json")
    current = ledger.get("current")
    if not isinstance(current, dict) or (current.get("versionName"), current.get("versionCode")) != (
        version_name, version_code,
    ):
        raise ReleaseIntentError("Release intent does not match the current version-ledger allocation")
    expected_track = "release" if channel == "stable" else "test"
    if current.get("channel") != expected_track:
        raise ReleaseIntentError("Release intent channel conflicts with the version-ledger track")

    gradle = (root / "mobile/build.gradle.kts").read_text(encoding="utf-8")
    version_names = GRADLE_VERSION_NAME.findall(gradle)
    version_codes = GRADLE_VERSION_CODE.findall(gradle)
    if version_names != [version_name] or version_codes != [str(version_code)]:
        raise ReleaseIntentError("Release intent does not match the Android Gradle version")

    tag = f"v{version_name}"
    existing_tag = _git(root, "tag", "--list", tag)
    if existing_tag:
        target = _git(root, "rev-parse", f"refs/tags/{tag}^{{commit}}")
        if target != commit:
            raise ReleaseIntentError("Release tag already exists at a different commit")

    prerelease = channel == "beta"
    return Decision(
        True,
        "explicit-release-intent-ready",
        release_tag=tag,
        version_name=version_name,
        version_code=version_code,
        prerelease=prerelease,
    )


def write_github_output(path: Path, decision: Decision) -> None:
    values = {
        "should_publish": str(decision.publish).lower(),
        "reason": decision.reason,
        "release_tag": decision.release_tag,
        "version_name": decision.version_name,
        "version_code": str(decision.version_code) if decision.publish else "",
        "prerelease": str(decision.prerelease).lower(),
    }
    with path.open("a", encoding="utf-8", newline="\n") as output:
        for key, value in values.items():
            if "\n" in value or "\r" in value:
                raise ReleaseIntentError("Release intent output contains an invalid line break")
            output.write(f"{key}={value}\n")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--event", required=True)
    parser.add_argument("--branch", required=True)
    parser.add_argument("--conclusion", required=True)
    parser.add_argument("--main-sha", required=True)
    parser.add_argument("--github-output", type=Path)
    args = parser.parse_args(argv)
    try:
        decision = evaluate(
            ROOT,
            commit=args.commit,
            event=args.event,
            branch=args.branch,
            conclusion=args.conclusion,
            main_sha=args.main_sha,
        )
        if args.github_output:
            write_github_output(args.github_output, decision)
    except (OSError, ReleaseIntentError) as exc:
        print(f"RELEASE_INTENT_STATUS=FAIL: {exc}", file=sys.stderr)
        return 1
    if decision.publish:
        print(
            f"RELEASE_INTENT_STATUS=READY tag={decision.release_tag} "
            f"versionCode={decision.version_code} channel={'beta' if decision.prerelease else 'stable'}"
        )
    else:
        print(f"RELEASE_INTENT_STATUS=SKIP reason={decision.reason}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
