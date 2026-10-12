# CarPaly Android version and delivery policy

`config/android-version-ledger.json` is the machine-readable allocation and delivery-policy ledger. Never edit an allocated name/code pair to reuse it, replace an already delivered APK, or lower/reuse a `versionCode`. The ledger pins `applicationId=com.shihab.diplay.hudtest` and the v1.1.4 Release certificate SHA-256 `4d26d1c861b41a2cee4515e31f5f5c7eb13b9dd06e7485aa1687bc1d2ac73d90`.

## Verified version history

- `v1.1.4`: public pre-release, `versionName=1.1.4`, `versionCode=36`.
- `v1.1.5`: historical public pre-release asset, `versionName=1.1.5`, `versionCode=37`; its original asset name is retained as historical data and is not a naming template.
- `versionCode=38`: observed in a local historical build and treated as the high-water mark even though that build is not a new user delivery.
- `v1.1.51`: `versionCode=39`, published as the formal GitHub Release; APK SHA-256 `222801dbc5e96b668c22a078da38d2b4ed184724c0b088c35d7d04c32752754a` matches the verified GitHub asset record. The hand-authored Release body conflicts with the formal channel label and is preserved pending manual correction.
- `v1.1.52`: `versionCode=40`, delivered as a local candidate APK recorded in the ledger; no public tag or Release exists. It remains a local candidate and makes no vehicle-fix claims.
- Continue `v1.1.53`, `v1.1.54`, and onward by immutable ledger allocations. The later `v1.1.6` allocation must use a `versionCode` above every prior observed or delivered code.

The ledger's `channel` records the allocation/development track; it is not the GitHub Release `prerelease` flag. For example, `v1.1.51` was allocated on the test track but GitHub currently marks its published Release as formal (`prerelease=false`). The GitHub Release API is the source of truth for the published channel, while the ledger preserves the immutable allocation history. Neither label means Debug build, Debug signer, or a separate Test/Upgrade-Test APK artifact. Every user-installable package is the Release variant signed by the fixed Release identity.

## Build and allocate

Run `python scripts/android_versioning.py check` before building or committing. It verifies Gradle metadata, the fixed package and signer, the Release-only artifact policy, and monotonic version history. Use `python scripts/android_versioning.py next-test` for the next numbered candidate or `final-release` for the later `1.1.6` line; allocation is refused until the current version has a verified Release APK SHA-256 recorded as delivered.

The only user APK name is `CarPaly-XingyueL-v{versionName}.apk`, for example `CarPaly-XingyueL-v1.1.51.apk`. Build it with `scripts/build-release-apk.ps1`; validate with `scripts/verify-release-apk.ps1 -ApkPath <path> -RequireCanonicalFileName -RecordDelivery`. The verifier checks package ID, increasing version metadata, v2 APK signature, fixed signer, Release/non-debuggable status, supported ABI, ZIP integrity, and exact match of packaged runtime authentication assets to the authorized local inputs. It refuses to replace existing artifacts and records the immutable APK SHA-256 only after verification.

CI may compile Debug variants and run Debug unit tests internally. CI Debug APKs are not uploaded as downloadable artifacts and are never user-installable deliverables. No standalone Debug, Test, or Upgrade-Test APK packaging task is supported.

Missing or unreadable original Release signing credentials means `BLOCKED`: do not build with the Android Debug key, generate a replacement keystore, alter the package ID, uninstall an older app, or clear user data. A successful source/Debug build does not establish a user-delivery APK or prove that an in-place upgrade has been tested on a device.
