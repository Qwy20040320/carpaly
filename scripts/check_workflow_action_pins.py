#!/usr/bin/env python3
"""Require trusted, immutable Action references in the Android release workflow."""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/android.yml"
TRUSTED_ACTIONS = {
    "actions/checkout",
    "actions/setup-go",
    "actions/setup-java",
    "android-actions/setup-android",
    "gradle/actions/setup-gradle",
    "actions/upload-artifact",
}
FULL_COMMIT_SHA = re.compile(r"^[0-9a-f]{40}$")
USES = re.compile(r"^\s*(?:-\s*)?uses:\s*([^\s#]+)", re.MULTILINE)


def main() -> None:
    contents = WORKFLOW.read_text(encoding="utf-8")
    references = USES.findall(contents)
    if not references:
        raise SystemExit(f"No Actions found in {WORKFLOW.relative_to(ROOT)}")

    failures: list[str] = []
    seen: set[str] = set()
    for reference in references:
        if reference.startswith("./"):
            continue
        if "@" not in reference:
            failures.append(f"Action is not pinned: {reference}")
            continue
        repository, revision = reference.rsplit("@", 1)
        seen.add(repository)
        if repository not in TRUSTED_ACTIONS:
            failures.append(f"Action is outside the reviewed allowlist: {repository}")
        if not FULL_COMMIT_SHA.fullmatch(revision):
            failures.append(f"Action must use a full 40-character commit SHA: {reference}")

    unused = TRUSTED_ACTIONS - seen
    if unused:
        failures.append(f"Reviewed Action inventory does not match workflow: {', '.join(sorted(unused))}")
    if failures:
        raise SystemExit("Android workflow Action pin check failed:\n" + "\n".join(failures))
    print(f"Android workflow Action pins passed: {len(references)} immutable references.")


if __name__ == "__main__":
    main()
