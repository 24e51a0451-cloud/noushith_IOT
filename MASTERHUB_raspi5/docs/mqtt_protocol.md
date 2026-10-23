# Mobile MQTT contract

Registration and lifecycle are separate. All channels use QoS 1.

## Registration

Phone publishes non-retained JSON to `masterhub/mobile/register`:

```json
{"device_uuid":"c3a1d9b4-7d52-4a1e-8e31-2e6f5d8e7c10","requested_name":"vyshnavi","platform":"android","app_version":"1.0.0","capabilities":["media","jiosaavn"],"timestamp":1757400000000}
```

Hub replies, non-retained, on `masterhub/mobile/{device_uuid}/register_ack`:

```json
{"status":"APPROVED","device_id":"vyshnavi","device_uuid":"c3a1d9b4-7d52-4a1e-8e31-2e6f5d8e7c10","topic_prefix":"masterhub/mobile/vyshnavi","message":"Registered successfully in PostgreSQL"}
```

A name conflict returns `status: REJECTED`, `device_uuid`, and
`error: Username already taken`. Names accept 3–32 ASCII letters, digits or
underscores and are normalized to lowercase. The phone must use the returned
`device_id` and `topic_prefix`. PostgreSQL keeps the hardware UUID as the stable
internal identity; renaming updates the same device. Capabilities are saved with
the registry record; app_version and the registration timestamp are informational.
Invalid UUIDs cannot receive a correlated reply. Retained requests are ignored.
Status packets never register devices or produce registration replies.

## Commands

Hub publishes non-retained commands to `masterhub/mobile/{device_id}/command`:

```json
{"command_id":"9f2c8d1e-3a4b-5c6d-7e8f-0a1b2c3d4e5f","command":"PLAY_PAUSE","target_device":"vyshnavi","origin":"bci_prediction","confidence":0.89,"query":"Kesariya","expires_at":1757400030000,"timestamp":1757400000000}
```

Origin is `bci_prediction` for Cortex/BCI actions and `dashboard` for manual actions.
Times are Unix milliseconds. Normal commands expire after the configured ACK
timeout (8 seconds by default); SEARCH allows at least 45 seconds.
Play/pause sends `PLAY_PAUSE`. Other existing command values remain unchanged:
`Right_Next_Song`, `Right_Previous_Song`, `Right_Volume_Up`, `Right_Volume_Down`,
`SEARCH`, and `Right_JioSaavn` for launch. Return to Home remains unsupported.

## Receipts

Phone publishes results to `masterhub/mobile/{device_id}/ack`, not retained.
A matching `command_id` with `status: SUCCESS` completes the command.
`FAILED` or `REJECTED` preserves the phone's `code` and `error` details. The full
receipt, including `device_id`, `command`, `tier_used`, and `timestamp`, is kept.
Only `SUCCESS`, `FAILED`, and `REJECTED` receipts are accepted. Unknown IDs cannot
confirm execution. Receipts must identify the target device and must not be retained. Late receipts may replace TIMEOUT; duplicates cannot overwrite
terminal results. The dashboard recognizes SUCCESS.

## Status and heartbeat

The phone configures a retained LWT on `masterhub/mobile/{device_id}/status`
at connection time:

```json
{"device_id":"vyshnavi","status":"OFFLINE","reason":"Connection lost / abrupt disconnect"}
```

On connect it publishes retained status:

```json
{"device_id":"vyshnavi","status":"ONLINE","remote_state":"ACTIVE","timestamp":1757400000000}
```

It publishes a non-retained heartbeat every 10–15 seconds on
`masterhub/mobile/{device_id}/heartbeat`:

```json
{"device_id":"vyshnavi","status":"alive","battery_level":84,"timestamp":1757400015000}
```

The hub expires liveness after 35 seconds by default. Retained ONLINE alone cannot
establish fresh presence; a fresh heartbeat can. OFFLINE clears presence and disables
control immediately. ACTIVE enables remote control; STANDBY disables it.
Registration alone does not enable control. The phone must configure its own LWT
and heartbeat timer; the hub cannot configure a will for another MQTT client.

## Setup and removal of old topics

Only these topics are used:

- `masterhub/mobile/register`
- `masterhub/mobile/{device_uuid}/register_ack`
- `masterhub/mobile/{device_id}/command`
- `masterhub/mobile/{device_id}/ack`
- `masterhub/mobile/{device_id}/status`
- `masterhub/mobile/{device_id}/heartbeat`

The old `bci/...` registration and command routes are removed. `/media`, `/error`,
and `/control` are no longer subscribed to or published by the mobile transport.
Failures belong on `/ack`. Playback telemetry is not part of this contract.
Desktop agents remain on `masterhub/devices/{PC_ID}/...`.

Configure the broker using `.env.mobile.example` and restart MasterHub.
`BCI_MOBILE_DEVICE_ID` selects the default target (MOBILE_001 if unset).
Registered devices use the approved username. Old topic-prefix and individual-topic
environment overrides are ignored. Existing devices with old saved prefixes route
through `masterhub/mobile/{saved_name}`; re-register the phone to save the new prefix.
The hardware UUID stays the registry identity, so saved target selections survive.
The phone must implement the same contract, including its LWT and heartbeat timer.
GET `/api/jiosaavn/status` exposes current topics, presence and receipts.
Broker authentication and ACLs are separate from unique-name registration.
