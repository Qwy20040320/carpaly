# Release documentation automation

This automation keeps the public README, changelog, Release Notes, and repository description aligned with verifiable GitHub release state. It is independent from Android builds and does not read the `mfi-public-release` Environment.

## Sources of truth

- GitHub Releases API supplies published tag, draft/pre-release state, publication date, Release URL, and the actual uploaded asset names, links, sizes, and SHA-256 digests.
- The version ledger at `config/android-version-ledger.json` supplies application id, fixed signer identity, immutable `versionName`/`versionCode` allocations, and local artifact records. It does not establish that a version was published.
- `config/release-documentation.json` supplies the candidate summary, user-reported vehicle feedback, repository About description target, and managed marker identifiers.
- An APK is presented as verification-record checked only when its Release sidecar JSON agrees with the GitHub asset digest, package id, tag/version, fixed signing-certificate SHA-256, and required APK checks. The workflow reads the small JSON sidecar only; it does not download or execute APKs.

Internal APK metadata is never rewritten to match a display label. Historical tags and filenames remain exactly as GitHub reports them. Drafts are excluded; pre-releases are labeled separately; the latest formal Release is the newest published non-pre-release Release. Local candidates have no public download link.

## Managed document regions

The synchronizer edits only marker-delimited regions in the root `README.md` and `CHANGELOG.md`. It refuses to write when a marker is absent, duplicated, or out of order. All text outside those regions remains unchanged. Current Release Notes without a `CARPALY:RELEASE_NOTES` marker are left intact and reported as `UNMANAGED_PRESERVED`; new Release Notes created by the release publisher include a managed facts block.

Do not remove or copy managed marker pairs. To add hand-written context, place it before or after a managed region. Machine-generated release status must not be hand-edited inside the marker pair.

## Workflow behavior

- `release-docs-check.yml` runs metadata validation, workflow pin checks, and offline tests. It needs only read permission.
- `release-docs-sync.yml` runs on published/edited/deleted Release events, a daily reconciliation schedule, manual dispatch, and a successful manual tag workflow run. The additional `workflow_run` path compensates for GitHub not starting downstream workflows for most events created with `GITHUB_TOKEN`. It reads public release state and never builds an APK or reads signing/MFi secrets.
- The sync workflow updates a dedicated `automation/release-docs-sync` branch and opens or updates a Pull Request. It never commits directly to `main`, force-pushes, or auto-merges. If a merge conflict or GitHub permission failure occurs, it stops and preserves the existing branch/PR.
- Release Notes are patched only when the Release body already contains exactly one well-formed managed block. Identical text is not patched, preventing `release: edited` loops. Unmarked hand-written bodies are preserved.
- The authenticated publisher adds a managed facts block to newly created Release Notes. On rerun, already-published Releases are read-only; an existing draft's hand-written title and body are preserved, and only its draft/pre-release flags may change after every asset verifies.
- About synchronization changes only the repository description. Existing homepage and topics are read-only. If the description already matches, no admin token is needed. If it differs, the workflow needs the optional `CARPALY_REPO_ADMIN_TOKEN` repository secret with narrowly scoped repository-administration write access; otherwise the README/CHANGELOG sync succeeds and the About status is reported as blocked/proposed-only.
- The repository currently reports `can_approve_pull_request_reviews=false`. [GitHub's repository Actions settings documentation](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/enabling-features-for-your-repository/managing-github-actions-settings-for-a-repository) says this setting controls whether `GITHUB_TOKEN` may create or approve pull requests. The sync workflow does not approve PRs, but automated PR creation will require the repository owner to enable that setting or configure a narrowly scoped GitHub App/fine-grained token with contents and pull-request write access. Do not grant the signing or MFi secrets to the docs workflow.

The current repository description is intended to be:

> CarPaly — Android CarPlay receiver project with Geely Xingyue L (KX11) compatibility development.

The project homepage and topics are not rewritten by the description synchronizer.

## Manual GitHub configuration and signer verification

### Documentation sync permission

The current documentation workflow uses the built-in `GITHUB_TOKEN`, with only `contents: write` and `pull-requests: write` on its sync job, to push its dedicated branch and open/update a PR. To let that workflow create PRs, a repository owner must open **Settings → Actions → General → Workflow permissions** and enable **Allow GitHub Actions to create and approve pull requests**. The workflow itself never approves or merges a PR. If the repository owner does not want that repository-wide switch enabled, use a repository-scoped GitHub App or fine-grained token with only the contents and pull-request permissions needed for this one workflow; do not give it Release, Actions, MFi, or signing-secret access. The optional `CARPALY_REPO_ADMIN_TOKEN` is separate and is needed only if the repository description actually differs and is to be changed.

### Safe Release certificate check

Do not change `RELEASE_SIGNING_CERT_SHA256` to make an unknown keystore pass. The immutable expected value is `4d26d1c861b41a2cee4515e31f5f5c7eb13b9dd06e7485aa1687bc1d2ac73d90`.

1. In **Settings → Environments → `mfi-public-release`**, confirm only the names and scopes of these Environment Secrets: `MFI_IDENTITY_PK8_BASE64`, `MFI_CERTIFICATE_P7B_BASE64`, `RELEASE_KEYSTORE_BASE64`, `RELEASE_STORE_PASSWORD`, `RELEASE_KEY_ALIAS`, and `RELEASE_KEY_PASSWORD`. Confirm `RELEASE_SIGNING_CERT_SHA256` is an Environment Variable with the pinned value above. GitHub intentionally does not reveal secret values; never echo them or place them in command arguments, logs, or source files.
2. On the trusted machine that holds the original Release keystore, inspect its public certificate using `keytool -list -v -keystore <protected-keystore-path> -storetype PKCS12 -alias <known-alias>`. Omit `-storepass` so keytool prompts interactively. Compare the reported SHA-256 certificate fingerprint, normalized to lowercase hex without colons, with the fixed value above and with `apksigner verify --print-certs <known-original-release-apk>`. Do not export the private key.
3. Compare the known alias with the value entered in the Environment without displaying the alias or password in logs. If a Secret must be repaired, set it only from the verified original keystore and credential source using an approved secure stdin-based process; do not guess passwords, substitute a new keystore, or change the pinned fingerprint.
4. The Android workflow has a separate `verify_release_signer_only` manual-dispatch mode. It is restricted to the `main` ref, receives only the four Release signer Secrets and the pinned fingerprint, has `contents: read`, reports the public certificate SHA-256 and a failure category, then deletes its temporary keystore. It does not receive MFi inputs, build an APK, create a tag, call the Release API, or upload assets. To use it, choose **Actions → Android checks → Run workflow**, select `main`, set `verify_release_signer_only=true` and `publish_authenticated_release=false`.
5. The `mfi-public-release` deployment policy must allow the `main` branch for this signer-only job as well as the existing `v1.*.*` release-tag pattern. This is a targeted Environment deployment-ref change, not a secret change. If policy is intentionally tag-only, leave it unchanged and do not run the branch-only preflight; first agree on a permitted read-only validation ref. The actual authenticated publishing job remains restricted to an explicit manual dispatch on a version tag whose commit is contained in `main`.

This preflight-only mode is the evidence path for the previous mismatch. The previous cloud log established `SIGNER_MISMATCH` but omitted the actual certificate digest; a passing run should show the actual public certificate SHA-256. A failure should be classified as missing Environment value, invalid Base64/PKCS12, alias mismatch, password/integrity failure, certificate parse failure, or fingerprint mismatch. It must not be used to trigger or simulate a historical Release.

### v1.1.51 Release Notes revision proposal (not applied online)

GitHub currently marks `v1.1.51` as a formal Release (`prerelease=false`), while the hand-written body says `预发布测试版（Pre-release）` and `测试预发布版`. Suggested replacement wording for owner review:

> **发布渠道：正式版（GitHub `prerelease=false`）。** 此状态仅表示 GitHub Release 元数据，不代表已完成星越 L 实车验收。现有用户反馈曾报告 CarPlay 连接正常、Siri 双向语音正常及方向盘按键有响应，但对应 APK 版本、车型配置和连接方式未记录，且未由维护者独立复现；不据此宣称本 Release 已实车兼容。用户同时反馈音乐约一秒后自动暂停（唤醒 Siri 时可播放）、导航提示无声、顶部原车状态栏仍遮挡。HUD、仪表和燃油接口保持 `NOT_TESTED`。

This is a proposal only. The synchronizer preserves this existing unmarked body, and no online Release Notes were changed.

## P0 signing/deployment incident record (2026-10-12)

- Runs #44 (`v1.1.4`), #51 (`v1.1.5`), and #62 (`v1.1.51`) were `push`-tag runs on `main` commit `ef8bec6e0d20060ceb436c36eb2d495f63c831bd`. The old `main` workflow included `tags: ['v1.*']`, so each historical tag started the protected Release job. The tag-in-main check and ordinary Android `check` job passed; the grouped provisioning/signing step failed with `Release keystore signer differs from the pinned environment certificate`.
- The `mfi-public-release` Environment has a tag policy matching `v1.*.*`; the jobs reached and ran inside it, so this is not evidence of a deployment-branch-policy rejection. No required reviewer is configured. Its six expected Secret names and `RELEASE_SIGNING_CERT_SHA256` variable exist, but GitHub does not reveal Secret values through the read API.
- The old failure message omitted the actual signer fingerprint. Therefore `SIGNER_MISMATCH` is the confirmed failure category, but the exact source (wrong PKCS12 value, alias, or secret-content corruption) is not proven. The local v1.1.52 APK signer matches the pinned digest; this does not prove the Environment keystore Secret matches it.
- The local feature workflow now removes automatic tag-push publication and requires a manual dispatch with an explicit boolean plus a tag commit contained in `main`. MFi resource provisioning and Release signer validation are separate steps. `scripts/release_signing_preflight.py` reports stable failure categories and only public certificate SHA-256 fingerprints; it never disables the signer pin.
- README/CHANGELOG synchronization is a separate workflow with no `mfi-public-release` Environment and no signing/MFi Secret references. Current repository About Description, homepage and topics already match the local metadata; no remote metadata was changed during this task.
- The public `v1.1.51` Release is marked formal by GitHub metadata while its hand-written body says “pre-release testing build”. The synchronizer reports this conflict and preserves the unmarked body; it does not silently rewrite the channel or the notes.

## Local checks

From the project root, use Python 3.12+ and run:

```powershell
python scripts/validate_release_metadata.py
python -m unittest scripts.test_release_docs_sync scripts.test_release_signing_preflight scripts.test_release_pipeline
python scripts/sync_release_docs.py --repository Qwy20040320/carpaly
python scripts/sync_release_docs.py --repository Qwy20040320/carpaly --preview-release-notes
```

The first sync command is read-only and prints a proposed diff; `--preview-release-notes` also makes GET requests only and reports which marked note blocks would change. Add `--write` only when intentionally updating the marked local regions. `--sync-release-notes` and `--sync-about` perform external writes and are not needed for local verification. Never pass credentials as command-line arguments; the GitHub workflow uses `GH_TOKEN` from the Actions context and an optional separate About token.

## Current candidate and vehicle evidence

The local ledger currently allocates v1.1.52 / versionCode 40 as a candidate. The GitHub API, not that local allocation, decides whether it has a public Release. User-reported CarPlay/audio/display observations are labeled as such, with unknown APK version or connection mode stated explicitly. They do not imply a fix or full-vehicle compatibility. HUD, DIM/instrument cluster, fuel data, and other unverified vehicle paths remain `NOT_TESTED`.
