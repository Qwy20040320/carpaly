#!/usr/bin/env python3
"""Credential-free tests for the fail-closed Release signer preflight."""

from __future__ import annotations

import base64
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import release_signing_preflight as preflight


EXPECTED = "d9b329525fc1ef21c365fab72c10367527cc038297c4f30eaa22b2207429139e"
OTHER = "0" * 64
SECRET = "never-print-this-secret"


def make_env(**overrides: str) -> dict[str, str]:
    values = {
        "RELEASE_KEYSTORE_BASE64": base64.b64encode(b"\x30\x03\x02\x01\x00").decode("ascii"),
        "RELEASE_STORE_PASSWORD": "synthetic-store-password",
        "RELEASE_KEY_ALIAS": "release",
        "RELEASE_KEY_PASSWORD": "synthetic-key-password",
        "RELEASE_SIGNING_CERT_SHA256": EXPECTED,
    }
    values.update(overrides)
    return values


class FakeJavaTools:
    def __init__(self, *, fingerprint: str = EXPECTED, list_result: tuple[int, str, str] | None = None,
                 alias_result: tuple[int, str, str] | None = None,
                 sign_result: tuple[int, str, str] | None = None,
                 verify_result: tuple[int, str, str] | None = None) -> None:
        self.fingerprint = fingerprint
        self.list_result = list_result
        self.alias_result = alias_result
        self.sign_result = sign_result
        self.verify_result = verify_result
        self.commands: list[list[str]] = []

    def __call__(self, command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        self.commands.append(command)
        tool = Path(command[0]).name.lower()
        if "keytool" in tool:
            if "-alias" in command:
                code, out, err = self.alias_result or (
                    0,
                    f"Alias name: release\nSHA256: {':'.join(self.fingerprint[i:i + 2] for i in range(0, 64, 2))}\n",
                    "",
                )
            else:
                code, out, err = self.list_result or (0, "Alias name: release\n", "")
        elif "-verify" in command:
            code, out, err = self.verify_result or (0, "jar verified.\n", "")
        else:
            code, out, err = self.sign_result or (0, "jar signed.\n", "")
            if code == 0 and "-signedjar" in command:
                Path(command[command.index("-signedjar") + 1]).write_bytes(b"temporary signed test jar")
        return subprocess.CompletedProcess(command, code, out, err)


class FingerprintTests(unittest.TestCase):
    def test_normalize_plain_lowercase(self):
        self.assertEqual(preflight.normalize_fingerprint(EXPECTED), EXPECTED)

    def test_normalize_uppercase_colons(self):
        value = ":".join(EXPECTED[i:i + 2].upper() for i in range(0, 64, 2))
        self.assertEqual(preflight.normalize_fingerprint(value), EXPECTED)

    def test_rejects_short_fingerprint(self):
        with self.assertRaises(preflight.PreflightFailure) as raised:
            preflight.normalize_fingerprint("abcd")
        self.assertEqual(raised.exception.code, "WORKFLOW_CONFIGURATION_ERROR")

    def test_rejects_non_hex_fingerprint(self):
        with self.assertRaises(preflight.PreflightFailure):
            preflight.normalize_fingerprint("g" * 64)

    def test_rejects_fingerprint_with_label(self):
        with self.assertRaises(preflight.PreflightFailure):
            preflight.normalize_fingerprint("SHA256:" + EXPECTED)


class Base64Tests(unittest.TestCase):
    def test_decodes_wrapped_base64(self):
        payload = b"\x30\x03\x02\x01\x00"
        encoded = base64.b64encode(payload).decode("ascii")
        self.assertEqual(preflight.decode_keystore(encoded[:8] + "\n" + encoded[8:]), payload)

    def test_rejects_invalid_base64(self):
        with self.assertRaises(preflight.PreflightFailure) as raised:
            preflight.decode_keystore("not a keystore!")
        self.assertEqual(raised.exception.code, "KEYSTORE_DECODE_ERROR")

    def test_rejects_empty_base64(self):
        with self.assertRaises(preflight.PreflightFailure) as raised:
            preflight.decode_keystore(" \n ")
        self.assertEqual(raised.exception.code, "ENVIRONMENT_SECRET_MISSING")

    def test_rejects_empty_decoded_keystore(self):
        with self.assertRaises(preflight.PreflightFailure) as raised:
            preflight.decode_keystore("")
        self.assertEqual(raised.exception.code, "ENVIRONMENT_SECRET_MISSING")

    def test_rejects_oversized_keystore(self):
        # Exercise the bound without allocating a huge object by mocking decode.
        with patch.object(preflight.base64, "b64decode", return_value=b"x" * (64 * 1024 * 1024 + 1)):
            with self.assertRaises(preflight.PreflightFailure) as raised:
                preflight.decode_keystore("eA==")
        self.assertEqual(raised.exception.code, "KEYSTORE_DECODE_ERROR")

    def test_rejects_jks_or_pem_mislabeled_as_pkcs12(self):
        for payload in (b"\xfe\xed\xfe\xedJKS", b"-----BEGIN PKCS12-----"):
            with self.subTest(payload=payload[:8]), self.assertRaises(preflight.PreflightFailure) as raised:
                preflight.decode_keystore(base64.b64encode(payload).decode("ascii"))
            self.assertEqual(raised.exception.code, "KEYSTORE_DECODE_ERROR")


class ErrorClassificationTests(unittest.TestCase):
    def test_wrong_store_password_is_distinct(self):
        code, _ = preflight._classify_keystore_read_failure("keystore password was incorrect")
        self.assertEqual(code, "PASSWORD_ERROR")

    def test_bad_pkcs12_format_is_distinct(self):
        code, _ = preflight._classify_keystore_read_failure("Invalid keystore format")
        self.assertEqual(code, "KEYSTORE_DECODE_ERROR")

    def test_tamper_or_password_diagnostic_is_not_claimed_as_exact_root(self):
        code, detail = preflight._classify_keystore_read_failure(
            "Keystore was tampered with, or password was incorrect"
        )
        self.assertEqual(code, "PASSWORD_ERROR")
        self.assertIn("check both", detail)

    def test_unrecognized_store_type_is_format_error(self):
        code, _ = preflight._classify_keystore_read_failure("Unrecognized keystore format")
        self.assertEqual(code, "KEYSTORE_DECODE_ERROR")

    def test_generic_certificate_read_error_is_distinct(self):
        code, _ = preflight._classify_keystore_read_failure("provider could not parse entry")
        self.assertEqual(code, "CERTIFICATE_PARSE_ERROR")

    def test_missing_secret_names_are_reported_without_values(self):
        env = make_env()
        env.pop("RELEASE_KEY_PASSWORD")
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(preflight.PreflightFailure) as raised:
                preflight.verify_keystore(output_path=Path(directory) / "unused.p12", environment=env)
        self.assertEqual(raised.exception.code, "ENVIRONMENT_SECRET_MISSING")
        self.assertIn("RELEASE_KEY_PASSWORD", raised.exception.safe_message())
        self.assertNotIn(SECRET, raised.exception.safe_message())


class PreflightTests(unittest.TestCase):
    def verify(self, fake: FakeJavaTools, env: dict[str, str] | None = None) -> tuple[Path, preflight.PreflightResult]:
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        output = Path(folder.name) / "private" / "release.p12"
        result = preflight.verify_keystore(
            output_path=output,
            environment=env or make_env(),
            runner=fake,
            keytool="keytool",
            jarsigner="jarsigner",
        )
        return output, result

    def test_matching_pkcs12_alias_and_signer_pass(self):
        output, result = self.verify(FakeJavaTools())
        self.assertTrue(output.is_file())
        self.assertEqual(result.certificate_sha256, EXPECTED)

    def test_fingerprint_mismatch_is_reported_with_public_hashes(self):
        with tempfile.TemporaryDirectory() as directory:
            fake = FakeJavaTools(fingerprint=OTHER)
            with self.assertRaises(preflight.PreflightFailure) as raised:
                preflight.verify_keystore(
                    output_path=Path(directory) / "keystore.p12",
                    environment=make_env(), runner=fake, keytool="keytool", jarsigner="jarsigner"
                )
        failure = raised.exception
        self.assertEqual(failure.code, "SIGNER_MISMATCH")
        self.assertEqual(failure.actual_sha256, OTHER)
        self.assertEqual(failure.expected_sha256, EXPECTED)

    def test_wrong_alias_is_reported_before_signing(self):
        with tempfile.TemporaryDirectory() as directory:
            fake = FakeJavaTools()
            with self.assertRaises(preflight.PreflightFailure) as raised:
                preflight.verify_keystore(
                    output_path=Path(directory) / "keystore.p12",
                    environment=make_env(RELEASE_KEY_ALIAS="missing"), runner=fake,
                    keytool="keytool", jarsigner="jarsigner"
                )
        self.assertEqual(raised.exception.code, "ALIAS_MISMATCH")
        self.assertEqual(len(fake.commands), 1)

    def test_store_password_error_is_not_reported_as_signer_mismatch(self):
        fake = FakeJavaTools(list_result=(1, "", "keystore password was incorrect"))
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(preflight.PreflightFailure) as raised:
                preflight.verify_keystore(
                    output_path=Path(directory) / "keystore.p12", environment=make_env(),
                    runner=fake, keytool="keytool", jarsigner="jarsigner"
                )
        self.assertEqual(raised.exception.code, "PASSWORD_ERROR")

    def test_corrupt_pkcs12_is_not_reported_as_signer_mismatch(self):
        fake = FakeJavaTools(list_result=(1, "", "Invalid keystore format"))
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(preflight.PreflightFailure) as raised:
                preflight.verify_keystore(
                    output_path=Path(directory) / "keystore.p12", environment=make_env(),
                    runner=fake, keytool="keytool", jarsigner="jarsigner"
                )
        self.assertEqual(raised.exception.code, "KEYSTORE_DECODE_ERROR")

    def test_missing_certificate_digest_is_parse_error(self):
        fake = FakeJavaTools(alias_result=(0, "Alias name: release\nCertificate: X.509\n", ""))
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(preflight.PreflightFailure) as raised:
                preflight.verify_keystore(
                    output_path=Path(directory) / "keystore.p12", environment=make_env(),
                    runner=fake, keytool="keytool", jarsigner="jarsigner"
                )
        self.assertEqual(raised.exception.code, "CERTIFICATE_PARSE_ERROR")

    def test_key_password_failure_is_distinct(self):
        fake = FakeJavaTools(sign_result=(1, "", "UnrecoverableKeyException"))
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(preflight.PreflightFailure) as raised:
                preflight.verify_keystore(
                    output_path=Path(directory) / "keystore.p12", environment=make_env(),
                    runner=fake, keytool="keytool", jarsigner="jarsigner"
                )
        self.assertEqual(raised.exception.code, "PASSWORD_ERROR")

    def test_failed_preflight_removes_decoded_keystore(self):
        fake = FakeJavaTools(fingerprint=OTHER)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "keystore.p12"
            with self.assertRaises(preflight.PreflightFailure):
                preflight.verify_keystore(
                    output_path=output, environment=make_env(), runner=fake,
                    keytool="keytool", jarsigner="jarsigner"
                )
            self.assertFalse(output.exists())

    def test_password_values_never_appear_in_process_arguments(self):
        fake = FakeJavaTools()
        self.verify(fake)
        flattened = " ".join(" ".join(command) for command in fake.commands)
        self.assertNotIn("synthetic-store-password", flattened)
        self.assertNotIn("synthetic-key-password", flattened)
        self.assertIn("RELEASE_STORE_PASSWORD", flattened)
        self.assertIn("RELEASE_KEY_PASSWORD", flattened)

    def test_credentials_are_passed_only_in_child_environment(self):
        fake = FakeJavaTools()
        self.verify(fake)
        # The test runner accepts **kwargs; the script uses env-backed keytool
        # options so passwords do not appear as command-line arguments.
        self.assertTrue(all("-storepass:env" in call for call in fake.commands if "keytool" in call[0]))

    def test_java_locale_is_pinned_for_cross_platform_parsing(self):
        fake = FakeJavaTools()
        self.verify(fake)
        self.assertTrue(all("-J-Duser.language=en" in call for call in fake.commands))
        self.assertTrue(all("-J-Duser.country=US" in call for call in fake.commands))

    def test_probe_uses_temporary_jar_and_not_an_apk(self):
        fake = FakeJavaTools()
        self.verify(fake)
        signing_commands = [call for call in fake.commands if "jarsigner" in Path(call[0]).name.lower()]
        self.assertEqual(len(signing_commands), 2)
        self.assertTrue(any("-signedjar" in call for call in signing_commands))
        self.assertTrue(all(".apk" not in " ".join(call).lower() for call in signing_commands))

    def test_all_listed_aliases_are_case_insensitive(self):
        fake = FakeJavaTools(list_result=(0, "Alias name: RELEASE\n", ""))
        output, _ = self.verify(fake)
        self.assertTrue(output.exists())

    def test_mfi_secrets_are_not_required_by_signer_preflight(self):
        fake = FakeJavaTools()
        self.verify(fake)
        # The exact signed-in values are intentionally not included in this helper's inputs.
        self.assertNotIn("MFI_IDENTITY_PK8_BASE64", preflight.EXPECTED_ENV_NAMES)

    def test_bad_certificate_fingerprint_does_not_run_jarsigner(self):
        fake = FakeJavaTools(fingerprint="bad")
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(preflight.PreflightFailure):
                preflight.verify_keystore(
                    output_path=Path(directory) / "keystore.p12", environment=make_env(),
                    runner=fake, keytool="keytool", jarsigner="jarsigner"
                )
        self.assertEqual(len(fake.commands), 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
