#!/usr/bin/env python3
"""Dispatch post-release workflows and wait for their correlated GitHub runs."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import Callable, Sequence


WORKFLOWS = {
    "pages.yml": "CarPaly Pages deploy",
    "release-docs-sync.yml": "CarPaly release docs sync",
}
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
DISPATCH_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,100}$")


class FollowupError(RuntimeError):
    """A downstream workflow failed, was ambiguous, or did not finish in time."""


@dataclass(frozen=True)
class WorkflowResult:
    workflow: str
    status: str
    conclusion: str
    url: str


def _gh(
    args: Sequence[str],
    *,
    input_text: str | None,
    runner: Callable[..., subprocess.CompletedProcess[str]],
) -> str:
    completed = runner(
        ["gh", "api", *args],
        input=input_text,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    if completed.returncode != 0:
        # Avoid echoing arbitrary CLI diagnostics that could include request data.
        raise FollowupError(f"GitHub API request failed (gh exit {completed.returncode}).")
    return completed.stdout


def dispatch_workflow(
    repository: str,
    workflow: str,
    dispatch_id: str,
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> None:
    payload = json.dumps(
        {"ref": "main", "inputs": {"dispatch_id": dispatch_id}},
        separators=(",", ":"),
    )
    _gh(
        [
            "--method",
            "POST",
            f"repos/{repository}/actions/workflows/{workflow}/dispatches",
            "--input",
            "-",
        ],
        input_text=payload,
        runner=runner,
    )


def matching_runs(
    repository: str,
    workflow: str,
    dispatch_id: str,
    commit: str,
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> list[dict[str, object]]:
    raw = _gh(
        [
            f"repos/{repository}/actions/workflows/{workflow}/runs",
            "-f",
            "branch=main",
            "-f",
            "event=workflow_dispatch",
            "-F",
            "per_page=100",
        ],
        input_text=None,
        runner=runner,
    )
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as error:
        raise FollowupError(f"GitHub returned malformed run data for {workflow}.") from error
    runs = payload.get("workflow_runs") if isinstance(payload, dict) else None
    if not isinstance(runs, list):
        raise FollowupError(f"GitHub returned no workflow run list for {workflow}.")
    title_prefix = WORKFLOWS[workflow]
    expected_title = f"{title_prefix} ({dispatch_id})"
    return [
        run
        for run in runs
        if isinstance(run, dict)
        and run.get("display_title") == expected_title
        and run.get("head_sha") == commit
    ]


def wait_for_workflow(
    repository: str,
    workflow: str,
    dispatch_id: str,
    commit: str,
    *,
    timeout_seconds: int,
    poll_seconds: int,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    monotonic: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> WorkflowResult:
    deadline = monotonic() + timeout_seconds
    while monotonic() < deadline:
        runs = matching_runs(repository, workflow, dispatch_id, commit, runner=runner)
        if len(runs) > 1:
            raise FollowupError(f"Ambiguous correlated runs found for {workflow}; refusing to report success.")
        if runs:
            run = runs[0]
            status = str(run.get("status", ""))
            conclusion = str(run.get("conclusion") or "")
            if status == "completed":
                result = WorkflowResult(workflow, status, conclusion, str(run.get("html_url", "")))
                if conclusion != "success":
                    raise FollowupError(
                        f"{workflow} completed with conclusion={conclusion or 'unknown'}"
                        + (f" ({result.url})" if result.url else ".")
                    )
                return result
            if status not in {"queued", "in_progress", "waiting", "requested", "pending"}:
                raise FollowupError(f"{workflow} returned unexpected run status={status or 'unknown'}.")
        sleep(min(poll_seconds, max(0, deadline - monotonic())))
    raise FollowupError(f"Timed out waiting for correlated {workflow} run {dispatch_id}.")


def run_followups(
    repository: str,
    dispatch_id: str,
    commit: str,
    *,
    timeout_seconds: int,
    poll_seconds: int,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    monotonic: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> list[WorkflowResult]:
    for workflow in WORKFLOWS:
        dispatch_workflow(repository, workflow, dispatch_id, runner=runner)

    deadline = monotonic() + timeout_seconds
    results: list[WorkflowResult] = []
    failures: list[str] = []
    for workflow in WORKFLOWS:
        remaining = max(0, int(deadline - monotonic()))
        if remaining <= 0:
            failures.append(f"{workflow}: shared follow-up timeout expired before its result was observed.")
            continue
        try:
            results.append(
                wait_for_workflow(
                    repository,
                    workflow,
                    dispatch_id,
                    commit,
                    timeout_seconds=remaining,
                    poll_seconds=poll_seconds,
                    runner=runner,
                    monotonic=monotonic,
                    sleep=sleep,
                )
            )
        except FollowupError as error:
            failures.append(f"{workflow}: {error}")
    if failures:
        raise FollowupError("; ".join(failures))
    return results


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--dispatch-id", required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--timeout-seconds", type=int, default=2400)
    parser.add_argument("--poll-seconds", type=int, default=15)
    args = parser.parse_args(argv)
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", args.repository):
        parser.error("--repository must be OWNER/REPOSITORY")
    if not DISPATCH_ID_RE.fullmatch(args.dispatch_id):
        parser.error("--dispatch-id has invalid characters or length")
    if not SHA_RE.fullmatch(args.commit):
        parser.error("--commit must be a full lowercase Git SHA")
    if args.timeout_seconds < 1 or args.timeout_seconds > 2400:
        parser.error("--timeout-seconds must be between 1 and 2400")
    if args.poll_seconds < 1 or args.poll_seconds > 60:
        parser.error("--poll-seconds must be between 1 and 60")

    try:
        results = run_followups(
            args.repository,
            args.dispatch_id,
            args.commit,
            timeout_seconds=args.timeout_seconds,
            poll_seconds=args.poll_seconds,
        )
    except FollowupError as error:
        print(f"RELEASE_FOLLOW_UP_STATUS=FAIL: {error}", file=sys.stderr)
        return 1
    for result in results:
        print(f"{result.workflow.upper().replace('-', '_').replace('.', '_')}=PASS {result.url}".rstrip())
    print("RELEASE_FOLLOW_UP_STATUS=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
