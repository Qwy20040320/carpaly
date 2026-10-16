# V1.1.57 code changes in this candidate

This report covers local candidate-source changes only. No APK was signed, installed, or released in this task.

## OPUS decoder fallback

`shared/src/main/java/com/shilapi/xcertplay/media/MediaCodecStartup.kt` now provides a sequential candidate startup helper. It releases a decoder instance if configuration or startup fails, preserves earlier failures as suppressed exceptions, and does not convert VM/linkage `Error`s into recoverable fallback attempts.

`AndroidMediaSink.kt` keeps `MediaCodec.createDecoderByType()` first. For OPUS only, after the default candidate fails, it tries other Android `MediaCodecList` decoder names, preferring platform-reported software decoders. Failed candidates are released. AAC keeps the original default decoder path. Logs record candidate name, stage and exception class only; no audio payload is logged.

This can recover devices where the default codec factory fails but an explicitly named listed decoder works. It does not provide a decoder when none can be instantiated, and it has not been exercised on the target head unit. It does not establish that a successfully configured decoder produces audible output through the OEM audio route.

## Wired startup diagnostics

`CarPlayStartupGate` makes the first unmet startup prerequisite explicit and unit-testable. `CarPlayHostActivity` logs a changed blocker once until readiness changes, plus sanitized transport, permission-resolution and surface state. The host now records USB attach, VPN-consent result, and controller status-class transitions. `DiPlayActivity` records connect and host-launch requests without sensitive device data.

The change does not automatically retry after a denied permission, suppress Android dialogs, manufacture a USB grant, bypass VPN/MFi authorization, or change transport protocol behavior.

## Protocol audio classification diagnostics

The current candidate separates diagnostic classification from the existing
compatibility routing decision. Explicit protocol labels `media`, `navigation`,
`speechRecognition`, `telephony`, and `system` are recorded as MUSIC,
NAVIGATION, SIRI, CALL, and SYSTEM. Missing labels and ambiguous/unmapped labels
such as `default`, `alert`, and `compatibility` are recorded as UNKNOWN, with
the classification basis included in logs. The prior routing mapper and its
fallback behavior are intentionally unchanged, so this improves evidence but
does not claim that the fallback route is semantically correct or independently
controlled by the vehicle.

## Diagnostic privacy hardening

The controller's diagnostic messages sent to logcat and its host callback now
pass through the shared `DiagnosticRedactor`, including the MFi discovery,
location prewarm, and Bluetooth error branches that previously logged raw
exceptions directly. Exception output includes a bounded exception class and
only redacted detail; raw `Throwable` stack traces are not forwarded.
The routine wired-startup reader for the iPhone `syslog_relay` was removed so
private phone-side log lines are not collected or emitted by default. USB,
iAP2, MFi authentication, NCM, and AirPlay transport behavior were not
changed. Unit tests cover identifier redaction and rejection of credential or
protocol-trace lines.

## Existing display and control behavior

The current safe-area layout and shared video/touch transform remain unchanged. A status inset is evidence to preserve a safe content viewport, not authorization to hide or alter OEM system UI. Steering, HUD, cluster, fuel and climate features remain capability-gated and real-vehicle unverified.

## Not claimed

- No confirmed fix for the user's music auto-pause report.
- No confirmed audible navigation output or OEM speaker route.
- No confirmed root cause for the dismissed wired confirmation prompt.
- No real iPhone/vehicle connection result for V1.1.57.
