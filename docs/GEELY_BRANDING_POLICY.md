# CarPaly Geely branding policy

The default vehicle brand shown by CarPaly is permanently `GEELY`, with the packaged Geely icon. Do not make BYD the target brand or default label. Preserve user-selected vehicle names and icons when migrating old defaults; migrate only values that are demonstrably the old built-in default.

Existing regression coverage includes `HeadUnitProfileTest`, `AudioChannelPersistenceTest`, and `CarButtonImagePickerTest`. Keep those behaviors under automated test. Do not mechanically rename BYD/iAP2 identifiers, generic transport behavior, upstream notices, or unrelated third-party code. Vehicle-specific output must stay capability-gated and must not issue unverified CAN/UDS writes.

BYD wheel-key codes are historical defaults and are not evidence for the KX11. On a detected or manually selected Geely profile, preserve saved user-learned key mappings but do not apply those BYD codes implicitly; the driver must explicitly learn any actual Geely key events. Unknown OEM button behavior remains unclaimed.

The current software tests verify branding/default migration and selected audio behavior only. They do not prove the real Geely vehicle's CarPlay connection, phone audio, Siri, microphone, steering controls, HUD, instrument cluster, reverse camera, or sleep/wake integration. Those remain `NOT_TESTED` until the user supplies vehicle-test evidence.
