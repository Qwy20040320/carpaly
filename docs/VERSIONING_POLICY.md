# CarPaly Android version and delivery policy

`config/android-version-ledger.json` is the machine-readable source for immutable allocations, historic deliveries and signing epochs. Never reuse a `versionName`/`versionCode`, lower the high-water mark, replace a delivered APK, or retarget an existing tag.

## Version and signer history

The package id is permanently `com.shihab.diplay.hudtest`. The signer is selected by `versionCode` from the ledger's contiguous, non-overlapping signing epochs:

| versionCode | SHA-256 certificate fingerprint | Status |
| ---: | --- | --- |
| 36–40 | `4d26d1c861b41a2cee4515e31f5f5c7eb13b9dd06e7485aa1687bc1d2ac73d90` | Historical identity |
| 41+ | `d9b329525fc1ef21c365fab72c10367527cc038297c4f30eaa22b2207429139e` | Active identity, based on verified v1.1.53, v1.1.54 and v1.1.56 APKs |

The historical binaries are immutable. A certificate change means ordinary Android in-place upgrade is not established unless signing lineage support or a real target-device upgrade test proves it. Record `NOT_TESTED` otherwise. v1.1.55/code 43 has no verified source tag and remains `SOURCE_UNVERIFIED`.

The ledger records v1.1.52/code 40 as a delivered allocation. GitHub currently reports a published v1.1.52 Release, but its formal/pre-release metadata conflicts and its APK lacks a matching verification sidecar; do not rewrite that historical Release or treat the metadata conflict as verified evidence. The complete public high-water mark is 44 because v1.1.56/code 44 is published. The current Gradle assignment is therefore intentionally stale for a new delivery. Do not build or allocate a user APK from it; first reconcile source history and reserve a version strictly above 44 through a reviewed change.

The previously planned stable endpoint `v1.1.6` remains a future allocation, not a current build target; it must also use a `versionCode` above the verified high-water mark and the active signer epoch.

## Validate and allocate

Run `python scripts/android_versioning.py check` before a Release build or allocation. It checks Gradle metadata, the application id, signing epoch, artifact policy and complete version high-water mark. CI may use `check-ci` for branch consistency only; that does not authorize a Release build. Use `next-test` or `final-release` only after the current allocation has a verified immutable APK SHA-256 record. Do not change an already-delivered record to make a build pass.

The sole user-installable APK name is `CarPaly-XingyueL-v{versionName}.apk`. Build with `scripts/build-release-apk.ps1` through the root `build-release.ps1` orchestrator, then validate with `scripts/verify-release-apk.ps1`. The verifier checks the pinned epoch, package, monotonic version, Release/non-debuggable metadata, v2 signature, ABI, ZIP integrity and the exact local authentication asset pair. Existing output files are never overwritten.

## Delivery boundaries

All delivered APKs must be signed Release variants. Debug compilation is allowed only inside CI and Debug APKs are not deliverables. Missing original signer credentials means `BLOCKED_BY_SIGNING`; never substitute a Debug/new key, change the application id, uninstall an older app, or clear user data.

The local orchestrator can build and verify, synchronize reviewed source changes to a feature branch, and inspect a metadata-only Draft produced by the protected publisher. It cannot create or move tags, create or publish Releases, upload APKs, change OTA state or modify production GitHub settings. The checked-in release intent stays disabled unless separately reviewed on main. APKs containing extractable authentication identity material are never uploaded by this local system to a public Release, Actions Artifact, Pages or OTA.

See [Release signing policy](RELEASE_SIGNING_POLICY.md), [local release guide](LOCAL_RELEASE_GUIDE.md), and [automation architecture](RELEASE_AUTOMATION_ARCHITECTURE.md).
