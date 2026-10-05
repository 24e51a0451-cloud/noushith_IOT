# Mobile accounts and device registration

**Superseded for Android 0.5:** the current phone onboarding uses [MQTT device registration](mobile_mqtt_registration.md) and requires no HTTPS server address. This document describes the retained 0.4 account API for compatibility.

The Android companion version 0.4 adds registration/login before its existing dashboard. Playback, accessibility selectors, Android permissions, command payloads, heartbeat, acknowledgements, and manual Start/Stop controls are retained. A successful login does not start remote control automatically.

## Setup

1. Restart MasterHub with the new code. SQLite is created at `data/masterhub.db`, or the path in `MASTERHUB_DATABASE`. Existing `data/devices.json` is imported only when the SQLite registry has no saved snapshot. Keep backups of the database; JSON is no longer the live store. Run one MasterHub server process because device state and selected targets are held in memory.
2. Expose the account API through an HTTPS endpoint reachable from the phone, with a certificate trusted by Android. Enter that base URL in the app. The Flask development server at HTTP port 5000 does not provide HTTPS itself. No public server, DNS, certificate, or reverse proxy is deployed by this change. Keep the existing unauthenticated dashboard/control APIs on a trusted network; publish only the four account endpoints if exposing registration externally.
3. The phone must also reach the configured MQTT broker. `BCI_MOBILE_PUBLIC_MQTT_URI` optionally overrides the URI returned to phones; otherwise the existing mobile broker host/port/TLS settings are used. Optional `BCI_MOBILE_DEVICE_MQTT_USERNAME` and `BCI_MOBILE_DEVICE_MQTT_PASSWORD` are phone credentials, separate from backend broker credentials. Existing broker settings and legacy mobile topics remain supported.
4. Install the APK, create an account or log in, and enter a phone name. Usernames use 3–32 ASCII letters, digits, or underscores and are case-insensitive. Passwords use 8–128 characters. Repeated registration of the same installation for the same account returns the same device ID. Reinstalling/clearing app data creates a new installation identity. Different accounts on the same phone have separate device records.
5. Select the returned `MOBILE_...` device in MasterHub's target list. Grant the existing media/accessibility permissions and tap Start remote on the phone. MasterHub uses that selected phone for Mobile JioSaavn commands and feedback. Laptop and Local Host flows remain unchanged.

## API

All bodies and responses are JSON. Session expiry is Unix epoch **milliseconds**. Account responses have `Cache-Control: no-store`. Use HTTPS for credentials and session tokens.

- `POST /api/auth/register`: `{ "username": "alice", "password": "a long password" }`. Returns HTTP 201 with `{ "token": "...", "expires_at": 1234567890000, "user": { "id": 1, "username": "alice" } }`. An existing username returns 409.
- `POST /api/auth/login`: same request; same response with HTTP 200. Invalid credentials return 401.
- `POST /api/mobile/devices/register`: Bearer authorization, with `{ "installation_id": "a-persisted-installation-uuid", "name": "Alice phone", "device_category": "mobile", "platform": "android" }`. Returns HTTP 201 with `device` (the registry record) and `mqtt` (`uri`, `prefix`, `username`, `password`). The topic prefix is `masterhub/mobile/<assigned-device-id>`. Invalid/expired sessions return 401.
- `POST /api/auth/logout`: Bearer authorization; invalidates that session and returns `{ "success": true }`. Does not delete the registered phone.

SQLite enforces unique normalized usernames. Passwords use Werkzeug's scrypt password hashing; only SHA-256 hashes of random session tokens are stored in the database. Sessions last 30 days. The Android app encrypts its token using Android Keystore, stores a persistent installation ID, and never saves the account password. Logout clears local login, stops remote control, and requests server revocation. If offline, server revocation cannot be guaranteed; the local session is still cleared and the server token expires normally. Topic identity is read-only in the dashboard; the existing broker settings remain editable while stopped.

Registration/login attempts are limited to 10 per minute per directly observed client address. Behind a reverse proxy, configure per-client throttling there; this code deliberately does not trust arbitrary forwarded-IP headers.

## MQTT authorization boundary

Account authentication protects the new registration APIs. It does not itself provision broker users or ACLs. Unique device topics provide routing, not authorization. The current broker may allow shared or anonymous access; production isolation requires broker-side per-device credentials and ACLs (phone subscribes to its command/control topics and publishes its own telemetry/ACK topics). This change does not reconfigure the external broker or claim that one phone is prevented from accessing another's topics. Legacy MasterHub command/dashboard endpoints retain their previous access behavior.

## Validation

Run `python -m pytest tests/test_mobile_accounts.py tests/test_device_categories.py tests/test_media_jiosaavn_mobile.py tests/test_workflow.py` and the Android `testDebugUnitTest lintDebug assembleDebug` tasks. On a physical phone, verify signup, duplicate username rejection, login/logout, repeated login preserving the device ID, registration appearing in MasterHub, and existing playback/ACK behavior. A successful build is not proof that a particular JioSaavn version's accessibility controls work.
