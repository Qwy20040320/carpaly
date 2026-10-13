# CarPaly OTA Production-Key Runbook

## Current state

This is a preparation guide, not permission to create or configure the production identity. At the Phase 11 audit, the app trust store at `common/src/main/res/raw/ota_manifest_public_keys.json` is empty, `config/ota-publisher-policy.json` has `productionEnabled=false` and `environmentConfigurationReviewed=false`, and the `ota-manifest-publisher` GitHub Environment has no signing Secret or key-id Variable. No production OTA key was generated in this phase.

The supported format is one unencrypted PKCS#8 PEM ECDSA key on `secp256r1`/P-256 (`BEGIN PRIVATE KEY`), X.509 SubjectPublicKeyInfo DER encoded as Base64 for the app, and `SHA256withECDSA-P256` signatures. SEC1 `EC PRIVATE KEY`, encrypted PEM, other curves, unknown key IDs, and an empty app trust store must fail closed.

## Offline preparation commands

Use a dedicated, access-controlled offline workstation or encrypted volume. Do not place the private file in the repository, a synced folder, a ticket, chat, shell transcript, or CI artifact. The generator itself is intentionally not included in the Phase 11 local utility. Production generation and upload require separate approval.

After that approval, an operator may create the key on the protected host using OpenSSL and restrictive filesystem ACLs. `openssl genpkey -algorithm EC -pkeyopt ec_paramgen_curve:prime256v1 -out <protected-path>` emits the required unencrypted PKCS#8 PEM. Treat the output as plaintext private-key material despite the encrypted disk. Never add `-text`, print the file, or paste it into a command argument.

The included read-only Windows preflight supports:

```powershell
.\scripts\ota-key-preflight.ps1 -Mode dry-run
.\scripts\ota-key-preflight.ps1 -Mode self-test
.\scripts\ota-key-preflight.ps1 -Mode inspect-key -PrivateKeyPath 'X:\protected\ota-signing.pem' -KeyId 'carpaly-ota-<approved-id>'
.\scripts\ota-key-preflight.ps1 -Mode github-audit
```

`inspect-key` reads a path, verifies PKCS#8/P-256, prints only the public SPKI record and public-key SHA-256, and checks Git tracking/ignore status and key-ID collisions. It does not write a public trust record, generate keys, upload Secrets, or mutate GitHub. `self-test` creates only an in-memory ephemeral key and leaves no key file. Use `-PythonExe` to select the intended local Python interpreter if the `python` command is unavailable.

## Approved production provisioning sequence

1. Record the production key owner, purpose, key ID, public-key fingerprint, creation date, recovery custodian, and authorization outside the repository without storing private material in the record.
2. Generate a unique non-secret key ID matching `[A-Za-z0-9._-]{1,64}`. Do not reuse an ID for different public bytes.
3. Export the public record with `scripts/export_ota_public_key.py` only after explicit key-creation approval. Review the public curve, SPKI fingerprint, key ID, and exact generated diff independently.
4. Add the reviewed public record to the Android raw trust store in a later, versioned app build; set `status` to `active`. Do not put the private key or a test key in the app.
5. Build and verify that app with the immutable Android Release signer and a strictly greater `versionCode`. Install it through the user-approved trusted channel before enabling production feeds.
6. Only after a second person verifies the app-pinned key and GitHub Environment controls, configure `OTA_MANIFEST_SIGNING_PRIVATE_KEY_PEM` as a Secret and `OTA_MANIFEST_SIGNING_KEY_ID` as a Variable in `ota-manifest-publisher`. Configure the Environment to allow only `main`, require an eligible reviewer, and prevent self-review.
7. Check only Secret/Variable names and Environment policy after provisioning. GitHub does not offer a safe read-back of Secret plaintext. Validate key pairing by signing a non-production test fixture in the protected publishing job and verifying it using the app-pinned public key; do not emit the signature input containing any credential.
8. Keep `productionEnabled=false` and the empty feed in place until the trusted bootstrap APK is installed and all separate production gates are approved.

## Storage, backup, and access

Keep one primary encrypted offline copy and one independently protected recovery copy under two-person access control. Test that the recovery copy can be read in its authorized recovery context without exporting the key to another device. Restrict creation, read, and deletion access; record every access. GitHub Environment Secret is a deployment copy, not a backup. Rotate if a backup loses custody. No production key should be placed on the same workstation as public source checkout after provisioning.

The phase script has no production mutation mode. Any future GitHub Secret write, production key creation, signer preflight, OTA signing, Pages deployment, tag, or Release is a separately approved operation with a separate plan and rollback.
