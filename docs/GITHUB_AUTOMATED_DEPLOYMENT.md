# CarPaly GitHub Automated Deployment Guide

## Current observable setup

Repository: `Qwy20040320/carpaly` (Public). The default branch is `main`. Pages API reports workflow deployment source and the target URL, but no Pages deployment record was found during Phase 11; the root and both OTA feed URLs returned HTTP 404 at that check. Treat the website as not yet deployed, not as a verified live site. A local temporary build from read-only GitHub CLI Release metadata and the public `v1.1.51` verification sidecar rendered three history entries, Stable `v1.1.51`, no Beta download, and `otaFeedStatus=unavailable` with no feed files. This validates rendering only, not network deployment.

The active `Protect main - CarPaly` ruleset requires PRs, prevents deletion and non-fast-forward updates, requires the Android CI context, has zero approving reviews, and has no bypass actors. The release policy separately checks the exact merge SHA, authorized merger, PR source, ruleset evaluation and successful CI. `release-intent.enabled` remains false.

| Environment | Observed deployment branch policy | Secret/variable state (names only) | Protection finding |
| --- | --- | --- | --- |
| `github-pages` | `main` | no signing Secrets or Variables | no Pages deployment yet |
| `mfi-public-release` | `main`, `v1.*.*` tags | six signer/MFi Secrets and two Variables are present | cloud keystore/signer has not been verified; no required-reviewer rule observed |
| `release-policy-audit` | `main` | empty | current workflow expects `RELEASE_POLICY_READ_TOKEN`, which is not configured |
| `ota-manifest-publisher` | `main` | empty | no required reviewer/self-review protection observed; OTA publishing must stay blocked |

Secret values were not read. Name presence is not proof that values are valid. Android Release signer validation is version-code-specific: code 36–40 uses the legacy certificate `4d26d1c861b41a2cee4515e31f5f5c7eb13b9dd06e7485aa1687bc1d2ac73d90`; code 41 onward uses `d9b329525fc1ef21c365fab72c10367527cc038297c4f30eaa22b2207429139e`. The protected Environment pin must match the version epoch being built and the signer-only preflight must still pass before any protected Release operation. This local policy correction does not change GitHub Environment values.

## Pages first static deployment

`pages.yml` builds without signing secrets and deploys through `github-pages` with `pages: write` and `id-token: write`; build permissions are read-only. The workflow shares a non-cancelling concurrency group with the OTA feed publisher. A first deployment is a manual main-branch dispatch and requires an explicit bootstrap confirmation. It must not create stable/beta feed files while the app trust root is empty. This phase did not dispatch or deploy Pages.

After separate user authorization, confirm GitHub repository Settings → Pages → Build and deployment → Source is **GitHub Actions**, then Actions → `Publish CarPaly download site` → Run workflow on `main`, and select the first-static-bootstrap confirmation only after verifying that the production Pages site and both feed URLs are absent. The build must use real Releases; absent validated Beta assets stay hidden. Verify the deployed site and feed status after the run. If either feed existed before the deployment, the builder must validate and preserve it byte-for-byte or fail the full deploy.

## Production OTA Environment

The local policy expects only `ota-manifest-publisher` on `main`, at least one required reviewer, the `OTA_MANIFEST_SIGNING_PRIVATE_KEY_PEM` Secret, and the `OTA_MANIFEST_SIGNING_KEY_ID` Variable. The actual Environment currently has no reviewer rule, Secret, or Variable, and `config/ota-publisher-policy.json` is disabled/unattested. The Phase 11 workflow now checks the real Environment API before the signing job; its read-only preflight requires an Actions-read token and fails if the branch allow-list, reviewer rule, or no-self-review control is missing.

Manual setup (only after a separate production authorization): Settings → Environments → `ota-manifest-publisher`; allow only `main`; configure at least one authorized reviewer and prevent self-review; then provision the two names above without displaying the private key. Keep this environment distinct from `mfi-public-release` and `github-pages`. Pages must never receive MFi, Android signing, or OTA private-key Secrets.

## Release policy API credential

`release-policy-audit` currently has no configuration but its publisher job reads `RELEASE_POLICY_READ_TOKEN`. That is an actual blocker; no value was requested or written. The job reads PR association/details/reviews, the main ruleset and its exact rule-suite evaluation. Current GitHub REST documentation says repository rule-suite endpoints require repository `Administration: read`, while PR/review evidence needs `Pull requests: read`. `GITHUB_TOKEN` has no `administration` permission key in the Actions permissions schema. Prefer a repository-scoped GitHub App installation token with only Metadata read, Administration read, and Pull requests read, minted just-in-time, or redesign the gate without the rule-suite evidence. Do not use a classic full-repository PAT. No GitHub App has been configured in Phase 11.

If configured later, put the app private key/client ID only in the protected `release-policy-audit` Environment, restrict the installation to this repository, mint a short-lived token within the gated job, pass it only as `GH_TOKEN`, and revoke it at job completion. Validate the required API calls in a non-publishing run before enabling release intent. Never put this credential in a PR or Pages job.

## Release to OTA sequence

The intended order remains: reviewed same-commit release intent on protected `main` → full CI → exact merge proof → protected signer preflight → authenticated Release APK build and signature verification → Tag/Release → verify downloaded APK/checksum/source snapshot → sign Stable/Beta OTA data with an already app-pinned key → validate current feed state and final Pages artifact → deploy once through serialized Pages Environment → verify deployed links and documentation. A failure before Pages leaves old site/feed intact. Draft PRs, branch pushes, tag pushes and ordinary Pages builds do not sign or publish APKs.

No production publishing or deployment was performed in Phase 11.
