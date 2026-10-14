# Android version and delivery policy

`config/android-version-ledger.json` is the machine-readable allocation and signing-epoch ledger. Never edit an allocated name/code pair to reuse it, replace an already delivered APK, or lower/reuse a `versionCode`. The application ID remains `com.shihab.diplay.hudtest`.

## Verified version history

- `v1.1.4`: public pre-release, `versionName=1.1.4`, `versionCode=36`.
- `v1.1.5`: historical public pre-release, `versionName=1.1.5`, `versionCode=37`; its original asset name is retained as historical data.
- `versionCode=38`: observed in a local historical build and treated as the high-water mark.
- `v1.1.51`: `versionCode=39`, published GitHub Release; APK SHA-256 `222801dbc5e96b668c22a078da38d2b4ed184724c0b088c35d7d04c32752754a`, signed by the legacy certificate.
- `v1.1.52`: `versionCode=40`, delivered as a local candidate; APK SHA-256 `f5bea98180dadad4fecab77031f7373dc423b59c420bc9b085372b524c7e8c64`, signed by the legacy certificate. Keep this APK unchanged.
- `v1.1.53`: reserved as `versionCode=41`, using the explicitly authorized new signing epoch. This is **fresh-install-only** and cannot update a v1.1.52 or earlier installation in place.
- Future allocations follow the immutable ledger and complete code high-water mark. The later `v1.1.6` allocation must use a version code above every prior observed or delivered code.

## Signing epochs and installation compatibility

The original Release certificate `4d26d1c861b41a2cee4515e31f5f5c7eb13b9dd06e7485aa1687bc1d2ac73d90` remains the immutable signer record for codes 36–40. Starting at code 41, the new certificate `d9b329525fc1ef21c365fab72c10367527cc038297c4f30eaa22b2207429139e` is used. Android package updates require a compatible signer; Android will reject an old-signer install as an update to the new-signer app or vice versa. A fresh install can lose application-local settings and pairing data. Do not uninstall or clear data unless the user explicitly accepts that consequence and has decided what must be backed up.

Each allocation records its certificate and installation policy. The ledger's `channel` describes the development track, not the APK build type, signature identity, GitHub `prerelease` flag, or vehicle validation. Use only `CarPaly-XingyueL-v{versionName}.apk` for installable packages. Every package is built as Release; internal CI may compile Debug, but must not upload or deliver Debug APKs.

Run `python scripts/android_versioning.py check` before building or committing. It verifies Gradle metadata, the package and active signer epoch, Release-only delivery policy, immutable allocations and monotonic version history. `python scripts/android_versioning.py next-test` allocates a new candidate only after the current candidate has a verified APK SHA-256 recorded as delivered; `final-release` allocates the planned `1.1.6` line under the then-current signer epoch.

The user APK build entry point is `scripts/build-release-apk.ps1`; it writes to a version-specific directory under `artifacts/`, validates the output with the Android SDK and refuses collisions. A successful source/Debug build does not establish an installable signed APK, update compatibility, or real vehicle behavior. New-signer candidates cannot replace existing legacy-signed installs without a separate data-preserving migration mechanism; none is currently implemented.
