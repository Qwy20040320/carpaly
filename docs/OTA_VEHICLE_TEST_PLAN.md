# CarPaly OTA vehicle acceptance plan

This checklist is for a stationary 2024 Geely Xingyue L Tianji head unit. Do not test while driving. No item is marked PASS until the physical action is observed and recorded.

## Preconditions

- [ ] Confirm vehicle is in P, parking brake is set, and the test area is safe.
- [ ] Record head-unit Android version, build fingerprint (redact serial/VIN), model/trim, and time-zone/time offset.
- [ ] Record installed CarPaly version/versionCode and its signer certificate SHA-256 without collecting private keys.
- [ ] Confirm the update APK came from the CarPaly GitHub Release and compare the published SHA-256.
- [ ] Confirm current and candidate `applicationId` are `com.shihab.diplay.hudtest` and candidate versionCode is greater.
- [ ] Confirm each APK uses the signer assigned to its versionCode in `config/android-version-ledger.json`; v1.1.53/code 41 uses a different signer than v1.1.52/code 40 and cannot update it in place.
- [ ] Confirm the production OTA manifest trust key has been shipped in the installed app and its key id is active. Until then, update checking is expected to fail closed.
- [ ] Stop CarPlay before installer launch. Do not test update installation during music, navigation, phone, Siri, or reversing-camera use.

## Stable/Beta discovery

- [ ] On Stable (default), verify the page shows installed version/code, stable update channel, release version/code/date, notes, APK size, and available actions.
- [ ] Confirm a draft, unverified asset, wrong signer, expired/invalidly signed manifest, and beta-only version are never offered by Stable.
- [ ] Manually enable Beta and verify the beta catalog is independent; switch back to Stable and confirm preference persists across process restart.
- [ ] Disable automatic checks and confirm no background HTTP request occurs on app launch. Enable it and confirm checks are throttled and do not acquire audio focus.
- [ ] Exercise offline/timeout/HTTP 404/403/429 and malformed manifest behavior; app remains usable and old published page/manifest remains unchanged.

## Download and integrity

- [ ] Download only after explicitly tapping Download; verify progress and final file size.
- [ ] Cancel once during transfer; verify the partial file is removed and CarPlay/UI responsiveness is preserved.
- [ ] Interrupt network once, reconnect, and record whether a clean retry is possible. Current implementation does not claim Range resume.
- [ ] Test insufficient storage, unexpected redirect, wrong sidecar, wrong size, wrong SHA-256, and untrusted redirect host; each must fail without exposing an installer.
- [ ] Confirm a completed file is in the app-private update cache and has exact package, versionName, versionCode, and fixed Release signer.
- [ ] Confirm the APK contains the required runtime authentication resources, but do not export or copy them.

## Installer and upgrade

- [ ] With CarPlay active, tap Install; installer launch must be blocked with a clear message.
- [ ] With vehicle motion state unavailable, verify the app explicitly asks for stationary confirmation and describes P/parking brake/CarPlay stop requirements. This is a user attestation, not a vehicle sensor reading.
- [ ] Deny “install unknown apps” permission if prompted; verify the app offers Android's official authorization page and returns safely.
- [ ] Cancel Android's package installer and verify the existing version/settings remain unchanged.
- [ ] Approve the same-signer, higher-version update; record OS installer result. Do not uninstall the existing app or clear data.
- [ ] On first launch after the system installer closes/restarts the app, verify the new version is displayed and existing settings remain intact.
- [ ] Reconnect wired and wireless CarPlay separately; verify startup, video/touch, music, navigation guidance, Siri/microphone, and reconnect behavior. Do not equate a successful APK install with CarPlay acceptance.
- [ ] Verify status bar/left OEM dock do not obscure critical update UI and that update/install prompts never cover reversing camera or active calls.

## Evidence to return

Provide the exact app version before/after, installer outcome, test timestamps, channel, release tag, redacted update log, screenshots only if permitted by vehicle privacy policy, and a checklist outcome per row (`PASS`, `FAIL`, `BLOCKED`, or `NOT_TESTED`). Do not send VIN, account tokens, identity files, private keys, contacts, or unrelated logs.

### Current baseline

All OTA vehicle checklist items remain `NOT_TESTED`. The earlier user report that the head unit can open an APK installer is `USER_REPORTED_SUPPORTED`, not proof that installation, in-place upgrade, settings migration, or CarPlay runtime works. The installed v1.1.51 predates a provisioned OTA trust root and cannot securely bootstrap itself through the new OTA client.
