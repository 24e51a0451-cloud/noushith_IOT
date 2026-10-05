# MQTT phone registration — Android 0.5

## Test the update

1. Restart the updated MasterHub using `python app.py`. This starts the registration listener on the existing mobile MQTT broker. Flask CLI/WSGI starts the listener when the dashboard or device-list/mobile-status endpoint is opened. Keep MasterHub running during registration.
2. Install `BCI-JioSaavn-Remote-0.5.0.apk` over the existing app. It uses the same debug signing certificate as 0.4. Do not uninstall if you want to preserve its stored installation UUID.
3. Open the app, enter a unique username, and tap **Register device**. There is no MasterHub HTTP/HTTPS address, account password, or login. Broker settings are optional and use the existing configured broker; defaults remain `tcp://52.21.249.6:1883`. If the broker requires credentials, enter them under Broker settings. Phone and MasterHub must use the same broker.
4. The phone waits for MasterHub's confirmation. If the username is taken by another UUID, it shows an error. If MasterHub does not respond within 15 seconds after publishing, it asks you to check the server/broker and retry. It does not activate an unconfirmed registration.
5. The dashboard shows the registered username in the device selector. Select it as the active target. On the phone, grant the existing media/accessibility permissions, open a song in JioSaavn, and tap **Start remote**. Registration itself does not start playback or remote control.
6. Use **Change username / registration** on the phone to rename it. This stops remote control while editing. The same UUID is reused; the existing registry entry is updated. Press Start remote again after saving.

## Identity and storage

The phone generates and persists a UUID in SharedPreferences on first opening. Upgrading from 0.4 reuses the saved installation UUID when available; otherwise it reuses the previous MQTT client UUID or generates one. Normal reopening and renaming preserve the UUID. Clearing app data or uninstalling removes local identity.

MasterHub stores registration in SQLite `data/masterhub.db` (`mqtt_devices`) and its persistent device registry. UUID is the primary key; lowercase username has a UNIQUE constraint. Usernames accept 3–32 ASCII letters, digits and underscores, case-insensitively. Existing laptop data and the earlier account tables are preserved. The old HTTPS account APIs remain available for compatibility, but Android 0.5 does not call them.

## MQTT contract

Registration request topic: `bci/devices/register`, QoS 1, not retained.

```json
{
  "device_id": "cab4c400-6d5a-4dab-b6dc-527ebc297177",
  "username": "sathwik",
  "device_type": "Android",
  "request_id": "unique-per-registration-attempt"
}
```

MasterHub replies on `bci/{uuid}/registration` with the same `device_id` and `request_id`. Success has `status: REGISTERED`, the normalized `username`, and `topic_prefix: bci/{uuid}`. Rejection has `status: REJECTED` and an `error`. The phone ignores retained replies or replies for other attempts/devices.

Each registered phone uses these UUID-based topics:

- `bci/{uuid}/commands`: existing BCI/manual command payload, plus `target_device` equal to the phone UUID.
- `bci/{uuid}/ack`: existing execution acknowledgements.
- `bci/{uuid}/media`: existing track title, artist, album, position, volume and playback state. Album-art upload is unchanged and not implemented.
- `bci/{uuid}/status`: retained online/offline state and control readiness.
- `bci/{uuid}/heartbeat`: fresh liveness, sent every five seconds while connected.
- `bci/{uuid}/control`: existing START/STOP pipeline messages, now also requiring `target_device` equal to the UUID.

The Android service discards commands/control messages with missing or mismatched `target_device` before executing or acknowledging them. Broadcast `all` is not accepted. Existing expiry, duplicate-command protection, media controls and accessibility behavior are retained. Legacy mobile topic namespaces and desktop PC-agent topics continue to work for older registrations.

## Access boundary

This is device discovery with unique names, not password-based user authentication. A UUID is an identifier, not a secret. Existing broker authentication configuration is supported, but this change does not install broker ACLs. Broker-side permissions are needed to stop other clients claiming a UUID, publishing registration responses, or publishing to another phone's topics. UUID topics and the client target check prevent accidental misrouting; they do not replace broker authorization.

## Verification

Backend tests cover case-insensitive uniqueness, concurrent username claims, stable UUIDs, rename conflicts, SQLite reload, correlated registration replies, topic selection, and target fields. A local Mosquitto integration test exchanges real registration, rename and command messages. Android unit tests cover response correlation and exact UUID target matching; the debug APK build and lint complete successfully. Physical-phone playback and the externally configured broker still require the operator's test.
