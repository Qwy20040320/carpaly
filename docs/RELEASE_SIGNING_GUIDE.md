# Android Release signing guide

## Identity selection

The immutable `config/android-version-ledger.json` signing epochs map version codes 36–40 to the historical certificate and 41+ to the currently verified certificate. Gradle, `android_versioning.py`, the APK verifier and the build scripts all select the identity by `versionCode`. The active ledger certificate is based on inspected historical APKs; only possession of the corresponding private key plus an actual successful signature operation proves signing capability.

The local build requires `ANDROID_KEYSTORE_PATH`, `ANDROID_KEYSTORE_PASSWORD`, `ANDROID_KEY_ALIAS`, and `ANDROID_KEY_PASSWORD`, plus the separately authorized runtime authentication inputs. Read values only through an approved secret manager/environment injection. Do not echo, serialize, export, commit or upload them. `RELEASE_SIGNING_CERT_SHA256` is a public fingerprint pin, not a credential.

Before Release assembly, `:mobile:verifyCarPalyReleaseSigning` opens the configured PKCS#12, validates the alias/private-key entry and verifies the public certificate digest against the version epoch. Missing or mismatched values fail closed; there is no Debug fallback. After assembly, `scripts/verify-release-apk.ps1` validates APK signer, package, code/name, non-debuggable manifest, ABI, archive integrity and local authentication-resource pair.

## Safe operating sequence

1. Confirm the exact reviewed source commit and eligible ledger allocation.
2. Inject the existing authorized signer values into the isolated build process without putting them in command-line arguments.
3. Run `build-release.ps1 -CheckOnly`; inspect only status categories and public certificate fingerprint.
4. Run the full Release build and validate its report and SHA-256.
5. Keep the private key and MFi identity in their separate protected stores; never place either in APK reports, public source, Actions artifacts or GitHub Pages.

Current local signer credentials are not configured here, and the current version allocation is stale versus public code 44. This guide does not claim that an APK can presently be produced.
