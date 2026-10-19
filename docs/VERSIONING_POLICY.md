# CarPaly Android version and delivery policy

`config/android-version-ledger.json` records immutable allocations, historical deliveries, source provenance, and signer epochs. Never reuse a version name/code, lower the high-water mark, replace a delivered APK, or retarget an existing tag. The package ID remains `com.shihab.diplay.hudtest`.

## Verified release and candidate records

| Version | Code | GitHub/source status | APK SHA-256 | Signer SHA-256 |
| --- | ---: | --- | --- | --- |
| v1.1.4 | 36 | historical public Release | historical | `4d26d1c861b41a2cee4515e31f5f5c7eb13b9dd06e7485aa1687bc1d2ac73d90` |
| v1.1.5 | 37 | historical public pre-release | historical | `4d26d1c861b41a2cee4515e31f5f5c7eb13b9dd06e7485aa1687bc1d2ac73d90` |
| v1.1.51 | 39 | recorded delivery | `222801dbc5e96b668c22a078da38d2b4ed184724c0b088c35d7d04c32752754a` | `4d26d1c861b41a2cee4515e31f5f5c7eb13b9dd06e7485aa1687bc1d2ac73d90` |
| v1.1.52 | 40 | GitHub Release exists; notes conflict and APK proof is not verified | `f5bea98180dadad4fecab77031f7373dc423b59c420bc9b085372b524c7e8c64` | `4d26d1c861b41a2cee4515e31f5f5c7eb13b9dd06e7485aa1687bc1d2ac73d90` |
| v1.1.53 | 41 | public Release; source/tag metadata is partial | `01212c62442b80f61d9fb9238f868d4f476bf460ededabb99ee038367dc9ed27` | `d9b329525fc1ef21c365fab72c10367527cc038297c4f30eaa22b2207429139e` |
| v1.1.54 | 42 | public Release; tag and release source record match `e3eca1dc5145cd293815d8f176d5c3812169271a` | `f244fff2765881b7f7a1b66b1ed44202ca3356730e11636b210b5267da514d3c` | `d9b329525fc1ef21c365fab72c10367527cc038297c4f30eaa22b2207429139e` |
| v1.1.55 | 43 | no verified Tag/Release; `SOURCE_UNVERIFIED` | `3e62340c45b576a5e83638c4b9e152b86ce78b650a48fc65bedff61e37ed23e1` | `d9b329525fc1ef21c365fab72c10367527cc038297c4f30eaa22b2207429139e` |
| v1.1.56 | 44 | public Release; tag and build report identify `6b206c9e6944255a159424522017dca984423e67` | `835bb4ac5a7d7d57442fa2b949b8500a349cd0fb7911a6210e4e2a1d0ad8b99e` | `d9b329525fc1ef21c365fab72c10367527cc038297c4f30eaa22b2207429139e` |
| v1.1.57 | 45 | local candidate; source reproducibility against the integrated commit is not established | `b0d1ffa688910752713eb96ab20f7c2c3c3a09afd52cd97f1178cbc0d515ace2` | `d9b329525fc1ef21c365fab72c10367527cc038297c4f30eaa22b2207429139e` |
| v1.1.58 | 46 | reserved local candidate; no GitHub tag or Release; APK not built | not built | `d9b329525fc1ef21c365fab72c10367527cc038297c4f30eaa22b2207429139e` |

Version code 38 was observed in a local historical build and must not be reused. The current reserved high-water mark is 46. v1.1.55 remains source-unverified even though a local APK record exists; do not infer its source from its version label. Do not fabricate or retarget the v1.1.53 historical tag mapping.

The planned label `v1.1.6` is not currently allocated or released. Any future allocation must use the canonical user APK filename `CarPaly-XingyueL-v{versionName}.apk`, remain above the full version-code high-water mark, and pass the release gates; the label alone does not assert a release.

## Signing epochs and upgrade boundary

Codes 36–40 use signer `4d26d1c861b41a2cee4515e31f5f5c7eb13b9dd06e7485aa1687bc1d2ac73d90`. Code 41 onward uses signer `d9b329525fc1ef21c365fab72c10367527cc038297c4f30eaa22b2207429139e`. No Android signing lineage between those certificates is verified: code 40 to 41 cannot be claimed as an in-place update. Codes 42 to 46 have same-signer/increasing-code prerequisites within the d9 epoch; actual device installation and data preservation still require device evidence.

The ledger's `channel` is the development/allocation track, not the GitHub Release `prerelease` flag or Android build type. A `test` allocation is still a Release APK, not a Debug APK.

## Validate, allocate, and deliver

Run `python scripts/android_versioning.py check` before a Release build. It validates Gradle metadata, package ID, the immutable ledger, epoch mapping, signer fields, allocation, and full observed high-water mark. PR/Push CI may run `check-ci` for consistency, but that does not authorize a signed Release build. Allocators must not reuse any name/code pair or reduce the high-water mark.

Use the root `build-release.ps1` orchestrator for preflight, and `scripts/build-release-apk.ps1` plus `scripts/verify-release-apk.ps1` for build and verification. The verifier checks version-specific signer, package, version, Release/non-debuggable state, APK signature, ABI, ZIP integrity, and the authorized runtime-authentication pair. It records a hash only after successful validation and does not overwrite an existing artifact. A linked worktree candidate is copied, not moved, to the primary checkout's ignored `artifacts/v{versionName}` directory by `scripts/artifact_delivery.py`.

Missing or unreadable signer inputs means `BLOCKED_BY_SIGNING`; never use Debug signing, generate a replacement key, change application ID, uninstall an older app, or clear user data. A successful build does not prove source reproducibility, upgrade installation, or vehicle behavior.

## Publishing boundaries

The authenticated main-branch publisher is gated by complete CI, source and ledger checks, a signer preflight, no pre-existing tag/Release, and an enabled same-commit `config/release-intent.json`. The v1.1.58 candidate leaves release intent disabled. Draft-only automation must remain idempotent and must never publish or attach an APK automatically. The local system does not upload APKs, alter OTA state, change production GitHub settings, or modify historical Releases. APKs containing extractable authentication identity material are not public distribution assets absent explicit authorization.

See [Release signing policy](RELEASE_SIGNING_POLICY.md), [local release guide](LOCAL_RELEASE_GUIDE.md), and [automation architecture](RELEASE_AUTOMATION_ARCHITECTURE.md).
