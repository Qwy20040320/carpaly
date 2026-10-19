# CarPaly Android Release signing policy

All user-installable APKs use the Android `release` variant, package ID `com.shihab.diplay.hudtest`, and canonical name `CarPaly-XingyueL-v{versionName}.apk`. The version ledger is authoritative for signer selection.

## Approved signer epochs (`signingEpochs`)

| Version-code range | Certificate SHA-256 | Upgrade boundary |
| --- | --- | --- |
| 36–40 | `4d26d1c861b41a2cee4515e31f5f5c7eb13b9dd06e7485aa1687bc1d2ac73d90` | Historical signer |
| 41+ | `d9b329525fc1ef21c365fab72c10367527cc038297c4f30eaa22b2207429139e` | Current signer epoch |

No Android signing lineage between the 4d and d9 certificates has been verified. A code 40 installation cannot be assumed to upgrade in place to code 41. Code 41 is recorded as a fresh-install boundary. Code 42 onward can meet same-signer and increasing-version prerequisites only when the installed package is already d9-signed. These are compatibility prerequisites, not proof of an actual device installation or data migration.

Never re-sign a historical APK, create a replacement key, modify a delivered APK, change the package identity, uninstall an existing install, or clear user data to work around a signer mismatch.

## Verification and credential handling

`scripts/android_versioning.py`, Gradle's `:mobile:verifyCarPalyReleaseSigning`, and `scripts/verify-release-apk.ps1` must resolve the expected certificate by the current `versionCode`. Missing, overlapping, malformed, or mismatched epoch entries fail closed. The ledger's current signer fields must agree with that epoch.

Local Release builds require the authorized Android signing inputs and runtime authentication assets. Do not put passwords, keystores, private keys, DPAPI files, or credential material in Git, command literals, logs, reports, or public Actions artifacts. Android APK signing and CarPlay/MFi authentication are separate systems. Preserve the existing authentication checks and assets; do not remove them or fabricate substitutes.

The local `build-release.ps1` orchestrator may run preflight and tests. `-CheckOnly` does not build. `-SkipTests` must remain a non-ready private candidate and cannot be promoted as a release. The lower-level `scripts/build-release-apk.ps1` validates the Release variant, version, signer, APK structure, runtime asset pair, and checksum before delivery. It must refuse to overwrite an existing artifact and use the centralized ignored `artifacts/v{versionName}` location from a linked worktree.

CI may compile Debug variants internally, but it must not upload Debug APKs as user-deliverable artifacts. Ordinary PR and push jobs must not map production signing Secrets. The protected publisher requires successful main CI and a same-commit reviewed release intent; this integration PR leaves `config/release-intent.json` disabled. No Tag, Release, APK upload, or OTA action is authorized by this change.

## Required gates

- `SIGNING_EPOCH_MATCH`: the keystore and resulting APK match the epoch selected by versionCode.
- `PACKAGE_NAME_MATCH`: application ID remains `com.shihab.diplay.hudtest`.
- `VERSION_CODE_INCREMENT`: unique allocation above the full observed high-water mark.
- `RELEASE_SIGNED_APK`: non-debuggable Release APK verified by `apksigner`.
- `SOURCE_PROVENANCE`: source commit and binary provenance are stated only when evidenced.
- `SENSITIVE_FILE_SCAN`: no keystore, password, authentication material, private diagnostic data, or APK enters public source.
- `VEHICLE_VALIDATION`: local build and simulations never count as real-vehicle validation.
