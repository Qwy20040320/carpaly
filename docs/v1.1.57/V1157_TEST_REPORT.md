# V1.1.57 local test report

## Scope

Validation ran in the isolated `codex/carpaly-v1.1.57` worktree at source base
`0d5617d017bb0739e1ca9cb3ee48fa2e105fed30`, with the local merge of
`v1.1.56` (`6b206c9e6944255a159424522017dca984423e67`) still in progress.
The merge has no unresolved index entries, but remains uncommitted because the
permanent signer policy and the delivered-version ledger disagree. The primary
worktree was not edited.

## Android Gradle CI

The complete `AGENTS.md` command was run after the diagnostic privacy changes:

```text
:shared:testDebugUnitTest :common:testDebugUnitTest :home:testDebugUnitTest
:mobile:lintDebug :home:lintDebug :maphost:lintDebug
:mobile:assembleDebug :home:assembleDebug :maphost:assembleDebug
```

Result: `BUILD SUCCESSFUL`; 2,125 tests, 0 failures, 0 errors, 3 skipped.
All three Debug lint and internal Debug assemble tasks succeeded. These Debug
outputs are CI-only and are not user-installable deliverables.

## Python and release-gate checks

- Python discovery: 235 tests; 221 passed, 1 failed, 2 errors, 11 skipped.
- The 3 failing test cases are confined to the fixed-signer policy conflict: two
  repository ledger checks stop at the mismatch between the permanent 4d
  signer rule and the merged d9 ledger, and one allocator test consequently
  receives that mismatch before its expected missing-SHA diagnostic. No
  assertion or signer pin was weakened.
- `scripts/android_versioning.py check`: fails closed with
  `Version ledger does not enforce the permanent Release APK delivery policy`.
- `scripts/check_workflow_action_pins.py`: PASS (36 immutable pins across 3
  workflows).
- `scripts/check_pages_workflow.py`: PASS; static Pages has no production
  secret scope and the production feed policy is verify/preserve-or-block.
- `scripts/check_release_automation.py`: PASS; production release requires
  full CI, reviewed main intent and signer pin before secrets; ordinary PRs do
  not receive production secrets; assets remain withheld by the current
  metadata-only publisher.
- `scripts/validate_release_metadata.py`: PASS for the existing 1.1.56/code 44
  candidate; V1.1.57 was not allocated.
- `scripts/check_project_docs.py`: FAIL because the signing policy disagrees
  with the ledger. The documentation's canonical APK naming and `v1.1.6`
  version-stream requirements were added; the signer mismatch is the sole
  remaining project-doc check failure.
- `scripts/check_public_tree.py`: PASS.

## Secret and workflow tooling

- Gitleaks staged scan: PASS, no leaks found.
- Gitleaks source scan: PASS for `common/src`, `shared/src`, `automotive/src`,
  `mobile/src`, `samples/home/src`, `samples/maphost/src`, `scripts`, `config`,
  `docs`, and `.github`.
- A whole-worktree Gitleaks scan reported 8 generic-key candidates, all in
  ignored generated Gradle cache files under `common/build` and `mobile/build`;
  none are tracked or staged. No candidate was read as a credential or copied
  into source.
- `actionlint` and Bash are not installed in this Windows environment. Linux
  Bash integration tests and `actionlint`: `NOT_RUN` (WSL has no configured
  Linux distribution). Hosted GitHub Actions: `NOT_RUN`.
- `git diff --cached --check` and `git diff --check`: PASS. Git reports only
  line-ending normalization warnings for the newly edited Markdown reports.

## Release and vehicle status

- Release signer preflight and Release APK build: `NOT_RUN`; blocked by the
  unresolved 4d/d9 signing policy and absence of approved local credentials.
- `release-intent.enabled=false`. No V1.1.57 version allocation, tag, Release,
  OTA feed, PR, or APK was created.
- Decoder candidate-selection/cleanup tests pass; actual OPUS decode and
  audible speaker output remain unverified.
- Music auto-pause remains a historical, not-reproduced report. Wired USB/
  iAP2/MFi session, navigation speech, OEM status bar, touch, steering input,
  HUD, cluster, and installation behavior for this revision are
  `NOT_TESTED` on a real vehicle.

## Verification addendum — 2026-10-16

After adding protocol-level audio classification diagnostics, the complete
`AGENTS.md` Gradle command was rerun in this worktree and completed successfully:
2,127 tests, 0 failures, 0 errors, 3 skipped; all requested lint and internal
Debug assemble tasks passed. The two added classifier tests cover explicit
`media`, `navigation`, `speechRecognition`, `telephony`, and `system` labels,
and keep missing, ambiguous (`default`, `alert`, `compatibility`), and unknown
labels classified as `UNKNOWN`.

This classification is diagnostic metadata only. Existing playback routing is
unchanged for compatibility; therefore it does not prove OEM volume-group
selection or a correct real-vehicle route. A focused Gitleaks scan of
`shared/src` and `scripts/check_public_tree.py` both passed after this change.
The Python suite was rerun after the Kotlin-only change: 235 tests, 221 passed,
1 failed, 2 errors, and 11 skipped. The three failing test cases remain the
unresolved fixed-signer/ledger policy conflict described above. `actionlint`,
Bash integration tests, hosted Actions, Release signing, and vehicle tests were
not run. No Release APK, tag, PR, or publication was created.
