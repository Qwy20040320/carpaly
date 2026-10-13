from __future__ import annotations

import unittest
import subprocess
from types import SimpleNamespace
from unittest.mock import patch

from scripts.ota_key_preflight import PreflightError, _gh_json, _synthetic_self_test, trust_key_ids


class OtaKeyPreflightTests(unittest.TestCase):
    def test_synthetic_in_memory_key_signs_and_verifies_without_artifacts(self):
        _synthetic_self_test()

    def test_trust_store_key_ids_must_be_unique(self):
        with self.assertRaisesRegex(PreflightError, "duplicate"):
            trust_key_ids({"schemaVersion": 1, "keys": [
                {"keyId": "same"}, {"keyId": "same"},
            ]})

    def test_empty_production_trust_root_is_valid_but_still_empty(self):
        self.assertEqual(trust_key_ids({"schemaVersion": 1, "keys": []}), [])

    def test_github_cli_json_is_decoded_as_utf8_on_windows(self):
        with patch("scripts.ota_key_preflight.subprocess.run", return_value=SimpleNamespace(
            returncode=0, stdout='{"description":"星越L"}'.encode("utf-8"),
        )) as run:
            self.assertEqual(_gh_json("user"), {"description": "星越L"})
        self.assertEqual(run.call_args.kwargs["timeout"], 25)

    def test_github_cli_invalid_utf8_fails_without_emitting_a_reader_traceback(self):
        with patch("scripts.ota_key_preflight.subprocess.run", return_value=SimpleNamespace(
            returncode=0, stdout=b"\x94",
        )):
            with self.assertRaisesRegex(PreflightError, "malformed JSON"):
                _gh_json("user")

    def test_github_cli_timeout_fails_closed_without_echoing_process_output(self):
        with patch("scripts.ota_key_preflight.subprocess.run", side_effect=subprocess.TimeoutExpired(
            cmd=["gh", "api", "user"], timeout=25, output="private response body",
        )):
            with self.assertRaisesRegex(PreflightError, "no secret values were requested"):
                _gh_json("user")


if __name__ == "__main__":
    unittest.main(verbosity=2)
