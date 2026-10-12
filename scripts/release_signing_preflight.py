#!/usr/bin/env python3
"""Validate a protected PKCS12 signer without printing or exposing credentials.

The script writes the decoded keystore to a caller-provided private runner path so
Gradle can use the same file after this fail-closed preflight. Only public SHA-256
certificate fingerprints and stable error categories are ever written to stdout.
"""

from __future__ import annotations

import argparse
import base64
import binascii
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping, Sequence


EXPECTED_ENV_NAMES = (
    "RELEASE_KEYSTORE_BASE64",
    "RELEASE_STORE_PASSWORD",
    "RELEASE_KEY_ALIAS",
    "RELEASE_KEY_PASSWORD",
    "RELEASE_SIGNING_CERT_SHA256",
)

FINGERPRINT_LINE = re.compile(
    r"(?im)^\s*(?:SHA-?256|Certificate fingerprint\s*\(SHA-256\))\s*:\s*([0-9a-f: ]+)\s*$"
)
ALIAS_LINE = re.compile(r"(?im)^\s*Alias name:\s*(.*?)\s*$")


@dataclass(frozen=True)
class PreflightResult:
    certificate_sha256: str
    keystore_path: Path


class PreflightFailure(Exception):
    def __init__(
        self,
        code: str,
        detail: str,
        *,
        actual_sha256: str | None = None,
        expected_sha256: str | None = None,
    ) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail
        self.actual_sha256 = actual_sha256
        self.expected_sha256 = expected_sha256

    def safe_message(self) -> str:
        message = f"{self.code}: {self.detail}"
        if self.actual_sha256:
            message += f" actual_sha256={self.actual_sha256}"
        if self.expected_sha256:
            message += f" expected_sha256={self.expected_sha256}"
        return message


def normalize_fingerprint(value: str) -> str:
    normalized = re.sub(r"[:\s]", "", value).lower()
    if not re.fullmatch(r"[0-9a-f]{64}", normalized):
        raise PreflightFailure(
            "WORKFLOW_CONFIGURATION_ERROR",
            "RELEASE_SIGNING_CERT_SHA256 must contain exactly 32 bytes of hex.",
        )
    return normalized


def decode_keystore(encoded: str) -> bytes:
    # Newlines are commonly introduced by base64 encoders and do not change the
    # payload. Other non-base64 characters remain a hard error.
    compact = re.sub(r"\s+", "", encoded)
    if not compact:
        raise PreflightFailure(
            "ENVIRONMENT_SECRET_MISSING", "RELEASE_KEYSTORE_BASE64 is empty."
        )
    try:
        payload = base64.b64decode(compact, validate=True)
    except (binascii.Error, ValueError):
        raise PreflightFailure(
            "KEYSTORE_DECODE_ERROR", "RELEASE_KEYSTORE_BASE64 is not valid base64."
        ) from None
    if not payload:
        raise PreflightFailure(
            "KEYSTORE_DECODE_ERROR", "Decoded PKCS12 keystore is empty."
        )
    if len(payload) > 64 * 1024 * 1024:
        raise PreflightFailure(
            "KEYSTORE_DECODE_ERROR", "Decoded PKCS12 keystore exceeds the 64 MiB limit."
        )
    # A PKCS#12 PFX is a DER-encoded ASN.1 SEQUENCE. This catches common
    # mistakes (JKS, PEM text, base64-of-base64) before keytool's ambiguous
    # "tampered with or password incorrect" diagnostic.
    if payload[0] != 0x30:
        raise PreflightFailure(
            "KEYSTORE_DECODE_ERROR", "Decoded keystore does not have a PKCS12 DER sequence header."
        )
    return payload


def _environment_value(environment: Mapping[str, str], name: str) -> str:
    value = environment.get(name)
    if not value:
        raise PreflightFailure(
            "ENVIRONMENT_SECRET_MISSING", f"Required environment value {name} is absent."
        )
    return value


def _tool_output(
    runner: Callable[..., subprocess.CompletedProcess[str]],
    command: Sequence[str],
    environment: Mapping[str, str],
) -> subprocess.CompletedProcess[str]:
    # Force keytool's public metadata/error labels to English on both Windows
    # and Linux. This is a Java process property, not a credential.
    full_command = [command[0], "-J-Duser.language=en", "-J-Duser.country=US", *command[1:]]
    try:
        return runner(
            full_command,
            check=False,
            text=True,
            capture_output=True,
            env=dict(environment),
        )
    except OSError:
        raise PreflightFailure(
            "WORKFLOW_CONFIGURATION_ERROR", "Java keytool/jarsigner is unavailable."
        ) from None


def _classify_keystore_read_failure(output: str) -> tuple[str, str]:
    lower = output.lower()
    if "keystore was tampered with, or password was incorrect" in lower:
        return (
            "PASSWORD_ERROR",
            "PKCS12 integrity verification failed; check both the store password and the encoded file integrity.",
        )
    if any(
        phrase in lower
        for phrase in (
            "password was incorrect",
            "keystore password was incorrect",
            "failed to decrypt",
            "unrecoverablekeyexception",
            "wrong password",
        )
    ):
        return "PASSWORD_ERROR", "The store password was rejected by keytool."
    if any(
        phrase in lower
        for phrase in (
            "invalid keystore format",
            "unrecognized keystore format",
            "unsupported keystore format",
            "not a pkcs12",
            "not a valid keystore",
            "der input",
            "malformed",
        )
    ):
        return "KEYSTORE_DECODE_ERROR", "The decoded file is not a readable PKCS12 keystore."
    return "CERTIFICATE_PARSE_ERROR", "keytool could not read the PKCS12 certificate metadata."


def _write_probe_jar(path: Path) -> None:
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_STORED) as archive:
        archive.writestr("probe.txt", "temporary signing preflight\n")


def verify_keystore(
    *,
    output_path: Path,
    environment: Mapping[str, str] | None = None,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    keytool: str | None = None,
    jarsigner: str | None = None,
) -> PreflightResult:
    env = dict(os.environ if environment is None else environment)
    missing = [name for name in EXPECTED_ENV_NAMES if not env.get(name)]
    if missing:
        raise PreflightFailure(
            "ENVIRONMENT_SECRET_MISSING",
            "Required values are absent: " + ", ".join(missing) + ".",
        )

    expected = normalize_fingerprint(env["RELEASE_SIGNING_CERT_SHA256"])
    payload = decode_keystore(env["RELEASE_KEYSTORE_BASE64"])
    keytool_path = keytool or shutil.which("keytool")
    jarsigner_path = jarsigner or shutil.which("jarsigner")
    if not keytool_path or not jarsigner_path:
        raise PreflightFailure(
            "WORKFLOW_CONFIGURATION_ERROR", "Java keytool and jarsigner must be on PATH."
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        output_path.write_bytes(payload)
        try:
            os.chmod(output_path, 0o600)
        except OSError:
            # Windows ACLs are inherited from the private runner temp directory.
            pass
        del payload

        list_result = _tool_output(
            runner,
            [
                keytool_path,
                "-list",
                "-v",
                "-keystore",
                str(output_path),
                "-storetype",
                "PKCS12",
                "-storepass:env",
                "RELEASE_STORE_PASSWORD",
            ],
            env,
        )
        if list_result.returncode != 0:
            code, detail = _classify_keystore_read_failure(
                f"{list_result.stdout}\n{list_result.stderr}"
            )
            raise PreflightFailure(code, detail)

        aliases = {match.group(1).strip().casefold() for match in ALIAS_LINE.finditer(list_result.stdout)}
        wanted_alias = env["RELEASE_KEY_ALIAS"].strip()
        if not wanted_alias or wanted_alias.casefold() not in aliases:
            raise PreflightFailure(
                "ALIAS_MISMATCH", "RELEASE_KEY_ALIAS is not present in the decoded PKCS12 keystore."
            )

        alias_result = _tool_output(
            runner,
            [
                keytool_path,
                "-list",
                "-v",
                "-alias",
                wanted_alias,
                "-keystore",
                str(output_path),
                "-storetype",
                "PKCS12",
                "-storepass:env",
                "RELEASE_STORE_PASSWORD",
            ],
            env,
        )
        if alias_result.returncode != 0:
            code, detail = _classify_keystore_read_failure(
                f"{alias_result.stdout}\n{alias_result.stderr}"
            )
            raise PreflightFailure(code, detail)

        fingerprint_match = FINGERPRINT_LINE.search(alias_result.stdout)
        if not fingerprint_match:
            raise PreflightFailure(
                "CERTIFICATE_PARSE_ERROR", "keytool output did not include a SHA-256 certificate fingerprint."
            )
        actual = re.sub(r"[^0-9a-fA-F]", "", fingerprint_match.group(1)).lower()
        if not re.fullmatch(r"[0-9a-f]{64}", actual):
            raise PreflightFailure(
                "CERTIFICATE_PARSE_ERROR", "keytool returned a malformed SHA-256 certificate fingerprint."
            )
        if actual != expected:
            raise PreflightFailure(
                "SIGNER_MISMATCH",
                "The readable PKCS12 private-key entry certificate differs from the pinned Release identity.",
                actual_sha256=actual,
                expected_sha256=expected,
            )

        # Validate the key password without modifying the protected keystore or
        # producing an APK. The temporary JAR and signature are removed below.
        with tempfile.TemporaryDirectory(prefix="carpaly-signing-probe-") as probe_dir:
            probe = Path(probe_dir)
            unsigned_jar = probe / "probe.jar"
            signed_jar = probe / "probe-signed.jar"
            _write_probe_jar(unsigned_jar)
            sign_result = _tool_output(
                runner,
                [
                    jarsigner_path,
                    "-keystore",
                    str(output_path),
                    "-storetype",
                    "PKCS12",
                    "-storepass:env",
                    "RELEASE_STORE_PASSWORD",
                    "-keypass:env",
                    "RELEASE_KEY_PASSWORD",
                    "-signedjar",
                    str(signed_jar),
                    str(unsigned_jar),
                    wanted_alias,
                ],
                env,
            )
            if sign_result.returncode != 0 or not signed_jar.is_file():
                combined = f"{sign_result.stdout}\n{sign_result.stderr}".lower()
                if "alias" in combined and ("does not exist" in combined or "not found" in combined):
                    raise PreflightFailure(
                        "ALIAS_MISMATCH", "jarsigner could not locate the configured key alias."
                    )
                raise PreflightFailure(
                    "PASSWORD_ERROR", "The key password was rejected during the temporary signing probe."
                )

            verify_result = _tool_output(
                runner,
                [jarsigner_path, "-verify", str(signed_jar)],
                env,
            )
            if verify_result.returncode != 0:
                raise PreflightFailure(
                    "CERTIFICATE_PARSE_ERROR", "The temporary signer output could not be verified."
                )

        return PreflightResult(actual, output_path)
    except Exception:
        try:
            output_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--keystore-path", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        result = verify_keystore(output_path=args.keystore_path)
    except PreflightFailure as failure:
        print(f"RELEASE_SIGNING_STATUS={failure.safe_message()}", file=sys.stderr)
        return 1
    print("RELEASE_SIGNING_STATUS=PASS")
    print(f"RELEASE_SIGNER_CERT_SHA256={result.certificate_sha256}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
