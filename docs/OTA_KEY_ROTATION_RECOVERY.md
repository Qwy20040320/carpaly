# CarPaly OTA Key Rotation and Recovery

## Normal rotation

- Generate and review the new key only under separate production authorization. Give it a new stable key ID and record the public SPKI SHA-256.
- Add the new public key to a reviewed app release before signing a production manifest with it. During transition the client may trust both keys, each with an explicit `active` or `retiring` state.
- Verify a non-production cross-language signature vector, the app trust-store parse, exact key ID, channel, freshness, replay floor, APK hash, package ID, version, and pinned Android signer.
- Configure the OTA Environment to use the new key only after that bootstrap app is installed by the intended user population.
- Revoke/remove the prior key in a later trusted app release after transition. Retiring keys are accepted only during the explicit overlap; revoked keys are not accepted.

## Incident actions

| Incident | Immediate containment | Recovery path |
| --- | --- | --- |
| Private OTA key suspected leaked | Stop signing and deployments; revoke the GitHub Environment Secret; preserve logs and access records. Do not publish a replacement feed. | Create a newly authorized key, ship its public key in a trusted signed Android Release APK, install it through a human-confirmed trusted channel, then resume with a new key ID. |
| Private key lost or backup unreadable | Keep OTA publishing disabled. Do not infer a replacement from the public key. | Follow the same trusted APK bootstrap with a newly authorized key. Existing clients cannot learn a new root from the old unsigned network path. |
| Secret/Variable mismatch | Fail closed; compare the configured key ID and public fingerprint to reviewed client trust material without reading Secret plaintext. | Re-enter the correct Secret through an approved protected workflow; run an explicitly approved signer-only/test preflight before any production signing. |
| Manifest signature, channel, time, or replay validation fails | Stop deployment; preserve the last known-good feed. Never disable signature/freshness/replay checks. | Rebuild from verified Release metadata, correct the signed data, and redeploy only after verification. If a deployed feed is suspect, use an already trusted signing identity to publish a corrected higher-issued-time feed. |
| Feed missing, corrupt, or site deployment fails | Do not deploy a replacement site that drops the feed. Pages workflow must reject an unverifiable prior feed. | Restore byte-identical verified feed/site state from trusted Release history; verify signatures and checksums before redeploy. |
| Android APK installation fails | Do not uninstall the working app, clear its data, or promise silent rollback. | Keep the currently installed version; diagnose package, `versionCode`, signer lineage, storage and installer authorization; retry only with a verified compatible APK. |
| Android Release certificate mismatch | Stop distribution and OTA; preserve the installed app and user data. | Recover the original authorized signing identity. Do not accept a new certificate merely because the manifest names it. If original signing identity is irrecoverable, report blocked and plan a user-visible migration separately. |
| Client is too old to trust new key | Do not make the feed unsigned or publish it under an unknown key. | Deliver the trust-bootstrap APK over an existing trusted manual channel, then resume OTA. Long-offline clients may need the same manual install. |

## Revocation and rollback boundaries

Revocation is delivered inside a reviewed app trust-store update; it cannot be pushed to old clients through an untrusted feed. Keep prior keys only for a documented, bounded transition. Avoid lowering `issuedAt`, `versionCode`, or the app signer. A cleared app-data directory resets the preference-backed replay marker, so replay defense also relies on expiry, installed package/version/signer checks, immutable release asset verification, and operational release history.

No recovery path uses root, a hidden install API, unknown vehicle Binder/CAN commands, unsigned JSON, or an arbitrary server-provided key.
