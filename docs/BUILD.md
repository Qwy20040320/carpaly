# Build DiPlay / CarPaly

> **CarPaly fork note:** the root [README](../README.md) is the current user-facing feature and compatibility guide. Every user APK must be the Release variant signed by the certificate assigned to its versionCode signing epoch in the version ledger, use application ID `com.shihab.diplay.hudtest`, and be named `CarPaly-XingyueL-v{versionName}.apk`. Debug compilation is permitted only for internal CI/source checks; no Debug/Test/Upgrade-Test APK is a user deliverable. Release builds fail closed if the required signer or runtime authentication assets are unavailable. After verification, candidate artifacts are copied—not moved—to the primary checkout's ignored `artifacts/v{versionName}` directory.

The procedures below retain the upstream DiPlay module layout and source-build workflow; vehicle-specific claims apply only where explicitly labeled.

Use this procedure to build the DiPlay app for an Android head unit.
Run the commands from the repository root, where `gradlew` and `settings.gradle.kts` are located.

## Select the application

This repository contains several Android applications.
Select `mobile` to build the main DiPlay app.

| Gradle module | Purpose | Internal Debug build output (not a user deliverable) |
| --- | --- | --- |
| `:mobile` | Main DiPlay app for Android head units | `mobile/build/outputs/apk/debug/mobile-debug.apk` |
| `:maphost` | Sample application that displays a map from DiPlay | `samples/maphost/build/outputs/apk/debug/maphost-debug.apk` |
| `:home` | Optional DiPlay Home launcher | `samples/home/build/outputs/apk/debug/home-debug.apk` |
| `:automotive` | Separate Android Automotive application inherited from xcertplay | `automotive/build/outputs/apk/debug/automotive-debug.apk` |

The `:common` and `:shared` modules are libraries.
The applications use these libraries.

If the installed app is **DiPlay map host**, you selected `:maphost` or its APK.
Build `:mobile` and select `mobile-debug.apk` to install the main app.
A command such as `./gradlew assembleDebug` can build more than one application.
Use the module name in each build command to select the required application.

## Prepare the build environment

Install these tools:

- JDK 25.
- Android SDK Platform 37 (`platforms;android-37.0`).
- Android SDK Build-Tools 36.0.0.
- Android SDK Platform-Tools.
- Android NDK 28.2.13676358.

Use the Gradle wrapper included in this repository.
The first build needs an internet connection to download dependencies.

1. Open the repository root in Android Studio.
2. Install the Android SDK packages with **Tools → SDK Manager**.
3. Set **Gradle JDK** to JDK 25 in the Android Studio Gradle settings.
4. Wait for Gradle sync to finish.

For a terminal build, set `JAVA_HOME` to your JDK 25 directory.
Set `ANDROID_HOME` to your Android SDK directory.
You can also specify the SDK directory in the root `local.properties` file:

```properties
sdk.dir=/absolute/path/to/Android/sdk
```

Keep `local.properties` outside Git.
Check the Java version before the build:

```sh
java -version
```

The output must identify Java 25.
On Windows, use `gradlew.bat` in place of `./gradlew` in the commands below.

## Build the main app

For a source build without runtime authentication assets:

```sh
./gradlew :mobile:assembleDebug
```

Check that this file exists:

```text
mobile/build/outputs/apk/debug/mobile-debug.apk
```

The debug application ID is `com.shihab.diplay.hudtest`.
The CarPaly branch keeps the application ID `com.shihab.diplay.hudtest` for Debug and Release variants so a correctly signed upgrade does not change package identity.

The source APK contains no accessory identity unless you supply runtime authentication assets.
Standalone CarPlay needs these assets to connect to an iPhone.
Use the car-test procedure below for that purpose.
Tests generate synthetic identities at runtime.
Keep test private keys outside Git.

### Use Android Studio

1. Open **Run → Edit Configurations**.
2. Select an **Android App** configuration, or create one.
3. Set **Module** to `mobile`.
4. Select this configuration in the toolbar.
5. Select the Android device.
6. Click **Run** to install the main debug app.

To build an APK without installation, run `:mobile:assembleDebug` in the Android Studio terminal.
Select the APK from the `mobile` output directory.

## Check the source build

Run the unit tests, lint checks, and main debug build:

```sh
./gradlew :shared:testDebugUnitTest :common:testDebugUnitTest :mobile:lintDebug :mobile:assembleDebug
```

Check that Gradle reports `BUILD SUCCESSFUL`.
For the complete CI procedure, see [the Android workflow](../.github/workflows/android.yml).
That workflow also checks and builds the `home` and `maphost` applications.

## Build a CarPaly user APK

CarPaly intentionally has no standalone authenticated Debug or Upgrade-Test packaging task. To build an authenticated Release candidate, prepare an external directory containing exactly `offline-mfi/identity.pk8` and `offline-mfi/certificate.p7b`; keep it outside Git. Supply a PKCS12 Release keystore whose certificate matches the active version's `signerCertificateSha256` in the version ledger:

| Variable | Value |
| --- | --- |
| `DIPLAY_AUTH_ASSETS_DIR` | Absolute path to the runtime assets directory |
| `ANDROID_KEYSTORE_PATH` | Path to your Android signing keystore |
| `ANDROID_KEYSTORE_PASSWORD` | Keystore password |
| `ANDROID_KEY_ALIAS` | Signing key alias |
| `ANDROID_KEY_PASSWORD` | Signing key password |

Keep the keystore and passwords outside Git. Run the canonical build script, which invokes `:mobile:assembleRelease`, verifies all inputs and the ledger-pinned signer, and refuses to overwrite existing artifacts:

```sh
powershell -ExecutionPolicy Bypass -File .\scripts\build-release-apk.ps1
```

The worktree-local candidate is first staged under `artifacts/v{versionName}/CarPaly-XingyueL-v{versionName}.apk`; after canonical signature, package, version and hash verification, `scripts/artifact_delivery.py` copies it into the primary standard checkout's ignored `artifacts/v{versionName}` folder. The primary checkout is resolved from Git's shared worktree metadata and expected repository identity, not by rewriting path strings. Set `CARPALY_PRIMARY_PROJECT_ROOT` only when automatic discovery is unavailable; the selected directory is still validated against the same Git common directory and remote. Delivery fails closed on path redirection, non-ignored destinations, missing proof, or conflicting same-name files. The source worktree candidate remains intact. The APK embeds the explicitly selected runtime identity, which recipients can extract, but never includes the Android signing keystore. v1.1.53/code 41 uses a new signing epoch and cannot update v1.1.52 or earlier in place; do not uninstall an older install until the user has decided how to preserve its data.
See [the project notices](THIRD_PARTY_NOTICES.md) for the experimental identity used in public releases.

The public source archive matches the release tag.
It excludes runtime identities, signing keys, local configuration, and build output.
The retired `build-beta.py` helper is no longer part of the build procedure.

## Correct build problems

| Symptom | Action |
| --- | --- |
| Installed app is DiPlay map host | Select `mobile` in Android Studio. Build and install the APK from the `mobile` output directory. |
| Gradle cannot find the Android SDK | Set `ANDROID_HOME` or the `sdk.dir` value in `local.properties`. |
| A required SDK or NDK package is absent | Install the listed package with SDK Manager. |
| Java or Gradle JDK version is incorrect | Set the terminal JDK and Android Studio Gradle JDK to Java 25. |
| CarPaly Release build reports missing authentication files | Check that `DIPLAY_AUTH_ASSETS_DIR` points to a parent containing `offline-mfi/identity.pk8` and `offline-mfi/certificate.p7b`. |
| CarPaly Release signer is unavailable or mismatched | Stop with `BLOCKED`; recover only the key assigned to the version's signer epoch. Never fall back to Debug signing. |
| Android rejects a v1.1.53 update to v1.1.52 or older | The v1.1.53 signer changed, so Android cannot install it as an in-place update. Keep the old app and its data unless the user explicitly chooses a fresh-install migration after data review. |
