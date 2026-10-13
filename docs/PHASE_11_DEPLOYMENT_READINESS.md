# Phase 11 Deployment Readiness

This is a readiness record, not deployment approval. As of 2026-10-13, production release intent is disabled and no production OTA signing or Pages deployment has occurred.

| Gate | Status | Evidence / next requirement |
| --- | --- | --- |
| Local/remote branch baseline | PASS | Both at `000e50e1ca474484a8f3bda77532e212c28db0f7`; no drift after fetch. |
| PR #6 | OPEN / DRAFT | Previous four checks passed at baseline SHA; new Phase 11 diff still needs CI. |
| OTA Python crypto contract | PASS (local tests) | Full Python discovery: 210 tests, 197 passed and 13 Windows-only Bash integration skips; all executed tests passed. |
| Python ↔ Android signature compatibility | PASS (local tests) | The fixed public-only vector passed in Python and Android JCA; Android `UpdateManifestVerifierTest` was 11/11 with no skips. |
| Android CI command | PASS (local) | 2,057 unit tests: 2,054 passed, 3 skipped; all requested Lint and Debug assemble tasks succeeded. No Release APK was built. |
| App production trust root | BLOCKED / intentionally fail-closed | `keys` is empty; no production private key exists in this phase. |
| Production OTA key | NOT_CREATED | Separate approval and offline generation/storage review required. |
| OTA signer Environment | BLOCKED | Missing signing Secret/Variable and required-reviewer/self-review policy; new runtime guard checks it before signer access. |
| Release policy audit Environment | BLOCKED | Workflow's `RELEASE_POLICY_READ_TOKEN` absent. Prefer a repo-scoped, short-lived GitHub App token with read-only permissions for ruleset suite, PR and metadata evidence. |
| Existing candidate APK signer | PASS (local artifact only) | v1.1.52's v2 signature is valid and its certificate matches the fixed pin; this does not verify the remote Release Keystore Secret. |
| Cloud Android Release signer | NOT_TESTED | Secret values were not read and the separately authorized signer-only preflight was not run. |
| Pages configuration | CONFIGURED | API says GitHub Actions source; `github-pages` is main-only and has no signing Secrets. |
| Pages deployment | NOT_DEPLOYED | No deployment record; root and Stable/Beta feed endpoints returned 404 at audit time. First static bootstrap remains an explicitly confirmed manual main dispatch. |
| OTA feeds | UNAVAILABLE | No app-pinned production key; no signed feeds were created. |
| Candidate APK | PASS (local artifact) | 16,966,920 bytes; package/version 1.1.52/code 40; expected SHA-256; `apksigner` v2 verification passes and signer matches fixed certificate pin. |
| Vehicle OTA | NOT_TESTED | No install or update was attempted on the Xingyue L head unit. |
| Release intent | DISABLED | `config/release-intent.json` remains `enabled=false`. |
| OTA key preflight tools | PASS (local) | `dry-run`, ephemeral in-memory `self-test`, read-only GitHub Environment name/policy audit, and PowerShell wrapper passed. Python 3.12.14/GitHub CLI are available; OpenSSL CLI is absent. No key file was created and no secret value was requested. |
| Static Pages rendering | PASS (local temporary build) | Read-only GitHub Releases plus the public v1.1.51 proof asset rendered Stable and history; unverified Beta remained hidden, OTA was marked unavailable, and no feed file was generated. No deployment was run. |

## Safe order after separate approvals

1. Review and merge PR #6 under the repository's protected-main process; no production tag is implied by that merge.
2. Fix the release-policy audit credential gap using an isolated least-privilege GitHub App installation, verify the exact API reads, then keep release intent disabled until approved.
3. Configure `ota-manifest-publisher` for main only with a required reviewer and self-review prevention. Provision the OTA signing Secret and key ID only after production-key creation approval. Keep it separate from Android Release signing.
4. Create and independently review the production P-256 key and public SPKI record. Add only the public key to a later immutable-ledger Android Release, with Android signing identity and version gates preserved.
5. Install the bootstrap APK by trusted human-confirmed means; verify correct trust-root load and negative tests on the intended device.
6. Run the separately approved signer-only preflight. This phase did not run it.
7. Only after APK/Release asset verification and protected human approvals may the OTA workflow sign feeds and deploy Pages. Verify the exact deployed feed and site; retain the prior feed/site on any failure.

## Local Phase 11 verification

The latest local checks passed after the Phase 11 source changes: Python 210 tests (13 intentionally skipped because the Windows host has no Bash), Android 2,057 unit tests (3 skipped), all AGENTS.md Debug lint/build tasks, version ledger validation, workflow/action pin checks, project-doc validation, ephemeral OTA sign/verify, staged/full-history Gitleaks, public-tree validation, and a temporary static site render using live public Release evidence. GitHub CI has not run for this unpushed diff. `actionlint` and Bash integration were not run locally because those executables are unavailable.

## Non-goals and stop conditions

Do not turn on `release-intent`, generate production keys, write GitHub Secrets, run signer-only checks, publish a tag/release, deploy Pages/feeds, upload an APK, or install an update on a vehicle as part of this readiness record. If a signer or feed cannot be authenticated, stop and preserve the installed app and last known-good site state.
