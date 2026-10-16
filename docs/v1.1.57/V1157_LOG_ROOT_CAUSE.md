# V1.1.57 runtime log findings

## Scope and evidence

This report summarizes the user-provided, locally reviewed diagnostic log. The raw log remains local and is not copied into the repository. The log had no stable connection-session identifier tying every excerpt to the same phone/audio session, so cross-excerpt conclusions are marked unknown.

| Symptom | Direct observation | What it establishes | What remains unknown |
| --- | --- | --- | --- |
| OPUS output absent | Four entries report `audioType=default`, `codec=OPUS`, `stage=decoder-create`, `IllegalArgumentException`. Nearby counters show no queued decoder input, unavailable decoder packets increasing, and no output buffers. | In those excerpts, decoding stopped before MediaFormat configuration or AudioTrack output. | Why Android's default decoder factory rejected creation; whether an explicitly named decoder can be created and decode this stream; whether each excerpt is the navigation stream. |
| Navigation voice absent | The user's vehicle report says navigation speech is inaudible. OPUS decoder creation failures exist in the supplied log. | Decoder construction is a concrete failure mode consistent with silence. | The excerpts do not correlate the failure with a navigation stream or establish the car's final output route. Root cause for the vehicle symptom is not fully proven. |
| Music pauses after about one second | Previously reported by the user; the corresponding current session did not reproduce the event. | Historical symptom only. | Trigger, focus owner, and whether this build changes it. No fix is claimed. |
| Top strip overlaps image | A reported viewport is 1800×656 while the negotiated canvas is 1920×720; top inset is 64 px. | The OS/OEM provides a reduced viewport and a top inset/overlay is present. | The 120 px width difference and exact OEM composition behavior. The app cannot prove it may hide the OEM strip. |

## Connection evidence

The reviewed log excerpts indicate that at least one wireless session reached iAP2 authentication, AirPlay session establishment, and an H.264 first frame. This proves those observed stages for that session only. It does not prove wired USB, OPUS decode, navigation audio routing, or the current V1.1.57 source on a vehicle.

## Classification

- OPUS decoder construction failure in the supplied excerpts: `OBSERVED`.
- Underlying platform/codec-selection cause: `UNKNOWN`.
- Navigation silence root cause across the complete car audio path: `PARTIAL_EVIDENCE`.
- Music auto-pause root cause: `HISTORICAL_NOT_REPRODUCED`.
- Display obstruction root cause: `PARTIAL_EVIDENCE`.
- Current V1.1.57 real-vehicle result: `NOT_TESTED`.

## Follow-up classification instrumentation

The candidate now records a protocol audio class independently from the
compatibility routing channel. Only explicit protocol labels are classified as
MUSIC (`media`), NAVIGATION (`navigation`), SIRI (`speechRecognition`), CALL
(`telephony`), or SYSTEM (`system`). Missing or ambiguous labels (`default`,
`alert`, `compatibility`, and unrecognized values) are logged as UNKNOWN. This
does not reinterpret the prior runtime log or establish a vehicle route; the
existing compatibility routing remains unchanged and vehicle audio behavior
is still `NOT_TESTED` for this candidate.
