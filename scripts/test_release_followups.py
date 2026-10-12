#!/usr/bin/env python3
"""Offline contract tests for correlated post-release workflow dispatch."""

from __future__ import annotations

import json
import io
import subprocess
import unittest
from contextlib import redirect_stderr

from scripts import dispatch_release_followups as followups


COMMIT = "a" * 40
DISPATCH_ID = "12345-2"
REPO = "Qwy20040320/carpaly"


class FakeGh:
    def __init__(self, run_pages: dict[str, list[dict[str, object]]]) -> None:
        self.run_pages = run_pages
        self.calls: list[tuple[list[str], str | None]] = []

    def __call__(self, command, *, input, **_kwargs):
        self.calls.append((command, input))
        endpoint = next((item for item in command if "/actions/workflows/" in item), "")
        workflow = next((name for name in followups.WORKFLOWS if name in endpoint), "")
        if "--method" in command and command[command.index("--method") + 1] == "POST":
            self.assert_dispatch_payload(workflow, input)
            return subprocess.CompletedProcess(command, 0, "", "")
        runs = self.run_pages[workflow]
        return subprocess.CompletedProcess(command, 0, json.dumps({"workflow_runs": runs}), "")

    @staticmethod
    def assert_dispatch_payload(workflow: str, raw: str | None) -> None:
        if workflow not in followups.WORKFLOWS or raw is None:
            raise AssertionError("dispatch did not use an expected workflow and JSON body")
        payload = json.loads(raw)
        if payload != {"ref": "main", "inputs": {"dispatch_id": DISPATCH_ID}}:
            raise AssertionError("dispatch payload was not pinned to main and the correlation ID")


def run(title_prefix: str, *, status: str = "completed", conclusion: str = "success", sha: str = COMMIT):
    return {
        "display_title": f"{title_prefix} ({DISPATCH_ID})",
        "head_sha": sha,
        "status": status,
        "conclusion": conclusion,
        "html_url": "https://github.com/Qwy20040320/carpaly/actions/runs/12345",
    }


class ReleaseFollowupTests(unittest.TestCase):
    def test_dispatches_both_and_waits_for_correlated_successes(self):
        pages_title = followups.WORKFLOWS["pages.yml"]
        docs_title = followups.WORKFLOWS["release-docs-sync.yml"]
        runner = FakeGh(
            {
                "pages.yml": [run(pages_title)],
                "release-docs-sync.yml": [run(docs_title)],
            }
        )
        results = followups.run_followups(
            REPO, DISPATCH_ID, COMMIT, timeout_seconds=10, poll_seconds=1,
            runner=runner, sleep=lambda _seconds: None,
        )
        self.assertEqual([result.workflow for result in results], list(followups.WORKFLOWS))
        dispatches = [
            call for call in runner.calls
            if "--method" in call[0] and call[0][call[0].index("--method") + 1] == "POST"
        ]
        self.assertEqual(len(dispatches), 2)

    def test_unrelated_or_wrong_sha_run_is_not_accepted(self):
        title = followups.WORKFLOWS["pages.yml"]
        runner = FakeGh({"pages.yml": [run(title, sha="b" * 40)]})
        with self.assertRaisesRegex(followups.FollowupError, "Timed out"):
            followups.wait_for_workflow(
                REPO, "pages.yml", DISPATCH_ID, COMMIT, timeout_seconds=1, poll_seconds=1,
                runner=runner, monotonic=iter([0.0, 0.0, 0.0, 2.0]).__next__, sleep=lambda _seconds: None,
            )

    def test_failed_downstream_run_fails_followup(self):
        title = followups.WORKFLOWS["pages.yml"]
        runner = FakeGh({"pages.yml": [run(title, conclusion="failure")]})
        with self.assertRaisesRegex(followups.FollowupError, "conclusion=failure"):
            followups.wait_for_workflow(
                REPO, "pages.yml", DISPATCH_ID, COMMIT, timeout_seconds=10, poll_seconds=1,
                runner=runner, sleep=lambda _seconds: None,
            )

    def test_ambiguous_correlated_runs_fail_closed(self):
        title = followups.WORKFLOWS["pages.yml"]
        runner = FakeGh({"pages.yml": [run(title), run(title)]})
        with self.assertRaisesRegex(followups.FollowupError, "Ambiguous"):
            followups.wait_for_workflow(
                REPO, "pages.yml", DISPATCH_ID, COMMIT, timeout_seconds=10, poll_seconds=1,
                runner=runner, sleep=lambda _seconds: None,
            )

    def test_api_failure_does_not_leak_arbitrary_error_output(self):
        def failing_runner(command, **kwargs):
            return subprocess.CompletedProcess(command, 1, "", "secret-shaped-error-text")

        with self.assertRaises(followups.FollowupError) as raised:
            followups.dispatch_workflow(REPO, "pages.yml", DISPATCH_ID, runner=failing_runner)
        self.assertNotIn("secret-shaped-error-text", str(raised.exception))

    def test_timeout_and_poll_bounds_are_checked_by_cli(self):
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            followups.main([
                "--repository", REPO, "--dispatch-id", DISPATCH_ID,
                "--commit", COMMIT, "--timeout-seconds", "2401",
            ])


if __name__ == "__main__":
    unittest.main(verbosity=2)
