# CarPaly Release, Pages and OTA integration report

Audit date: 2026-10-12. This report records implementation evidence separately from unverified GitHub and vehicle behavior.

## Repository and remote state

- Local branch: `feature/carpaly-v1.1.5`; local HEAD and fetched `origin/feature/carpaly-v1.1.5` are `c08c0d029014aec1e50cfd0d128de2fff7c01bf4` before this turn's uncommitted work.
- PR #6 remains `OPEN` / Draft, from `feature/carpaly-v1.1.5` to `main`, remote head `c08c0d029014aec1e50cfd0d128de2fff7c01bf4`.
- Five reviewed public files are staged for local review (`.gitignore`, the public Markdown allow-list, and the three reports named below); no commit, push, tag, Release, PR edit/merge, secret/environment change, Pages activation, or APK upload was performed.
- The remote repository homepage is still the Releases page. A read-only Pages API request returned 404; that response is insufficient to determine whether Pages is disabled, restricted by repository policy, or unavailable to the caller. Confirm the Pages source in repository Settings before concluding the cause.
- Only the `mfi-public-release` Environment appeared in the read-only Environment list. `ota-manifest-publisher` is absent. No secret values were read.

## Phase status

| Phase | Status | Evidence / limitation |
| --- | --- | --- |
| 0 — Current state and upstream release/site research | PASS locally | Reviewed upstream Android checks, Android TV build, Pages deployment, site generator, README/Chinese README, CHANGELOG, and AGENTS. See `docs/UPSTREAM_RELEASE_PARITY.md`. PR #6 was read-only inspected. |
| 1 — CarPaly website | PASS locally / NOT_TESTED online | Original Chinese/English CarPaly site generator, content, styling, verified release history/downloads, compatibility table, and install/update guide are present. A real API build in a temporary directory rendered 3 public Releases, Stable `v1.1.51`, and no Beta download because current Beta lacks a verified APK proof sidecar. A Pages API request returned 404; that response alone does not distinguish disabled Pages, repository policy, or endpoint permission/availability. |
| 2 — OTA manifest backend | PASS in synthetic-key tests / BLOCKED for production | ECDSA P-256 signing/verification, Stable/Beta separation, channel tombstones, Release proof/tag/main/checksum filtering, 30-day feeds, and matching an active app-pinned key are tested. The producer emits sorted compact UTF-8 JSON and signs those exact bytes; the app verifies the carried bytes without reserialization. The app trust store is intentionally empty; no production key/environment was created. Missing-key invocation returned BLOCKED and wrote zero feed files. |
| 3 — Android OTA client | PASS in local unit/build checks / NOT_READY for production | Stable default/Beta opt-in, pinned-endpoint fetch without redirects, signed payload validation, freshness/channel/package/version/size/hash/signer checks, GitHub checksum/APK download validation, APK package/version/signer/debug/MFi-asset checks, Android system installer handoff, and per-channel persisted manifest replay checkpoints are implemented/tested locally. The update card is one `APP_UPDATES` settings section; Settings Overview → About opens that same page/state. The client fails closed with the empty pinned-key resource. Range resume and process-persistent download recovery are not implemented. |
| 4 — Release/docs/site/OTA integration | PASS locally / NOT_TESTED online | Existing README/CHANGELOG/Release Notes synchronizer is reused. Pages and OTA now consume one atomically written Release/verification snapshot per workflow run. The site reports the existing v1.1.51 formal-vs-pre-release-note conflict without changing the hand-written Release body. No remote metadata was changed. |
| 5 — Verification | PASS for local suites / BLOCKED or NOT_TESTED externally | The required AGENTS Gradle command completed `BUILD SUCCESSFUL`; available Gradle XML reports total 2,055 tests with 0 failures/errors and 3 skipped (shared results were up-to-date from the prior successful run; common results refreshed this turn). The mobile/home/maphost Lint tasks succeeded with no errors. Python release/docs/OTA suites: 143 tests, 134 passed and 9 Bash integration tests skipped. Git-history Gitleaks scanned 593 commits with no leaks; targeted public-source Gitleaks scans and `check_public_tree.py` passed. GitHub workflow YAML was not independently parsed locally because Ruby, PyYAML, and an installed ActionLint parser are unavailable; GitHub CI remains the syntax/runtime verifier. |

## Published Release evidence observed read-only

- Current public Release tags: `v1.1.51`, `v1.1.5`, `v1.1.4`.
- Only `v1.1.51` has a verification record currently accepted by the site generator. This is metadata/asset verification, not proof of vehicle compatibility.
- `v1.1.51` is marked formal by GitHub while its unmarked hand-written text contains pre-release wording. The page emits a warning; the original Release body is untouched. A wording proposal already exists in `docs/RELEASE_AUTOMATION.md`.
- No v1.1.52 or future candidate is shown as a public Release or download.

## APK and vehicle safety

- Existing `artifacts/CarPaly-XingyueL-v1.1.52.apk` remained present after the required Debug CI build; no APK in `artifacts/` was generated, overwritten, resigned, installed, or uploaded by this turn.
- The CI command built Debug variants only, as required by the repository check. Those artifacts are not offered as user update packages.
- No final APK update, installer launch, settings migration, successful overwrite, or CarPlay regression test was performed on the Xingyue L. All vehicle OTA acceptance items remain `NOT_TESTED`; the procedure is in `docs/OTA_VEHICLE_TEST_PLAN.md`.

## OTA trust-root bootstrap and key operations

The trust root is `common/src/main/res/raw/ota_manifest_public_keys.json`. It is loaded from the installed APK and is never learned from the OTA server. An empty or malformed trust store blocks update checks; there is no unsigned fallback. The empty checked-in store is a pre-production state, not a usable OTA configuration.

The producer accepts an unencrypted PKCS#8 PEM ECDSA P-256 private key from `OTA_MANIFEST_SIGNING_PRIVATE_KEY_PEM` and a key id from `OTA_MANIFEST_SIGNING_KEY_ID`. GitHub encrypts Environment Secrets at rest; the workflow must scope them only to `ota-manifest-publisher`, require deployment review, and restrict permitted refs to the reviewed release/main path. The OTA key is not an Android APK signing key or an MFi authentication key.

Offline key ceremony (do not run for production until an authorized maintainer approves a production key):

1. On an approved isolated key-management workstation, create a P-256 key outside the checkout in an access-controlled secure location. Example PowerShell commands are `openssl genpkey -algorithm EC -pkeyopt ec_paramgen_curve:prime256v1 -out D:\Secure\ota-manifest-prod.pem` and `openssl pkey -in D:\Secure\ota-manifest-prod.pem -check -noout`. Do not echo, paste, attach, or commit the PEM. Recovery material must follow the organization's approved key-custody policy.
2. Export only the public record: `python scripts/export_ota_public_key.py --private-key D:\Secure\ota-manifest-prod.pem --key-id ota-prod-2026-01`. The JSON output contains an X.509 SubjectPublicKeyInfo DER key encoded as Base64, algorithm `SHA256withECDSA-P256`, and status `active`; it contains no private bytes. Review and merge this record into the app trust resource. During rotation, retain prior reviewed keys as `retiring` for a bounded overlap; do not replace the trust list with only the new entry.
3. Review, build and Android-sign an app containing the public key; distribute and install that bootstrap app through a trusted manual path (for example an authenticated GitHub Release installer or ADB). Verify it is installed before enabling OTA signing. v1.1.51 has no pinned OTA key and cannot securely OTA-install a trust root it does not already know.
4. Only after the bootstrap app is available, an authorized owner may create/configure `ota-manifest-publisher` separately from `mfi-public-release`, restrict deployments, and store `OTA_MANIFEST_SIGNING_PRIVATE_KEY_PEM` as an Environment Secret and `OTA_MANIFEST_SIGNING_KEY_ID` as an Environment Variable. A safe PowerShell/gh pattern is `Get-Content -Raw -Path D:\Secure\ota-manifest-prod.pem | gh secret set OTA_MANIFEST_SIGNING_PRIVATE_KEY_PEM --repo Qwy20040320/carpaly --env ota-manifest-publisher`. Confirm only the name with `gh secret list --env ota-manifest-publisher`; never read or print its value. These online changes were not authorized or performed here.
5. Before signing a feed, the producer derives the public key from the secret and requires an exact match with one `active` app-pinned key id. Local/CI signing tests use generated synthetic keys only.

GitHub Pages and Environment setup (manual; not performed in this task):

1. A repository maintainer opens **Settings → Pages → Build and deployment → Source** and selects **GitHub Actions**. The current workflow already separates a read-only OTA/site build job from a deploy job with only `pages: write` and `id-token: write`, using `github-pages` as the deployment environment. Confirm the `github-pages` environment and the first successful Actions deployment before changing the repository homepage.
2. The Pages REST API returned HTTP 404 during read-only inspection. Do not infer the cause from that response alone; inspect the Pages settings UI, repository policy/plan, Actions permissions, and the latest workflow run.
3. After the public key bootstrap app is installed, create `ota-manifest-publisher` separately from `mfi-public-release`. Configure selected deployment refs for protected `main` and release tags matching `v1.*.*`; add at least one independent required reviewer and enable prevent-self-review where available. Disable administrator bypass if that control is available. Reviewer/protection-rule availability depends on repository visibility/plan; verify the saved UI state instead of assuming it.
4. Configure only `OTA_MANIFEST_SIGNING_PRIVATE_KEY_PEM` as an Environment Secret and `OTA_MANIFEST_SIGNING_KEY_ID` as an Environment Variable in this environment. Do not place these in repository-level secrets or `github-pages`; the workflow's Pages deploy job does not receive them.
5. The production feed deploys only when the build job, including signed-manifest generation and regression tests, succeeds. A signing/verification failure prevents Pages artifact upload/deployment, leaving the previously deployed site and feeds in place. The workflow uses a shared non-canceling concurrency group; successful online behavior remains unverified until a real post-merge Actions run and HTTP fetch.

Rotation, revocation, and replay limits:

- Rotation is staged: ship the new public key in a reviewed Android app first, then begin signing feeds with it; keep the previous key `retiring` only for a documented overlap, then remove/revoke it in another reviewed app update. The remote feed cannot add trust dynamically. Revocation is not instantaneous for offline or old clients; trust-store changes must reach them through the existing trusted installer channel.
- The client stores the highest accepted signed `issuedAt` and signed-payload digest per channel. Older issued feeds are rejected; an exact replay is idempotent, while different content reusing the same issue time is rejected. The checkpoint is app-private preferences, not hardware monotonic storage; clearing app data/reinstalling resets it. Expiry and APK version/signer checks remain independent defenses.
- The manifest signer can select only the canonical CarPaly Release URL and signed metadata. The client downloads and validates the APK digest, package, version, pinned Release signer, and installed-app signer; Android's package installer independently enforces update signature compatibility. A manifest signature cannot make an APK with a different signer replace the installed app.

No production OTA key has been generated, imported, or uploaded, and no production trust root is present in the current app.

## Remaining blockers / manual actions

1. Review the local changes and create/update PR #6 only after authorization for remote writes. This turn leaves all changes uncommitted; only the five public documentation/allow-list files above are staged, and runtime/workflow/site changes remain unstaged.
2. Run CI on GitHub to validate workflow YAML and the actual Pages job. Nine Bash publisher integration tests require a Linux/Git Bash environment; this machine has no Git Bash in the usual install locations, and WSL reports no usable distro.
3. An authorized maintainer must enable GitHub Pages with **Source: GitHub Actions** and ensure the `github-pages` deployment environment is permitted. The public homepage/About field can be switched to `https://qwy20040320.github.io/carpaly/` separately; it remains the Releases page now.
4. Before any production OTA feed: follow the staged trust-root bootstrap above; the public key must ship in an app installed through a trusted channel before the private signing secret is configured or used. None of those production operations were performed.
5. Keep OTA key separate from MFi/Android signing/repository-admin credentials. Never populate the empty trust store with an unreviewed key or let the application fetch its own trust key.
6. The repository setting **Allow GitHub Actions to create and approve pull requests** may be needed for the existing documentation sync job to open its PR; if the owner declines it, use a narrowly scoped GitHub App/fine-grained token as documented in `docs/RELEASE_AUTOMATION.md`.
7. After a verified feed is deployed, run the parked-vehicle acceptance checklist and mark only observed results `PASS`.

## Final status fields

```text
UPSTREAM_PARITY_STATUS=PASS_LOCAL_AUDIT
CARPALY_REPOSITORY=https://github.com/Qwy20040320/carpaly
BASELINE_COMMIT=c08c0d029014aec1e50cfd0d128de2fff7c01bf4
PR_6_STATUS=OPEN_DRAFT_UNCHANGED
ANDROID_CI_STATUS=PASS_LOCAL; REMOTE_CI_NOT_RUN_FOR_UNCOMMITTED_CHANGES
ANDROID_TV_BUILD_STATUS=NOT_RUN
RELEASE_WORKFLOW_STATUS=PASS_STATIC_ONLY; NOT_TRIGGERED
RELEASE_SIGNER_STATUS=V1.1.51_PUBLIC_PROOF_PRESENT; CLOUD_SECRET_NOT_TESTED
GITHUB_PAGES_SITE_STATUS=PASS_LOCAL_BUILD
GITHUB_PAGES_DEPLOYMENT_STATUS=NOT_TESTED; PAGES_API_404_CAUSE_UNKNOWN
README_SYNC_STATUS=PASS_EXISTING_AUTOMATION_REUSED
CHANGELOG_SYNC_STATUS=PASS_EXISTING_AUTOMATION_REUSED
RELEASE_NOTES_SYNC_STATUS=PASS_PRESERVES_UNMARKED_HANDWRITTEN_BODY
APK_OWNERSHIP_STATUS=CARPALY_SOURCE_ONLY; NO_NEW_RELEASE_APK_BUILT
APK_SIGNING_STATUS=NOT_APPLICABLE_TO_THIS_LOCAL_DEBUG_CI; EXISTING_RELEASE_IDENTITY_UNCHANGED
OTA_MANIFEST_STATUS=BLOCKED_PRODUCTION_KEY_NOT_PROVISIONED
OTA_MANIFEST_SIGNATURE_STATUS=PASS_EPHEMERAL_TEST_KEY_ONLY
OTA_STABLE_CHANNEL_STATUS=BLOCKED_NO_PRODUCTION_FEED
OTA_BETA_CHANNEL_STATUS=BLOCKED_NO_VERIFIED_BETA_APK_OR_PRODUCTION_FEED
OTA_CHECK_STATUS=FAILS_CLOSED_WITH_EMPTY_APP_TRUST_STORE
OTA_DOWNLOAD_STATUS=LOCAL_TESTS_PASS; NO_LIVE_DOWNLOAD
OTA_SHA256_VERIFY_STATUS=PASS_UNIT_TESTED
OTA_APK_SIGNER_VERIFY_STATUS=PASS_UNIT_TESTED; NO_CANDIDATE_RELEASE_APK_INSTALLED
OTA_PACKAGE_INSTALLER_STATUS=PASS_UNIT_TESTED; REAL_HEAD_UNIT_NOT_TESTED
OTA_DRIVING_SAFETY_STATUS=PASS_FAIL_CLOSED_POLICY; VEHICLE_STATE_SIGNAL_UNAVAILABLE
OTA_REAL_VEHICLE_TEST_STATUS=NOT_TESTED
LOCAL_TEST_STATUS=PASS (Gradle 2052 passed/3 skipped; Python 134 passed/9 skipped; Gradle XML total 2055)
GITHUB_RUNTIME_TEST_STATUS=NOT_TESTED_FOR_THIS_UNCOMMITTED_CHANGESET
UNSTAGED_CHANGES_PRESERVED=YES; FIVE_PUBLIC_DOC_FILES_STAGED; NO_COMMIT
BLOCKERS=Pages/ota environment absent; production OTA key not provisioned/pinned; 9 Bash tests unavailable locally; no vehicle OTA acceptance
MANUAL_GITHUB_ACTION_REQUIRED=Enable Pages; configure isolated OTA Environment after app-pinned public key ships; optionally allow docs Action PR creation
NEXT_SAFE_STEP=Review local diff, then user-authorized update to Draft PR #6; do not release until OTA key and Pages policies are reviewed
```

## Phase 7 local verification update — 2026-10-12

This section supersedes the earlier snapshot counts and the earlier statement that no local commits existed. It records only checks actually run against the Phase 7 working tree; GitHub CI has not run for these local changes.

- Branch baseline remains `c08c0d029014aec1e50cfd0d128de2fff7c01bf4`; remote `feature/carpaly-v1.1.5` was fetched and had not advanced at the last check. PR #6 remains OPEN / Draft. No push, merge, tag, Release, secret/environment edit, or Pages activation was performed.
- The AGENTS Gradle command completed successfully: 2,059 reported tests, 0 failures, 0 errors, 3 skipped; mobile, home, and maphost lint and Debug assembly tasks succeeded. Debug output is CI-only and is not a user release APK.
- Python discovery completed 171 tests, 13 skipped, with no failures. The skipped set includes shell-dependent integrations unavailable on this Windows host; they still require GitHub Linux CI. Workflow YAML/actionlint also still require the Linux CI environment.
- `gitleaks git --redact .` scanned 593 commits with no leaks; `scripts/check_public_tree.py`, workflow SHA pin checks (13 immutable pins), Pages workflow checks, release metadata checks, release automation/intent checks, and targeted OTA/Pages tests passed.
- A live Release API site build in an isolated temporary directory rendered three published releases, Stable `v1.1.51`, and no Beta download. The existing formal/pre-release wording mismatch is surfaced as a warning only; the hand-written online Release body was not edited.
- The production OTA manifest command was run with production signing variables absent. It failed closed with the expected missing-key status and emitted zero feed files. The app trust store remains empty, no production OTA identity was generated, and OTA is not production-ready.
- The existing `artifacts/CarPaly-XingyueL-v1.1.52.apk` was preserved unchanged (16,966,920 bytes; SHA-256 `f5bea98180dadad4fecab77031f7373dc423b59c420bc9b085372b524c7e8c64`). No APK was rebuilt, resigned, installed, or uploaded in the Phase 7 verification.
- `mfi-public-release` is the only Environment observed in read-only inspection. `ota-manifest-publisher` and `github-pages` were not present. The Pages API 404 does not identify whether Pages is disabled, policy-restricted, or unavailable to this caller. Repository Actions default workflow permissions are read-only and GitHub Actions PR creation is not enabled. No setting was changed.
- The local site/OTA, Android client, and release automation changes are being prepared in explicit reviewable commit groups. Unrelated CarPlay runtime/vehicle diagnostic edits remain outside those groups and are preserved in the worktree.
- The local commit set is not yet on GitHub. GitHub Linux CI, online Pages deployment, cloud signer/secrets verification, production OTA provisioning, and vehicle OTA acceptance remain NOT_TESTED or BLOCKED as appropriate.
