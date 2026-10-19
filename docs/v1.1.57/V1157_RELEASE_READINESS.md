# V1.1.57 release readiness

## Current result

`BLOCKED_BY_SIGNER_POLICY`. This is a local development candidate only. No
version tag, GitHub Release, OTA feed, APK, or vehicle installation was created
for V1.1.57.

## Source and merge state

- Candidate branch: `codex/carpaly-v1.1.57`.
- Candidate base and fetched `origin/main`: `0d5617d017bb0739e1ca9cb3ee48fa2e105fed30`.
- In-progress merge source: tag `v1.1.56` at
  `6b206c9e6944255a159424522017dca984423e67`; merge base is the V1.1.53
  commit `64703e7dced85b81963a85b8b3ff12a7efc56448`.
- The index has no unresolved Git entries. The merge message records prior
  conflict resolution in version-policy/test files, but a semantic signer
  policy conflict remains. The merge is intentionally left uncommitted.
- Critical V1.1.56 runtime files (settings/update UI, controller, media sink,
  logging, and mobile version configuration) match the `v1.1.56` tag in the
  merge index. The main-branch workflow files were not changed by this merge.
- Existing unstaged V1.1.57 source/test changes remain separate from the staged
  merge result. The primary worktree and its existing changes were not edited.

## Implemented and locally testable

- Existing OPUS decoder candidate fallback is retained. It tries the Android
  default decoder first, enumerates supported explicit candidates if needed,
  releases rejected instances, and records sanitized failure stage/class.
- Startup prerequisites and controller-stage changes remain observable without
  inventing a wired-confirmation event.
- A private iPhone `syslog_relay` capture was removed from routine wired startup;
  controller diagnostics now pass through redaction before logcat/callback
  delivery and do not include raw Throwable stack traces.
- Existing safe-area/inset and shared touch-transform behavior is retained.
  The reported OEM top strip still requires vehicle re-test.
- Steering, HUD, cluster, fuel, and climate remain permission/capability gated.

## Verification status

- Python publisher/site/OTA/version test discovery: 235 tests; 224 passed,
  3 failed, 11 skipped. The 3 failures are the unresolved fixed-signer versus
  ledger mismatch (two repository checks and one allocator error-priority
  expectation); they are not suppressed.
- The required AGENTS Gradle command completed successfully after the
  diagnostic privacy change: 2,125 tests, 0 failures/errors, 3 skipped; all
  requested Debug lint and internal assemble tasks passed.
- `scripts/android_versioning.py check`: fails closed on the same permanent
  delivery-policy mismatch.
- Action pin, Pages workflow, release automation, release metadata, and public
  tree checks passed. The version-policy artifact naming and `v1.1.6`
  progression documentation was completed. `scripts/check_project_docs.py`
  still fails closed only because the permanent signer pin differs from the
  ledger.
- Gitleaks staged and source-directory scans passed. The full worktree scan
  found 8 generic-key candidates only in ignored, untracked Gradle cache files
  under `common/build` and `mobile/build`; no source/config/doc/workflow match
  was found.
- `actionlint`, Linux Bash integration tests, and hosted GitHub Actions:
  `NOT_RUN`; actionlint/Bash are absent and WSL has no configured Linux
  distribution.
- Final `git diff --check` and `git diff --cached --check`: PASS.
- `release-intent.enabled=false`; no V1.1.57 allocation or release permission
  was enabled.

## Runtime and release evidence

- OPUS candidate-selection/cleanup code tests are not proof that OPUS decoded
  PCM or reached the car speakers. `OPUS_CODE_TESTED`; audible result remains
  `OPUS_AUDIBLE_PENDING`.
- The user-reported USB confirmation prompt is still not uniquely identified.
  The normal application USB connect action is not an app-owned modal. No
  contemporaneous runtime trace proves the reported event's identity or
  establishes a wired iAP2/MFi session.
- USB/wired CarPlay, audio output, navigation speech, automatic music pause,
  fullscreen/OEM status strip, touch behavior, steering-wheel input, HUD, and
  cluster behavior for this revision: `NOT_TESTED` on a real vehicle.
- No V1.1.57 Release APK exists. Signing preflight/build were not run because
  the signer policy is unresolved and no approved local credentials are
  available in the process context.
- No V1.1.57 PR or Release draft exists. The currently open PR #11 is for the
  separate local-release-orchestrator branch; it is not this candidate.

## Next safe action

Obtain an explicit, evidence-backed maintainer decision resolving the 4d/d9
signer conflict and upgrade path. Until then, keep this merge uncommitted, keep
the release intent disabled, and do not create or sign a user-installable APK.
