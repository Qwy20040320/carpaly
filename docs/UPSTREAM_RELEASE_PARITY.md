# DiPlay release and website parity audit

Audit date: 2026-10-12. This is a source-level comparison of public upstream files and local CarPaly behavior; it is not a claim of runtime or vehicle validation.

## Upstream sources reviewed

- [Android checks workflow](https://github.com/shihabal3amri/DiPlay/blob/main/.github/workflows/android.yml)
- [Android TV build workflow](https://github.com/shihabal3amri/DiPlay/blob/main/.github/workflows/build-android-tv.yml)
- [GitHub Pages workflow](https://github.com/shihabal3amri/DiPlay/blob/main/.github/workflows/pages.yml)
- [Website generator](https://github.com/shihabal3amri/DiPlay/blob/main/scripts/build_site.py)
- [English README](https://github.com/shihabal3amri/DiPlay/blob/main/README.md), [Chinese README](https://github.com/shihabal3amri/DiPlay/blob/main/README.zh-CN.md), [CHANGELOG](https://github.com/shihabal3amri/DiPlay/blob/main/CHANGELOG.md), and [AGENTS.md](https://github.com/shihabal3amri/DiPlay/blob/main/AGENTS.md)
- [Published upstream site](https://shihabal3amri.github.io/DiPlay/)

## Behavior comparison

| Area | DiPlay upstream behavior | CarPaly local behavior | Parity / difference | Files and verification |
| --- | --- | --- | --- | --- |
| Android checks | Main push, pull request, and manual dispatch; Ubuntu; source tests, lint, Debug builds, test-report artifact. | Existing Android checks retain ordinary PR/Push CI and isolate authenticated publishing behind explicit manual inputs and a protected environment. | Same developer feedback loop; CarPaly has additional signing/MFi release boundaries. | `.github/workflows/android.yml`; existing action-pin and release checks. |
| Android TV build | Manual source-only Debug build; artifact retention is 7 days; it is not the authenticated public APK. | Manual source-only Debug artifact; it remains separate from formal releases. | Build model matches; artifact display name still needs a CarPaly-specific label review. | `.github/workflows/build-android-tv.yml`; workflow should remain non-release and secret-free. |
| GitHub Pages | Main/site-path changes plus manual dispatch; deploys the `site` tree through official Pages actions and a `github-pages` environment. | New bilingual CarPaly generator and separate Pages deploy job; the build job has read-only contents access, and the deploy job has only Pages/OIDC permissions. | Architecture aligned; immutable action pins and OTA signing are CarPaly hardening/extensions. | `.github/workflows/pages.yml`, `scripts/build_site.py`, `site/content.json`, `site/assets/site.css`, `scripts/check_pages_workflow.py`. |
| Site content | Multilingual download/version/history pages sourced from DiPlay's releases and hard-coded upstream links. | Chinese/English pages use only CarPaly published Releases and validated APK verification sidecars; no local candidate or unverified APK receives a download button. | Layout/function family is comparable, but assets, brand, repository, release source, and compatibility statements are CarPaly-owned. | `scripts/build_site.py`; `scripts/test_build_site.py`; site build uses one Release snapshot for both Pages and OTA generation. |
| Release APK | Upstream workflow/Release artifacts describe DiPlay's own build and authorization scope. | CarPaly APK must be built from CarPaly source, package `com.shihab.diplay.hudtest`, reserved version ledger, and the pinned CarPaly signer. | Deliberately not a binary mirror; application behavior, identity, and vehicle claims remain CarPaly-specific. | Existing Android release pipeline and verification sidecars; no publishing action was run in this task. |
| Release metadata and history | README/CHANGELOG/site describe upstream releases. | Existing synchronizer manages only marked README/CHANGELOG regions and preserves hand-written Release Notes; Pages reads actual Releases and ignores drafts. | User content is preserved; metadata source remains the existing Release API and version ledger. | `scripts/sync_release_docs.py`, `scripts/validate_release_metadata.py`, `config/release-documentation.json`. |
| OTA | No CarPaly vehicle updater or CarPaly OTA channel exists upstream. | Stable/Beta signed-manifest design, APK/signature checks, persisted per-channel replay checkpoint, and Android installer handoff are CarPaly extensions. | Not upstream parity; this is new code and remains disabled until a reviewed public key ships in an app installed through a trusted manual channel, the isolated publisher Environment is provisioned, Pages is enabled, and vehicle installation is tested. | `scripts/ota_manifest.py`, `scripts/build_ota_manifests.py`, `scripts/export_ota_public_key.py`, `common/.../UpdateManifestVerifier.kt`, `UpdateManifestReplayGuard.kt`, `ota_manifest_public_keys.json`. |
| GitHub permissions | Upstream workflows primarily build and deploy the upstream project. | Pages signing and deployment are split across `ota-manifest-publisher` and `github-pages`; neither receives MFi or Android signing secrets. | Tighter capability separation; repository owner still must configure Pages and the OTA Environment. | `.github/workflows/pages.yml`, `docs/RELEASE_AUTOMATION.md`, static permission-boundary check. |
| Security posture | Reviewed workflow sources use version-tagged Actions references in places; tags are mutable references. | New Pages workflow uses full commit-SHA action references, minimal job permissions, immutable site-to-OTA Release snapshot, fail-closed proof and signed-feed handling. | Deliberate security hardening, not a byte-for-byte copy. | `scripts/check_pages_workflow.py`, `scripts/check_workflow_action_pins.py`; local checks passed. |

## Current status and blockers

- Local site source, tests, and Pages workflow are present. The workflow has not been run in GitHub and the site has not been deployed. Read-only GitHub Pages API inspection returned 404 on the audit date; Pages must be enabled by an authorized repository maintainer.
- The trust store `common/src/main/res/raw/ota_manifest_public_keys.json` is intentionally empty. No production OTA private key was generated or configured. The client therefore refuses OTA checks until a reviewed public key is shipped.
- Stable/Beta manifests cannot be produced until the matching key is pinned in the app and the isolated `ota-manifest-publisher` Environment is provisioned. No GitHub Environment or secret was modified.
- The first app build that contains the OTA trust root cannot be installed through the old app's OTA channel: v1.1.51 has no pinned OTA key. That bootstrap build must be installed manually or via another already-trusted channel before the publisher secret is enabled and OTA feeds are signed.
- The Android app's verified APK install, signature compatibility, retained settings, and real-car update behavior remain untested in this task.
- Existing upstream and CarPaly formal release flows were not invoked. No tag, Release, PR, or remote setting was changed.

## Acceptance mapping

| Requirement | Result | Evidence |
| --- | --- | --- |
| Research original Android, TV, and Pages flows | PASS, source review | Linked upstream workflow files above. |
| Preserve CarPaly APK ownership and identity | PASS, code/config | Existing app id/version ledger/signer checks remain unchanged. |
| Bilingual site from actual verified CarPaly Releases | PASS locally; live deployment NOT_TESTED | Offline fixture tests pass; Pages API currently not configured. |
| Website and OTA share one Release snapshot | PASS locally | Snapshot round-trip test and workflow static check. |
| OTA stable/beta signed catalogs | BLOCKED by deliberate missing production trust key/Environment | Empty app trust store; no key material was provisioned. The client fails closed and does not trust a key fetched from the manifest host. |
| Pages official deployment and remote behavior | NOT_TESTED | Requires maintainer Pages/Environment settings and a main-branch Actions run. |
| Real vehicle installation and update | NOT_TESTED | Must be performed on the user's parked Xingyue L head unit. |

## Phase 7 release orchestration update — 2026-10-12

The local candidate adds a gated automatic-release path in addition to the existing manually controlled release workflow. It requires a version change with `release-intent.enabled=true` in the exact main commit, a successful complete Android CI run, an approved non-draft PR whose merge commit is that exact main commit, and aligned release metadata/version ledger before the job can request the `mfi-public-release` Environment. Ordinary website/documentation commits do not satisfy the intent gate. Release and follow-up workflows use explicit correlated `workflow_dispatch` calls rather than relying on a `GITHUB_TOKEN`-generated downstream push to trigger another workflow. The checked-in v1.1.52 intent remains disabled.

The Pages workflow and backend were locally exercised against the three actual public Releases: Stable resolves to `v1.1.51`; Beta is hidden because no verified Beta APK proof is available. Production OTA output remains unavailable by design: the checked-in app trust store is empty, the production key/Environment is not configured, and missing signing inputs produce no feeds. Website deployment, cloud CI for the local changes, production signer preflight, and vehicle installation have not been verified online or in a vehicle.
