# Release Draft workflow boundary

The authenticated publisher in `.github/workflows/android.yml` is the only path that may create the version tag and metadata-only Release Draft, and only after an explicitly enabled same-commit intent on protected `main`, full CI, version/source checks, exact merge authorization and signer preflight. `release-intent.enabled=false` remains the baseline. The Android build verifies/signs internally but the public workflow does not upload an APK or Actions artifact containing the APK.

The local `build-release.ps1 -PrepareDraft` mode only reads and validates an existing Draft, tag target, main commit, release intent, CI, APK verification report/checksum and zero-asset condition. It cannot create a tag or draft, patch hand-written notes, upload binaries or publish. Existing published Releases are immutable. Draft creation is idempotent in `.github/scripts/prepare-release-draft.sh`; an existing draft is reused only if tag, source, channel, managed marker and empty asset list match.

Never treat a metadata-only Draft as an installable download. Public APK distribution remains blocked until the embedded authentication identity's distribution rights and a safe distribution design are independently approved. OTA remains disabled and is not a side effect of Draft preparation.
