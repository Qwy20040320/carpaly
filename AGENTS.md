# AGENTS.md

Instructions for coding agents that work on CarPaly, a community project derived from DiPlay.

## Checks

Run the CI command from `.github/workflows/android.yml` before you report a change as done:

```sh
./gradlew :shared:testDebugUnitTest :common:testDebugUnitTest :home:testDebugUnitTest \
  :mobile:lintDebug :home:lintDebug :maphost:lintDebug \
  :mobile:assembleDebug :home:assembleDebug :maphost:assembleDebug
```

Set `ANDROID_HOME` or `local.properties` if Gradle cannot find the SDK.

## Adding or moving a setting

The Settings screen is grouped by driver goal, not by implementation.
`SettingsCategory`, `SettingsSection` and `SettingsInformationArchitecture` at the top of
`common/src/main/java/com/shilapi/xcertplay/DiPlayActivity.kt` define the groups.
`SettingsLayoutPolicyTest` fails when a section has no category or has more than one.

### Choose the category

Ask which goal the driver has when they look for the setting. Use the first row that fits.

| Category | Put a setting here when it controls… | Examples |
| --- | --- | --- |
| Connection | how the iPhone connects and how DiPlay starts | connection setup, connect on open, start with the car, USB permissions, car hotspot automation, iPhone choice, Android permissions |
| Display | how CarPlay looks on the head-unit screen | day/night mode, picture, size, resolution, frame rate, dock, system bars, multi-window resolution |
| Audio | what the driver hears | media and navigation streams, music buffer |
| Navigation | location and turn-by-turn guidance | location to iPhone, BYD HUD and cluster guidance |
| Vehicle | how CarPlay fits this car and its driver | driving side, wheel keys (Siri, BYD joystick and map zoom), car button, gestures that conflict with the head unit |
| Diagnostics | troubleshooting evidence | diagnostic reports |
| Advanced | experimental, firmware-specific or risky behavior | dashboard map, split screen, screen rotation, side panel, HEVC video, audio focus, audio channel mapping, buffered music, vehicle data |
| Overview | nothing new | see "Overview" below |

A setting goes to Advanced when it is experimental, depends on specific firmware, or is an opt-in that can break sound, video or the connection on some head units.
A control that fixes a common problem and is safe at its default (for example the audio stream choice) stays in its category.
Exception: a gated control that only its own audience sees, and that completes an everyday goal, stays in that goal's category.
Example: auto car hotspot needs ADB but appears only for car-hotspot users, so it is in Connection.

Mark an experimental setting or card with the title suffix ` (experimental)`, never `· experimental`, a dash, or an `Experimental …` prefix.
Each locale MUST use its existing form: `(تجريبي)`, `(experimental)`, `(экспериментально)`, `(експериментально)`, `（实验性）`, `（實驗性）`.

### Add the code

1. To extend an existing card, add the control inside the `filteredSection(...)` block of a card in the correct category.
2. For a new card, add a `SettingsSection` entry and map it to exactly one category in `SettingsInformationArchitecture.sectionsByCategory`.
3. Build the new card with `filteredSection(content, SettingsSection.X, …)` inside `allSettingsSections()`.
   A plain `section(...)` call there MUST NOT be used: it renders on every category page.
4. A setting MUST NOT appear in two categories.
   Overview quick settings are the only duplicates. They MUST use the same persistence as the full control. Overview SHOULD NOT have more than four quick settings.
   A header shortcut MAY duplicate a Display setting when it uses the same persistence.
5. If the change reconnects CarPlay or applies at the next connection, the description MUST say so.
   A setting that only takes effect at the next connection MUST call `markReconnectNeeded()` after it saves.
   This shows the "Reconnect now" bar. It MUST NOT drop a running session without the driver's consent.
   Reconnect at once (`reconnectIfRunning()`) only after a dialog button that says "Apply and reconnect", or when the description says that the change reconnects CarPlay.
6. Add each new string to `common/src/main/res/values/` and to every `values-xx` locale folder.
   New Settings copy SHOULD use the `settings_` prefix. `SettingsTranslationsTest` fails when a `settings_*` string has no translation.
7. A control that opens a choice uses `button()` with the text `"Title · Value"`.
   That form renders as a setting row with the value and a chevron, and Search indexes the title.
8. When you move a control between categories, update `AdaptiveSettingsUiTest.settingsLiveWhereDriversLookForThem`.

### Overview

Overview holds the connection status, links to the categories, quick settings, About and Language.
Do not add a new setting to Overview. Add it to its category. Then promote it to quick settings only if drivers change it often.

## CarPaly packaging guardrails

Before changing Android packaging, version allocation, or default vehicle branding, read the policies:

- `docs/RELEASE_SIGNING_POLICY.md`
- `docs/VERSIONING_POLICY.md`
- `docs/GEELY_BRANDING_POLICY.md`

Every user-installable APK must use the Android Release build type, fixed package ID `com.shihab.diplay.hudtest`, and canonical name `CarPaly-XingyueL-v{versionName}.apk`. The immutable ledger defines signer epochs: versionCodes 36–40 use the historically verified `4d26d1c861b41a2cee4515e31f5f5c7eb13b9dd06e7485aa1687bc1d2ac73d90`; versionCode 41 onward uses the active verified `d9b329525fc1ef21c365fab72c10367527cc038297c4f30eaa22b2207429139e`. Never re-sign historical APKs or infer that cross-epoch in-place upgrades work; require Android signature lineage or a device test before claiming that. All new allocations must use the ledger-selected epoch and strictly increase versionCode. CI may compile Debug internally, but never upload Debug APK artifacts or deliver Debug/Test/Upgrade-Test packages. If the expected signer is unavailable, mark delivery BLOCKED; never substitute a key, change package ID, uninstall an older version, clear user data, or overwrite a delivered APK. A tag and Release may be created automatically only by the authenticated publisher after successful main-branch CI and an enabled, reviewed `config/release-intent.json` changed by that same main commit; ordinary pushes, pull requests, and tag pushes never publish. The source commit, latest published-source baseline, ledger, Gradle version, signer, APK, and existing tag/asset checks remain mandatory. CarPaly's default vehicle label and icon remain GEELY; retain legacy BYD support only behind its existing feature gates and never infer Geely event codes from BYD data. Run `python scripts/android_versioning.py check` and the CI command above.

The reviewed public Markdown set is the exact list in `config/public-markdown-allowlist.json`. `.gitignore`, public-tree validation, and source ZIP packaging must use the same allow-list. Never track local authorization records, vehicle-test reports, generated task logs, or other Markdown absent from that manifest. Keep APKs, authentication material, keystores, passwords and private diagnostic logs out of Git and source archives.

Version status is recorded by `config/android-version-ledger.json`. The ledger records allocations through v1.1.52/code40 and verified public releases v1.1.53/code41, v1.1.54/code42, and v1.1.56/code44; v1.1.55/code43 remains `SOURCE_UNVERIFIED`. GitHub also currently reports v1.1.52 as a published formal Release, but its hand-written notes say Beta/pre-release and it lacks matching APK verification evidence; preserve that Release and disclose the conflict rather than treating it as verified. The current main source is behind the v1.1.56 source baseline and its local version metadata is below the public high-water mark; strict Release build must remain blocked until the reviewed source/version line is reconciled. The ledger's `test` channel labels the allocation stage only, never the APK build type or signing key.
