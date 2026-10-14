# CarPaly Release signing policy

## Signing identity transition

The user explicitly authorized a new Android signing identity for CarPaly v1.1.53. This is a deliberate, non-backward-compatible signing epoch change:

- v1.1.4 through v1.1.52 retain the original certificate SHA-256 `4d26d1c861b41a2cee4515e31f5f5c7eb13b9dd06e7485aa1687bc1d2ac73d90`.
- v1.1.53 (versionCode 41) and later use the new candidate certificate SHA-256 `d9b329525fc1ef21c365fab72c10367527cc038297c4f30eaa22b2207429139e`.
- Android will reject an in-place update between these signer identities. The v1.1.53 candidate is **FRESH_INSTALL_REQUIRED** and cannot preserve installed v1.1.52 application data through normal APK update. Do not uninstall the existing app unless the user has separately decided how to preserve any needed data.
- The immutable per-version signer and installation policy are recorded in `config/android-version-ledger.json`. Never change historical APKs, signing identities, version allocations, or hashes to hide this transition.

The v1.1.53 private key and its DPAPI-protected password are local-only under the ignored `.private/release-signing-v1.1.53/` directory. They must not enter Git, logs, source archives, public Actions artifacts, or APK files. The public certificate fingerprint is not a secret. The private key needs an owner-controlled, encrypted offline backup before it is considered disaster-recoverable; the DPAPI password file only decrypts in the Windows account/profile that created it.

## Build and validation

Every user-installable APK must be built from the Android `release` variant, keep `applicationId=com.shihab.diplay.hudtest`, use the version-specific signer in the ledger, and use the canonical filename `CarPaly-XingyueL-v{versionName}.apk`. Missing or mismatched credentials fail closed; there is no Android Debug signer fallback. Never overwrite an existing delivered artifact.

Release builds require `ANDROID_KEYSTORE_PATH`, `ANDROID_KEYSTORE_PASSWORD`, `ANDROID_KEY_ALIAS`, and `ANDROID_KEY_PASSWORD`. `:mobile:preReleaseBuild` depends on `verifyCarPalyReleaseSigning`, which verifies the PKCS12 alias, password and active ledger fingerprint. The post-build verifier checks the actual APK signer, package/version metadata, non-debuggable Release state, ABI, ZIP integrity and exact runtime authentication-asset match. Use `scripts/build-release-apk.ps1`; it writes to a version-specific directory under `artifacts/`, refuses collisions, and records the APK hash only after validation. CI may compile Debug variants internally, but must not upload Debug APKs as downloadable artifacts.

The local candidate build also requires explicitly provided `DIPLAY_AUTH_ASSETS_DIR` with `offline-mfi/identity.pk8` and `offline-mfi/certificate.p7b`. These are separate from Android APK signing. This task does not publish them independently and does not authorize any GitHub upload.

The public `mfi-public-release` Environment still has the historical certificate pin unless an authorized maintainer changes it. Therefore cloud Release signing must fail closed until the Environment Variable `RELEASE_SIGNING_CERT_SHA256` and the protected keystore have been deliberately migrated and re-verified. Do not alter that Environment or trigger a production workflow as part of local candidate generation.

OTA remains disabled and its signed feed trust root remains independently controlled. Matching the Android APK signer does not provision an OTA manifest signing key or prove CarPlay/MFi authentication.

## Required gates

- `SIGNING_CERTIFICATE_MATCH`: the built APK signer equals the current version's signer epoch in the ledger.
- `PACKAGE_NAME_MATCH`: the application ID remains `com.shihab.diplay.hudtest`.
- `VERSION_CODE_INCREMENT`: the reserved version exceeds all observed previous codes.
- `RELEASE_SIGNED_APK`: only a non-debuggable Release APK with a verified signature qualifies.
- `FRESH_INSTALL_REQUIRED`: v1.1.53 cannot update v1.1.52 in place because the signer changed.
- `SENSITIVE_FILE_SCAN`: no keystore, password, MFi private key or unrelated credential enters Git, logs, source archives or external artifacts.
- `USER_DATA_PRESERVATION`: `NOT_TESTED` unless a permitted device verifies migration; signer change means normal Android update cannot preserve old app data.
