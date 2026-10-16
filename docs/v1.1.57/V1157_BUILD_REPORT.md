# V1.1.57 candidate build status

## Current result

`BLOCKED_BY_SIGNER_POLICY` — no V1.1.57 APK was built or signed in this worktree. No Debug APK is being presented as a deliverable.

## Verified latest installed-package evidence

The existing local V1.1.56 artifact was read-only verified from the main workspace:

- File: `CarPaly-XingyueL-v1.1.56.apk`
- Size: 17,034,933 bytes
- SHA-256: `835bb4ac5a7d7d57442fa2b949b8500a349cd0fb7911a6210e4e2a1d0ad8b99e`
- Package / version: `com.shihab.diplay.hudtest`, 1.1.56 / versionCode 44
- `debuggable`: false
- `apksigner`: valid v2 signature
- Signer certificate SHA-256: `d9b329525fc1ef21c365fab72c10367527cc038297c4f30eaa22b2207429139e`

The artifact was not modified.

## Blocking policy conflict

The supplied current `AGENTS.md` requires future user-installable APKs to use the v1.1.4 signer `4d26d1c861b41a2cee4515e31f5f5c7eb13b9dd06e7485aa1687bc1d2ac73d90`. The merged V1.1.56 build configuration and version ledger use signer `d9b329525fc1ef21c365fab72c10367527cc038297c4f30eaa22b2207429139e`, which is also the signer verified on the existing V1.1.56 APK. No signing-lineage proof authorizing a transition from d9 to 4d is present. Android in-place update compatibility therefore cannot be claimed for a 4d-signed V1.1.57 over the verified d9-signed V1.1.56.

The versioning script is pinned to 4d while the merged active ledger/build configuration says d9. The strict version allocation check must fail closed until the signer epoch and upgrade policy are reconciled. This report does not alter either fixed certificate to make the check pass.

`ANDROID_KEYSTORE_PATH`, `ANDROID_KEYSTORE_PASSWORD`, `ANDROID_KEY_ALIAS`, and `ANDROID_KEY_PASSWORD` were not present in this process environment. No password was guessed, no DPAPI data was decrypted, and no signing credential was accessed.

## Build outcome

- V1.1.57 version allocation: `BLOCKED`; no versionName/versionCode was changed.
- Release signing preflight: `NOT_RUN`.
- Release build: `NOT_RUN`.
- Output APK: `NOT_CREATED`.
- Upgrade compatibility from V1.1.56: `BLOCKED_BY_SIGNER_POLICY`.
- Real vehicle behavior: `NOT_TESTED`.

To proceed safely, reconcile the intended signer policy and Android upgrade path with evidence for any signing lineage. Keep the V1.1.56 APK and its data intact; do not uninstall or clear data to work around the conflict.
