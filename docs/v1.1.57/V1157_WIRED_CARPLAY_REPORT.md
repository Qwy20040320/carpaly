# V1.1.57 wired CarPlay connection trace

## Reported event

The user reports that the head unit detects an iPhone USB connection, a confirmation prompt is accepted and closes, but CarPlay does not appear to launch. No contemporaneous V1.1.57 device log or USB trace was supplied for this event. The root cause is therefore `UNKNOWN`.

## Source path found

1. Android declares `CarPlayHostActivity` for `USB_DEVICE_ATTACHED` and filters Apple USB vendor devices in `common/src/main/AndroidManifest.xml` and the USB device filter resource.
2. The home action and settings action labeled `Connect with USB` call `DiPlayActivity.connect(false)`. That method saves wired mode and proceeds to `openProjection()` (after stopping an existing background session if necessary); `openProjection()` launches `CarPlayHostActivity`. The button is not a modal confirmation and does not itself establish a session.
3. `CarPlayHostActivity.onCreate()` and `onNewIntent()` recognize the initial or subsequent Apple USB attach and call `requestStartupPrerequisites()`.
4. Wired startup uses `requestVpnConsent()`. A denied/unavailable VPN consent remains blocked; the callback logs the result. Microphone permission resolution and optional location permission are also checked before startup.
5. `maybeStartCarPlay()` evaluates the display surface, transport, location, microphone, settings-menu, teardown/resize, and existing-controller gates. It now emits a deduplicated `CarPlay startup gated reason=...` entry rather than silently returning.
6. When gates are clear, `startCarPlay()` creates `CarPlayController`, starts `DiPlaySessionService`, and calls `next.start()`.
7. `CarPlayController` discovers the Apple USB device, requests Android USB permission, handles the permission receiver plus polling fallback, requests configuration re-enumeration where needed, opens USBMUX/iAP2 data paths, invokes the configured MFi authentication path, attaches NCM/AirPlay, and reports controller/session/video/audio events through existing diagnostics.

## Confirmation prompt identification

No dedicated app-owned “confirm wired CarPlay connection” dialog was found in the normal `Connect with USB` path. The only matching app-owned USB confirmation-style prompt in `DiPlayActivity` is `promptEnableUsbAutoConfirm()`; its positive button invokes `autoApplyPermissions()`, a separate ADB/accessibility/overlay permission setup operation. It does not invoke `connect(false)` or `openProjection()` and is not Android's `UsbManager.requestPermission()` prompt. The reported on-vehicle prompt could therefore be an Android/system prompt or a different build/flow; its identity is `UNKNOWN` without a contemporaneous screen/log capture.

The source contains an app-owned “auto apply permissions” dialog, but it belongs to an explicit ADB/accessibility/overlay setup action. It is not the iPhone USB-permission dialog and is not called by the normal wired connect path. The normal wired connect path can still surface Android/system permission or device-resolution UI. The user's word “confirmation” does not identify which prompt was shown.

## Instrumentation added in this branch

- Record the app's wired/wireless connect request and host-activity launch request without recording device identifiers.
- Record USB attach delivery to the host.
- Record Android VPN-consent result as granted/not granted.
- Record the controller status class (for example, waiting for iPhone, requesting USB permission, selecting configuration, or opening data paths).
- Replace previously silent startup prerequisite returns with a deduplicated reason code and sanitized readiness state. Reasons include missing display surface, unresolved transport permission, location/microphone permission, active settings menu, pending teardown/resize, or an existing controller.

These are diagnostics and observability improvements; they do not change or bypass Android's USB, VPN, MFi, or OEM permission checks.

The regular wired route is logged as `CONNECT_REQUESTED` / `HOST_ACTIVITY_LAUNCH_REQUESTED`; the source has no application-owned wired-confirmation dialog to truthfully emit `WIRED_DIALOG_SHOWN` or `WIRED_CONFIRM_CLICKED` for. No synthetic dialog events were added.

## Status by stage

| Stage | Source status | Runtime evidence for the reported failed wired attempt |
| --- | --- | --- |
| USB attach dispatch | Implemented | Not supplied |
| Host/activity launch | Implemented | Not supplied |
| Startup prerequisites | Implemented; reason logging added | Not supplied |
| Android USB device permission | Implemented through `UsbManager.requestPermission` and result/polling paths | Not supplied |
| iPhone configuration selection / USBMUX | Implemented | Not supplied |
| iAP2 / MFi / NCM / AirPlay | Implemented in the current code path | Not supplied for this wired event |
| Video, touch, audio, disconnect/reconnect | Implemented code paths, each requiring runtime verification | Not supplied for this wired event |

“Implemented” describes source code only. It is not a claim that a head unit accepted the flow or that CarPlay connected.

## Required next evidence

On a safely parked vehicle, export the app's diagnostic report immediately after a single wired attempt. Preserve timestamps and the sequence from `CONNECT_REQUESTED` / `HOST_ACTIVITY_LAUNCH_REQUESTED` through the last `CarPlay controller stage` or `CarPlay startup gated` event. Redact VIN, serial numbers, Bluetooth/Wi-Fi identifiers, tokens, and personal data before sharing. Do not change permissions, reinstall, clear data, or repeat connection attempts solely for this report unless the user explicitly chooses to do so.

`REAL_WIRED_CARPLAY_STATUS=NOT_TESTED_IN_THIS_REVISION`

`WIRED_FAILURE_ROOT_CAUSE=UNKNOWN`
