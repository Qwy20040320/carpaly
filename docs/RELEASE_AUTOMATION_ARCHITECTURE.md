# Local Release system architecture

```text
reviewed source + immutable version ledger
        │
        ├── CheckOnly: SDK/JDK/Git/Python/Signer/Auth/Source/Version checks (no APK)
        ├── Build: tests → Release signer preflight → Release APK → metadata/signature/hash validation
        ├── PrepareGitHub: explicit safe paths → scans/tests → commit → normal push → PR → exact-head CI
        └── PrepareDraft: read-only verification of the protected publisher's existing zero-asset Draft
```

`build-release.ps1` is the Windows orchestration layer. `ReleaseSystem.Core.psm1` contains signer-epoch selection, redaction and private local-state helpers. `scripts/android_versioning.py` and `config/android-version-ledger.json` define version/source signing facts. `scripts/build-release-apk.ps1` and `scripts/verify-release-apk.ps1` perform the Release build boundary and APK verification. `scripts/release_automation.py` is a pure fail-closed policy evaluator. `.github/scripts/prepare-release-draft.sh` and the protected Android publisher remain authoritative for tag/Draft creation.

No local operation uploads an APK or changes repository/Environment settings. No ordinary PR job reads production secrets. Release-intent is disabled by default; automatic publishing is only possible through the existing protected main workflow after its complete reviewed gates. The current source baseline/high-water and unavailable local signer intentionally prevent a Release build.

The public APK currently contains extractable authentication identity assets. Source disclosure approval does not imply authorization to redistribute those assets. Therefore public APK attachment/upload is forbidden by this system; only sanitized public documentation and metadata-only drafts are permitted until distribution rights and an acceptable design are resolved.
