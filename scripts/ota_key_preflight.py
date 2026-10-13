#!/usr/bin/env python3
"""Local, read-only OTA key and GitHub Environment preparation checks.

This utility deliberately has no production-key generation, GitHub write, upload,
deployment, or release mode. ``self-test`` uses an ephemeral in-memory test key.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

if __package__:
    from . import ota_manifest
    from .export_ota_public_key import public_key_record
    from .ota_key_material import parse_p256_pkcs8_private_key
else:
    import ota_manifest
    from export_ota_public_key import public_key_record
    from ota_key_material import parse_p256_pkcs8_private_key


ROOT = Path(__file__).resolve().parents[1]
TRUST_PATH = ROOT / "common/src/main/res/raw/ota_manifest_public_keys.json"
REPOSITORY = "Qwy20040320/carpaly"
ENVIRONMENT_REQUIREMENTS = {
    "github-pages": (set(), set()),
    "mfi-public-release": (
        {"MFI_IDENTITY_PK8_BASE64", "MFI_CERTIFICATE_P7B_BASE64", "RELEASE_KEYSTORE_BASE64",
         "RELEASE_KEY_ALIAS", "RELEASE_KEY_PASSWORD", "RELEASE_STORE_PASSWORD"},
        {"MFI_PUBLIC_DISTRIBUTION_REVIEWED", "RELEASE_SIGNING_CERT_SHA256"},
    ),
    "release-policy-audit": ({"RELEASE_POLICY_READ_TOKEN"}, set()),
    "ota-manifest-publisher": ({"OTA_MANIFEST_SIGNING_PRIVATE_KEY_PEM"}, {"OTA_MANIFEST_SIGNING_KEY_ID"}),
}


class PreflightError(ValueError):
    pass


def trust_key_ids(trust: Any) -> list[str]:
    if not isinstance(trust, dict) or trust.get("schemaVersion") != 1 or not isinstance(trust.get("keys"), list):
        raise PreflightError("App-pinned OTA trust store is malformed")
    ids: list[str] = []
    for record in trust["keys"]:
        if not isinstance(record, dict) or not isinstance(record.get("keyId"), str):
            raise PreflightError("OTA trust store contains a malformed key record")
        ids.append(record["keyId"])
    if len(ids) != len(set(ids)):
        raise PreflightError("OTA trust store contains duplicate key ids")
    return ids


def _private_path_is_safe(path: Path) -> bool:
    resolved = path.resolve(strict=True)
    try:
        relative = resolved.relative_to(ROOT.resolve())
    except ValueError:
        return True
    relative_posix = relative.as_posix()
    tracked = subprocess.run(
        ["git", "ls-files", "--error-unmatch", "--", relative_posix],
        cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
    )
    if tracked.returncode == 0:
        raise PreflightError("Private-key input is Git-tracked; move it outside the repository")
    ignored = subprocess.run(
        ["git", "check-ignore", "--quiet", "--", relative_posix],
        cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
    )
    if ignored.returncode != 0:
        raise PreflightError("Private-key input inside the repository is not ignored by Git")
    return True


def _gh_json(endpoint: str) -> Any:
    try:
        result = subprocess.run(
            ["gh", "api", endpoint], cwd=ROOT, capture_output=True,
            timeout=25, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise PreflightError("GitHub read-only API request failed; no secret values were requested") from exc
    if result.returncode != 0:
        raise PreflightError("GitHub read-only API request failed; no secret values were requested")
    try:
        return json.loads(result.stdout.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PreflightError("GitHub read-only API returned malformed JSON") from exc


def audit_github_environment_names() -> dict[str, dict[str, Any]]:
    login = _gh_json("user").get("login", "")
    repository = _gh_json(f"repos/{REPOSITORY}")
    if repository.get("full_name", "").lower() != REPOSITORY.lower():
        raise PreflightError("GitHub CLI is not authenticated for the target repository")
    output: dict[str, dict[str, Any]] = {}
    for name, (required_secrets, required_variables) in ENVIRONMENT_REQUIREMENTS.items():
        environment = _gh_json(f"repos/{REPOSITORY}/environments/{name}")
        secret_response = _gh_json(f"repos/{REPOSITORY}/environments/{name}/secrets?per_page=100")
        variable_response = _gh_json(f"repos/{REPOSITORY}/environments/{name}/variables?per_page=100")
        secret_names = {item.get("name") for item in secret_response.get("secrets", [])
                        if isinstance(item, dict)}
        variable_names = {item.get("name") for item in variable_response.get("variables", [])
                          if isinstance(item, dict)}
        branches = _gh_json(f"repos/{REPOSITORY}/environments/{name}/deployment-branch-policies?per_page=100")
        output[name] = {
            "secretNamesPresent": sorted(secret_names & required_secrets),
            "secretNamesMissing": sorted(required_secrets - secret_names),
            "variableNamesPresent": sorted(variable_names & required_variables),
            "variableNamesMissing": sorted(required_variables - variable_names),
            "deploymentBranchPolicies": sorted(
                (item.get("type", "") + ":" + item.get("name", ""))
                for item in branches.get("branch_policies", []) if isinstance(item, dict)
            ),
            "requiredReviewerRuleCount": sum(
                1 for rule in environment.get("protection_rules", [])
                if isinstance(rule, dict) and rule.get("type") == "required_reviewers"
            ),
            "requiredReviewersConfigured": sum(
                len(rule.get("reviewers", [])) for rule in environment.get("protection_rules", [])
                if isinstance(rule, dict) and rule.get("type") == "required_reviewers"
                and isinstance(rule.get("reviewers", []), list)
            ),
            "preventSelfReview": any(
                rule.get("prevent_self_review") is True
                for rule in environment.get("protection_rules", [])
                if isinstance(rule, dict) and rule.get("type") == "required_reviewers"
            ),
        }
    permissions = repository.get("permissions", {})
    return {
        "authenticatedAs": login,
        "repositoryPermissions": {
            "admin": permissions.get("admin") is True,
            "push": permissions.get("push") is True,
            "maintain": permissions.get("maintain") is True,
        },
        "environments": output,
    }


def _synthetic_self_test() -> None:
    key = ec.generate_private_key(ec.SECP256R1())
    pem = key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption(),
    )
    record = public_key_record(pem, "phase11-ephemeral-self-test")
    trust = {"schemaVersion": 1, "keys": [record]}
    payload = {
        "schemaVersion": 1,
        "manifestKeyId": "phase11-ephemeral-self-test",
        "channel": "stable",
        "available": False,
    }
    envelope = ota_manifest.sign_payload(payload, record["keyId"], pem.decode("ascii"), trust)
    verified = ota_manifest.verify_envelope(envelope, trust)
    if verified != payload:
        raise PreflightError("Ephemeral OTA sign/verify self-test returned different payload data")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("dry-run", "self-test", "inspect-key", "github-audit"),
                        default="dry-run")
    parser.add_argument("--private-key", type=Path,
                        help="path to a protected local PEM file; key contents are never displayed")
    parser.add_argument("--key-id", help="public key identifier to validate")
    args = parser.parse_args(argv)
    try:
        if args.mode == "dry-run":
            trust = json.loads(TRUST_PATH.read_text(encoding="utf-8"))
            ids = trust_key_ids(trust)
            intent = json.loads((ROOT / "config/release-intent.json").read_text(encoding="utf-8"))
            print(f"OTA_TRUST_ROOT={'EMPTY_FAIL_CLOSED' if not ids else 'PINNED_KEYS_PRESENT'}")
            print(f"RELEASE_INTENT={'ENABLED' if intent.get('enabled') is True else 'DISABLED'}")
            print(f"PYTHON_RUNTIME={sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
            print(f"OPENSSL={'AVAILABLE' if shutil.which('openssl') else 'NOT_FOUND'}")
            print(f"GH_CLI={'AVAILABLE' if shutil.which('gh') else 'NOT_FOUND'}")
            print("MODE=dry-run; production key generation, GitHub writes, deployments, and Releases=NOT_PERFORMED")
        elif args.mode == "self-test":
            _synthetic_self_test()
            print("OTA_EPHEMERAL_SIGN_VERIFY=PASS; persistent key files=NONE")
        elif args.mode == "inspect-key":
            if args.private_key is None or not args.key_id:
                raise PreflightError("inspect-key requires --private-key and --key-id")
            _private_path_is_safe(args.private_key)
            key_bytes = args.private_key.read_bytes()
            key = parse_p256_pkcs8_private_key(key_bytes)
            record = public_key_record(key_bytes, args.key_id)
            ids = trust_key_ids(json.loads(TRUST_PATH.read_text(encoding="utf-8")))
            matches = [entry for entry in json.loads(TRUST_PATH.read_text(encoding="utf-8"))["keys"]
                       if entry.get("keyId") == args.key_id]
            if len(matches) > 1:
                raise PreflightError("App trust store contains duplicate key ids")
            if matches and matches[0].get("publicKeyX509Base64") != record["publicKeyX509Base64"]:
                raise PreflightError("Requested key id is already pinned to different public material")
            public_der = key.public_key().public_bytes(
                serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo,
            )
            print(f"PRIVATE_KEY_FORMAT=PKCS8_PEM; CURVE=P-256; private_contents=NOT_OUTPUT")
            print(f"PUBLIC_KEY_SHA256={hashlib.sha256(public_der).hexdigest()}")
            print(f"KEY_ID_STATUS={'PRESENT_MATCH' if matches else ('AVAILABLE' if args.key_id not in ids else 'INVALID')}")
            print(json.dumps(record, ensure_ascii=False, sort_keys=True))
        elif args.mode == "github-audit":
            result = audit_github_environment_names()
            print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
            print("GITHUB_AUDIT=READ_ONLY; secret values=NOT_REQUESTED")
    except (OSError, ValueError, json.JSONDecodeError, PreflightError) as exc:
        print(f"OTA_KEY_PREFLIGHT=BLOCKED: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
