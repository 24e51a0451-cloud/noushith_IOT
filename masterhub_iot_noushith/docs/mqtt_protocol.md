# MasterHub / BCI JioSaavn Remote — protocol v1

Android project: `D:\GALATICX\BCI_remotecontroll_jiosaavn`.
This is a new companion protocol, not a claim of compatibility with an unexamined older APK.

## Transport

Default broker: `52.21.249.6:1883`, keepalive 30 seconds, QoS 1.
Default prefix: `masterhub/mobile/MOBILE_001`. Phone subscribes to `/command` and `/control`;
MasterHub subscribes to `/ack`, `/error`, `/media`, `/status`, `/heartbeat`.
Commands, ACKs, media, heartbeat and control messages are not retained.
Status is retained with an offline last will. Every five seconds the phone sends
a non-retained heartbeat and media snapshot. MasterHub expires liveness after 35 seconds;
retained online status never proves a currently reachable phone.

This uses the same broker as hardware and desktop MasterHub. Configure matching
credentials if authentication is required. Do not retain commands. Failed/rejected ACKs
are also published on `/error` for diagnostics; `/ack` remains authoritative.

## Command envelope

```json
{"command":"Right_Next_Song","confidence":1.0,"Is_Actionable":true,"query":"","command_id":"UUID","issued_at":1790000000000,"expires_at":1790000008000}
```

Times are Unix milliseconds; synchronize PC and phone clocks. Expiry is eight seconds
by default; the phone accepts at most a 60-second lifetime and 30 seconds future clock skew.
Every command has a fresh UUID; transport retries keep the same UUID.
Phone persists receipt before acting, then saves its final ACK. Duplicates return the cached
ACK without performing the action again. A crash during execution produces UNCONFIRMED,
not an automatic replay. At-most-once attempts are preferred to repeated toggles.

Actions: `Right_Next_Song`, `Right_Previous_Song`, `Right_Play_Pause`,
`Right_Volume_Up`, `Right_Volume_Down`, `Right_Return_to_Home`, `SEARCH`, `LAUNCH`.
Home means Android Home. Search requires nonempty query, maximum 500 characters.
Launch and Search are manual-only in MasterHub. Navigation combos affect MasterHub only.

## Results

```json
{"command_id":"UUID","command":"Right_Next_Song","status":"EXECUTED","method":"MediaController","detail":"Playback state change observed","timestamp":1790000001500}
```

`EXECUTED`: observed state change or action-specific success.
`UNCONFIRMED`: action requested without confirming state change; do not auto-retry.
`FAILED` / `REJECTED`: failure or invalid command.
MasterHub additionally reports `PENDING` and `TIMEOUT`. HTTP success means accepted for
delivery; only the phone ACK describes execution. A late ACK may replace TIMEOUT.

Media fields: title, artist, album, duration_ms, position_ms, playing,
session_available, volume, max_volume, timestamp. Album art is not transferred in v1.
Status/heartbeat fields: online, control_enabled, accessibility_enabled, timestamp.

`{"request":"START"}` / `{"request":"STOP"}` on `/control` gates the already-running
phone pipeline. It never starts a stopped Android service. Automatic Cortex lifecycle
publishing is not enabled in this version.

## MasterHub setup

Copy settings from `.env.mobile.example` into the existing `.env` as needed; preserve
hardware MQTT settings. Start MasterHub, open the dashboard (starts the dedicated client),
then enable remote control in the phone app. API-only clients should GET
`/api/jiosaavn/status` first and wait for a fresh heartbeat.

```json
{"command":"mobile_jiosaavn_search","params":{"query":"A R Rahman","confidence":1.0}}
```

POST commands to `/api/command`; GET `/api/jiosaavn/status` for recent command results
and `/api/jiosaavn/media` for cached media. Mobile routes bypass selected desktop targets.

## Device validation required

Playback uses JioSaavn's `com.jio.media.jiobeats` session with notification access.
Accessibility fallback requires an unlocked screen and matching visible English button
labels; JioSaavn UI/version/language changes may require selector updates.
Search fills the visible search field; selecting/playing a result remains manual in v1.
Launch is reported UNCONFIRMED because Android may restrict background activity starts.
No global key-event fallback is used to avoid controlling a different music player.
Start remote explicitly after process termination/reboot. Physical phone behavior,
background battery restrictions and permissions must be tested before claiming reliability.

## Verified desktop topic separation

Desktop actions routed to PC agents use `masterhub/devices/<PC_ID>/command`, `/ack`,
`/status`, `/error` (for example PC_001). Local Host actions bypass MQTT.
The legacy workflow `jiosaavn_topic` label is unused by the desktop handler.
Mobile uses `masterhub/mobile/MOBILE_001` so phone status is not consumed by the
existing `masterhub/devices/+/status` PC discovery subscription. Channel names match
the desktop convention; mobile retains its separate JSON contract and extra telemetry.
The `/api/jiosaavn/status` endpoint exposes effective broker and topic configuration.
