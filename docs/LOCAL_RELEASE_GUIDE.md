# Windows local Release guide

Run from a clean CarPaly worktree with the approved Android SDK, JDK, Python 3, Git and (for GitHub modes) `gh` installed. The tool never prints signing values. Do not store secrets in command history, repository files or logs.

```powershell
./build-release.ps1 -Status
./build-release.ps1 -CheckOnly
./build-release.ps1
./build-release.ps1 -SkipTests
./build-release.ps1 -OutputDir D:\APP\CarPaly\artifacts\release\vX.Y.Z
./build-release.ps1 -PrepareGitHub
./build-release.ps1 -PrepareDraft
./build-release.ps1 -FullPrepare
```

`-Status` is read-only. `-CheckOnly` must not produce an APK. Default mode requires a clean main checkout, an eligible ledger version, latest verified source ancestry, local authorized signer and runtime authentication pair, then runs tests, builds Release, verifies the APK and writes checksum/build notes without overwriting existing files. `-SkipTests` is explicitly non-release-ready and may only write a private ignored candidate; it never upgrades that output to a deliverable. `-OutputDir`, `-AndroidSdkPath`, `-PythonExecutable`, and `-VerboseLog` configure paths/diagnostics; verbose logs are redacted and kept under ignored `.private/`.

`-PrepareGitHub` stages explicit reviewed paths only, refuses a pre-existing staged index or private/binary paths, runs local checks, scans the public tree and Gitleaks, makes a normal commit/push, opens or reuses a PR and waits for checks on the exact head SHA. High-risk release/signing/Gradle/workflow changes remain Draft for human review. Low-risk auto-merge is only requested through GitHub's native protected Auto-merge after live policy/CI proof; it is blocked if the repository setting or policy is unavailable. This script does not enable repository settings, approve PRs, or bypass branch rules.

`-PrepareDraft` is verification-only. It requires the exact clean main commit, enabled same-commit release intent, successful CI, a matching published-source baseline, a verified local APK/checksum and an already-existing tag plus metadata-only Draft created by the authenticated GitHub publisher. It never creates/moves tags or Releases, edits Release notes, uploads assets, publishes, or turns on OTA. An APK with extractable identity material remains withheld from all public assets.

The current ledger is not Release eligible: local v1.1.52/code 40 is below the public code 44 high-water mark and is not descended from the latest verified release source commit. Local signer inputs are also unavailable in this environment. A failed preflight is expected and must not be bypassed.
