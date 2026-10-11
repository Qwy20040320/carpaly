# CarPaly permanent Release signing policy

Every user-installable APK, whether an early candidate or a later stable version, must be built from the Android `release` variant and signed by the original v1.1.4 Release key. The pinned certificate SHA-256 is:

`4d26d1c861b41a2cee4515e31f5f5c7eb13b9dd06e7485aa1687bc1d2ac73d90`

The package ID must remain `com.shihab.diplay.hudtest`. Future APK filenames must be exactly `CarPaly-XingyueL-v{versionName}.apk` (for example `CarPaly-XingyueL-v1.1.51.apk`). Do not create separate Debug/Test/Upgrade-Test user APKs, change package identity, replace the original keystore, overwrite a previously delivered artifact, or use uninstall/data clearing to work around an upgrade failure. Preserve existing historical Release records and APKs unchanged.

The signing certificate is public; the private key, PKCS12/JKS keystore, key alias, store password, and key password are not. APK SHA-256 identifies one build and may differ between builds; the signing certificate and private key must remain fixed for Android in-place upgrade compatibility. v2/v3 APK signing validates file integrity but does not replace the same-signer requirement.

Release builds require `ANDROID_KEYSTORE_PATH`, `ANDROID_KEYSTORE_PASSWORD`, `ANDROID_KEY_ALIAS`, and `ANDROID_KEY_PASSWORD`. `:mobile:preReleaseBuild` depends on `verifyCarPalyReleaseSigning`, which loads the PKCS12 keystore, verifies the alias and key password, and compares the certificate to the fixed v1.1.4 fingerprint. The Release verifier checks the final APK signer against the same fingerprint. Missing or mismatched credentials fail closed; there is no Android Debug signer fallback and no automatic keystore generation. If the original credentials cannot be recovered in their authorized context, report `BLOCKED` and do not create an APK.

Use `scripts/build-release-apk.ps1` to build a user deliverable. It invokes `:mobile:assembleRelease`, requires the authorized external authentication assets and original signing inputs, verifies package/version/signature/runtime assets/ABI/ZIP integrity, refuses to overwrite existing outputs, and records the APK SHA-256 only after the final canonical filename is verified. The report does not claim installation, upgrade, or vehicle behavior unless separately tested.

The local `.private/release-signing` copy is not a usable credential source unless the original authorized Windows protection context can decrypt it. Do not brute-force it, copy it to another account, or use another project's key. Restore the original password in the authorized context or enter it locally through a secure credential mechanism; never paste it into chat, a command literal, source, or logs.

CI may compile Debug variants for internal checks, but it must not upload Debug APKs as downloadable workflow artifacts. The public GitHub workflow does not publish on tag push. Publishing remains a separate, explicit manual action; do not create version tags or Releases automatically. The public `mfi-public-release` environment has no required-reviewer rule, so it must not be used as a private signed-APK delivery channel.

## Required gates

- `SIGNING_CERTIFICATE_MATCH`: the APK and loaded keystore match the pinned v1.1.4 certificate.
- `PACKAGE_NAME_MATCH`: the application ID remains `com.shihab.diplay.hudtest` with no suffix.
- `VERSION_CODE_INCREMENT`: the reserved package version is greater than all observed prior versions.
- `RELEASE_SIGNED_APK`: only a non-debuggable Release variant verified by `apksigner` qualifies as a user deliverable.
- `SENSITIVE_FILE_SCAN`: no keystore, password, or unrelated credential enters source, APK, logs, or artifacts.
- `USER_DATA_PRESERVATION`: report `NOT_TESTED` unless a permitted device completed a real `adb install -r` and verified preferences afterward.
