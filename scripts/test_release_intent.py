from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.release_intent import ReleaseIntentError, evaluate


class ReleaseIntentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        subprocess.run(["git", "init", "-q"], cwd=self.root, check=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=self.root, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=self.root, check=True)
        (self.root / "config").mkdir()
        (self.root / "mobile").mkdir()
        self.base_intent = {
            "schemaVersion": 1, "enabled": False, "channel": "beta",
            "versionName": "1.1.52", "versionCode": 40,
        }
        self.ledger = {
            "current": {"versionName": "1.1.52", "versionCode": 40, "channel": "test"},
        }
        self._write_state(self.base_intent)
        self._commit("baseline")
        self.baseline = self._head()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _write_state(self, intent: dict) -> None:
        (self.root / "config/release-intent.json").write_text(json.dumps(intent), encoding="utf-8")
        (self.root / "config/android-version-ledger.json").write_text(json.dumps(self.ledger), encoding="utf-8")
        (self.root / "mobile/build.gradle.kts").write_text(
            'versionCode = 40\nversionName = "1.1.52"\n', encoding="utf-8",
        )

    def _commit(self, message: str) -> None:
        subprocess.run(["git", "add", "config", "mobile"], cwd=self.root, check=True)
        subprocess.run(["git", "commit", "-qm", message], cwd=self.root, check=True)

    def _head(self) -> str:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=self.root, text=True).strip()

    def _evaluate(self, **overrides):
        values = {
            "root": self.root, "commit": self._head(), "event": "push", "branch": "main",
            "conclusion": "success", "main_sha": self._head(),
        }
        values.update(overrides)
        return evaluate(**values)

    def test_disabled_intent_does_not_publish(self):
        self._write_state({**self.base_intent, "reason": "still intentionally disabled"})
        self._commit("change intent but leave disabled")
        result = self._evaluate()
        self.assertFalse(result.publish)
        self.assertEqual(result.reason, "release-intent-disabled")

    def test_document_only_commit_does_not_publish_even_if_intent_remains_enabled(self):
        enabled = {**self.base_intent, "enabled": True}
        self._write_state(enabled)
        self._commit("arm release intent")
        (self.root / "README.md").write_text("docs only\n", encoding="utf-8")
        subprocess.run(["git", "add", "README.md"], cwd=self.root, check=True)
        subprocess.run(["git", "commit", "-qm", "docs only"], cwd=self.root, check=True)
        result = self._evaluate()
        self.assertFalse(result.publish)
        self.assertEqual(result.reason, "release-intent-not-changed-by-this-commit")

    def test_explicit_current_beta_intent_passes(self):
        self._write_state({**self.base_intent, "enabled": True})
        self._commit("arm beta release")
        result = self._evaluate()
        self.assertTrue(result.publish)
        self.assertEqual(result.release_tag, "v1.1.52")
        self.assertTrue(result.prerelease)

    def test_pr_and_non_success_contexts_never_publish(self):
        self._write_state({**self.base_intent, "enabled": True})
        self._commit("arm beta release")
        self.assertFalse(self._evaluate(event="pull_request").publish)
        self.assertFalse(self._evaluate(conclusion="failure").publish)

    def test_stale_main_sha_skips_publication(self):
        self._write_state({**self.base_intent, "enabled": True})
        self._commit("arm beta release")
        self.assertEqual(self._evaluate(main_sha=self.baseline).reason, "main-advanced-since-ci")

    def test_intent_must_match_ledger_and_gradle(self):
        self._write_state({**self.base_intent, "enabled": True, "versionCode": 41})
        self._commit("mismatch code")
        with self.assertRaisesRegex(ReleaseIntentError, "version-ledger"):
            self._evaluate()

    def test_stable_intent_must_use_release_track(self):
        self._write_state({**self.base_intent, "enabled": True, "channel": "stable"})
        self._commit("stable mismatch")
        with self.assertRaisesRegex(ReleaseIntentError, "ledger track"):
            self._evaluate()

    def test_version_name_must_match_gradle(self):
        self._write_state({**self.base_intent, "enabled": True, "versionName": "1.1.53"})
        self.ledger["current"]["versionName"] = "1.1.53"
        (self.root / "config/android-version-ledger.json").write_text(json.dumps(self.ledger), encoding="utf-8")
        self._commit("gradle mismatch")
        with self.assertRaisesRegex(ReleaseIntentError, "Gradle version"):
            self._evaluate()

    def test_tag_conflict_fails_closed(self):
        self._write_state({**self.base_intent, "enabled": True})
        self._commit("arm beta release")
        subprocess.run(["git", "tag", "v1.1.52", self.baseline], cwd=self.root, check=True)
        with self.assertRaisesRegex(ReleaseIntentError, "different commit"):
            self._evaluate()

    def test_same_target_existing_tag_remains_eligible_for_safe_draft_recovery(self):
        self._write_state({**self.base_intent, "enabled": True})
        self._commit("arm beta release")
        subprocess.run(["git", "tag", "v1.1.52", self._head()], cwd=self.root, check=True)
        self.assertTrue(self._evaluate().publish)


if __name__ == "__main__":
    unittest.main(verbosity=2)
