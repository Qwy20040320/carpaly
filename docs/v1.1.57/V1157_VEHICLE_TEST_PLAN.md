# V1.1.57 parked-vehicle verification plan

All steps below are pending. No vehicle or iPhone was connected or operated for this candidate.

## Safety and baseline

- Use the 2024 Geely Xingyue L Tianji edition only while safely parked in P with the parking brake set.
- Record Android build/API level and the installed CarPaly version from the app's diagnostics; redact VIN, serials, Bluetooth/Wi-Fi identifiers and personal data before sharing logs.
- Do not uninstall the installed app, clear data, change signer, grant unknown OEM privileges, send vehicle-bus writes, or change head-unit configuration as a diagnostic shortcut.
- Confirm any candidate is signed compatibly before considering installation. Current V1.1.57 delivery is blocked by the verified signer-policy mismatch documented in `V1157_BUILD_REPORT.md`.

## P0: wired attach and startup

1. Connect iPhone by USB and note which prompt appears (Android “open with” / USB access, app permission, VPN consent, or another named prompt); do not infer from the prompt's appearance alone.
2. If the user explicitly accepts the normal prompt, note whether the CarPaly host activity opens.
3. If it opens, wait for the stage sequence: wired host → Android VPN consent result if shown → display/startup readiness → iPhone discovered → USB permission → configuration selection/re-enumeration → USB data paths → iAP2/authentication → NCM/AirPlay → first frame.
4. If it stops, export diagnostics immediately and preserve timestamps. The expected new fields include attach delivery, `CarPlay startup gated reason=...`, VPN consent result, and controller status-class transitions.
5. Test a disconnect/reconnect only after recording the first failure and without changing permissions or application data.

## P0: audio

- Verify music stays active beyond one second, then test navigation prompt and music duck/restore.
- Record selected stream/codec, decoder candidate and stage, input queued/output-buffer counters, AudioTrack creation, AudioFocus transitions and available output device.
- Verify Siri and microphone separately. Do not treat a successful Siri interaction as proof that navigation audio or OEM speaker routing works.
- For OPUS, confirm not just candidate instantiation but successful configure/start, queued packets, PCM output, AudioTrack writes and audible output. The code fallback alone is not a vehicle pass.

## P0: display and touch

- Record negotiated canvas, window viewport, status/navigation insets, OEM strip visibility, video content bounds and shared touch transform.
- Verify the top strip does not cover actionable CarPlay content and touches land at the visible video coordinates.
- Do not force-hide OEM UI or change resolution if the display owner does not permit it.

## P1: stability and vehicle-specific controls

- Test idle-to-active, phone unplug/replug and head-unit sleep/wake only in a parked state; record bounded recovery behavior.
- Verify media/voice steering keys only if the vehicle supports them; record received standard Android events without inferring ECARX key codes.
- Keep HUD, DIM/cluster, fuel, climate, CAN/vehicle writes and additional displays `NOT_TESTED` unless the corresponding service, permission and output are directly observed.
- Ensure reverse-camera / 360 view remains undisturbed; do not trigger maneuvers or interact with unknown controls for this test.

## Evidence threshold

`REAL_CARPLAY_CONNECTED=YES` requires a real iPhone, a completed protocol session and an operable CarPlay frame with matching runtime evidence. Vehicle audio, touch, steering, HUD, cluster, fuel, climate and camera-priority results are separate fields and may not inherit that status.
