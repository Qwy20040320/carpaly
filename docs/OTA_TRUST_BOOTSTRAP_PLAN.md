# CarPaly OTA Trust Bootstrap Plan

## Trust contract

CarPaly OTA envelopes use ECDSA P-256 with SHA-256. The publisher serializes payload JSON as UTF-8 with sorted keys, compact separators, non-ASCII characters preserved, and NaN/Infinity forbidden. The exact canonical byte sequence is Base64-carried in `signedPayload`; Android verifies those bytes directly before parsing, so Java/Kotlin JSON reserialization is not part of the signature protocol. The envelope key ID and signed payload key ID must agree.

The app pins X.509 SPKI DER public keys in `common/src/main/res/raw/ota_manifest_public_keys.json`. Python and Android both require the exact `SHA256withECDSA-P256` algorithm label and the named P-256 parameters. Key IDs must be unique and match `[A-Za-z0-9._-]{1,64}`. Unknown, revoked, malformed, duplicate, wrong-curve, or incorrectly signed keys are rejected. Stable/Beta channel, canonical GitHub asset URLs, package ID, version metadata, APK SHA-256, signer certificate fingerprint, dates, and size limits are inside the signed payload.

## First install is a manual trust bootstrap

The currently checked-in production trust store is empty. Empty means OTA updates are unavailable, not unsigned. The existing v1.1.52 candidate therefore is not a production OTA bootstrap package. An already installed client that does not pin the new key cannot safely learn that key from `stable.json`, `beta.json`, the website, or any other ordinary HTTPS response.

After production identity approval, the first bootstrap requires a new audited Release APK that includes the public key, retains `applicationId=com.shihab.diplay.hudtest`, uses the fixed Android signing identity, and advances the immutable version ledger. Install that APK through a trusted human-confirmed channel. Verify that the installed client loads the key and rejects a modified signature, unknown key ID, wrong channel, stale manifest, downgrade, wrong APK digest, package, or signer. Only then may an approved operator publish signed production feeds.

Do not assume root access, silent installation, or a successful car-install flow. A user must confirm Android's standard installer. Vehicle installation and in-place upgrade remain `NOT_TESTED` until the user verifies them on the car.

## Rotation states

1. Ship a reviewed app that pins the new key as `active`, while keeping the current key `active` or `retiring` for a bounded migration interval.
2. Confirm that intended clients have updated through a trusted package channel.
3. Switch the publisher to the new key ID only after its Secret/public-key match has been verified offline and in protected CI.
4. Ship a later app that marks the old key `revoked` or removes it. Never make the new key active remotely before clients pin it.
5. Keep key IDs immutable. Do not overwrite an existing ID with another public key.

The app replay guard stores the greatest accepted `issuedAt` and payload digest independently per channel. An older timestamp or different content reusing the same timestamp is rejected; an identical payload is idempotent. This is best-effort state in app preferences, not a hardware monotonic counter: clearing app data/reinstall resets it. Independent anti-downgrade checks still require a higher `versionCode` and matching Android signer.

## Release-before-feed ordering

Publish and download-verify the APK and checksum first. Validate the Release metadata and exact source commit, then sign Stable/Beta payloads that reference those immutable assets. Rebuild the Pages site from the same verified release snapshot, verify the signed feed and current deployed feeds, and deploy through the serialized `carpaly-pages` concurrency group. A missing, expired, untrusted, malformed, redirecting, or invalidly signed existing feed blocks the whole site deployment; never replace it with an empty feed on an ordinary site update.

If production verification fails, stop before Pages deployment and leave the current deployed site/feed untouched. Feed loss or signing-key compromise requires a trusted app update or a trusted manual APK installation; never bootstrap replacement trust from an unsigned feed.
