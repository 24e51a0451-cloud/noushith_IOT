# MasterHub Cortex Module

Connects to a real Emotiv EPOC X headset via the Emotiv Cortex API and
produces live mental-command predictions, normalized to the same
format already used elsewhere in this project.

The app-owned Cortex worker now routes mental commands through MasterHub's
existing FSM, Router, and domain handlers. Start `python app.py` and connect
from `/cortex/` or `/dashboard`. See
[the current mental-control guide](../docs/CORTEX_MENTAL_CONTROL.md) for ordered
navigation, neutral release, input preparation, and verification. The standalone
runner remains useful for diagnostics; its state is separate from the app.

The low-level API reference below describes the connection components; older
"wiring into MasterHub" examples are superseded by the app-owned integration.

## Folder structure

```
cortex/
├── __init__.py            Package docstring/version
├── config.py               All configurable values (credentials, URLs, timeouts, ...)
├── auth.py                  Cortex login / authorization / token refresh
├── headset.py                Discover, connect, disconnect, battery, signal quality
├── session.py                 Create / activate / close / recover a Cortex session
├── stream.py                   Subscribe to Cortex data streams (com, and future ones)
├── cortex_client.py             Generic, reusable JSON-RPC-over-WebSocket client
├── prediction_mapper.py          Raw Cortex "com" message -> normalized prediction
├── run_live.py                    Executable entry point (console output)
├── dashboard.py                    Optional Flask Blueprint: GET /status /headset /session
├── logger.py                        Rotating file + console logging (cortex/logs/cortex.log)
├── requirements.txt
└── README.md
```

## Architecture

```
Emotiv EPOC X
      │  (Bluetooth dongle / USB)
      ▼
EMOTIV Launcher / App  ──  runs the local Cortex WebSocket service (wss://localhost:6868)
      │
      ▼
cortex_client.py   — JSON-RPC request/response, reconnect, heartbeat, event dispatch
      │
      ├── auth.py       — requestAccess / authorize -> cortexToken
      ├── headset.py     — queryHeadsets / controlDevice, battery + signal quality
      ├── session.py      — createSession / updateSession
      └── stream.py        — subscribe(["com"]) -> raw {"com": [...], "time": ...} messages
                                   │
                                   ▼
                        prediction_mapper.py
                                   │
                                   ▼
                {"command": "push", "confidence": 0.94, "timestamp": "..."}
                                   │
                                   ▼
                          run_live.py (prints to console)
```

## Installation

```bash
cd masterhub          # your existing MasterHub project root
pip install -r cortex/requirements.txt
```

Only `websocket-client` is new; `Flask` is almost certainly already
installed since MasterHub's own `requirements.txt` depends on it (only
needed here if you register the optional `dashboard.py` blueprint).

Requires Python 3.11+, matching the rest of the project.

## How to obtain Cortex API credentials

1. Create/sign in to an Emotiv account at https://www.emotiv.com/.
2. Install the **EMOTIV Launcher** (Windows/macOS) — this is what runs
   the local Cortex WebSocket service on `wss://localhost:6868`.
3. Go to **My Account → Cortex Apps** (`https://www.emotiv.com/my-account/cortex-apps/`)
   and create a new application to get a `Client ID` and `Client
   Secret`.
4. Set them via environment variables (recommended) or edit `config.py` directly:

   ```bash
   # Windows (PowerShell)
   $env:CORTEX_CLIENT_ID = "your-client-id"
   $env:CORTEX_CLIENT_SECRET = "your-client-secret"
   ```

5. A `LICENSE` value is only required for licensed/pro features (e.g.
   raw EEG export); leave `CORTEX_LICENSE` unset to use your account's
   free-tier access.
6. The **first time** you connect with a new Client ID, Cortex will
   show an access-request popup inside the EMOTIV Launcher — you must
   click **Approve** there before `auth.py`'s `request_access()` will
   report success (see "Troubleshooting" below).

## How to pair an Emotiv EPOC X headset

1. Plug in the USB dongle that shipped with the EPOC X (or enable
   Bluetooth pairing mode on the headset, if your unit supports it).
2. Power on the headset and put it on — the built-in sensors need skin
   contact to report good signal quality.
3. Open the EMOTIV Launcher; it should list the headset once it's
   powered on and in range. If it doesn't appear, use `HeadsetManager.refresh()`
   (wraps Cortex's `controlDevice` "refresh" command) to force a rescan.
4. `run_live.py` calls `HeadsetManager.ensure_connected()` automatically,
   which discovers the first available headset and connects it — no
   manual pairing step is required in this module beyond the physical
   setup above.

## How to start the Cortex service

The Cortex WebSocket service is started automatically **by the EMOTIV
Launcher/App** — simply open and leave it running in the background.
There is nothing to start from this module; `cortex_client.py` just
connects to whatever is already listening at `CORTEX_URL`
(`wss://localhost:6868` by default).

## How to run `run_live.py`

From the MasterHub project root, with the EMOTIV Launcher open and the
headset powered on:

```bash
python -m cortex.run_live
```

Expected output:

```
Connected. Streaming live mental-command predictions (Ctrl+C to stop)...

[2026-08-03T12:45:10.123000+00:00] command='push' confidence=0.94
[2026-08-03T12:45:10.353000+00:00] command='neutral' confidence=0.81
[2026-08-03T12:45:10.601000+00:00] command='left' confidence=0.88
```

Press `Ctrl+C` to stop — the session is closed and the headset
disconnected cleanly on shutdown.

All connection events, authentication, headset/session/stream
lifecycle, incoming predictions, errors, and reconnect attempts are
also written to `cortex/logs/cortex.log` (rotating, same pattern as
`services/logger_service.py` and `simulator/logger.py`).

## Optional: status dashboard

`dashboard.py` exposes a self-contained Flask Blueprint with three
read-only endpoints:

* `GET /cortex/status` — connected / authorized / last error / uptime
* `GET /cortex/headset` — id, status, battery %, signal quality
* `GET /cortex/session` — session id, status, headset id

It is not registered anywhere by default. To use it in your own Flask
app (this is the only integration step left to you, since this
blueprint intentionally does not depend on MasterHub's own UI):

```python
from cortex.dashboard import cortex_bp
app.register_blueprint(cortex_bp)
```

`run_live.py` keeps this state updated automatically as it runs
(`dashboard.update_status/update_headset/update_session`), whether or
not you've registered the blueprint.

## Wiring into MasterHub (not included in this module, by design)

`prediction_mapper.map_mental_command()` produces the same
`{"command", "confidence", "timestamp"}` shape as
`emotiv_bci_predictions.json`. To feed live predictions into MasterHub
through your existing HTTP sender instead of just printing them, the
glue is a few lines outside this module, e.g.:

```python
from cortex.run_live import LiveRunner, _raw_message_queue
from cortex.prediction_mapper import map_mental_command
from simulator.sender import CommandSender
from simulator.prediction_reader import Prediction
from datetime import datetime

sender = CommandSender()
runner = LiveRunner()
runner.start()

index = 0
while True:
    raw = _raw_message_queue.get()
    p = map_mental_command(raw)
    index += 1
    prediction = Prediction(
        index=index,
        timestamp=datetime.fromisoformat(p.timestamp),
        raw_timestamp=p.timestamp,
        gesture=p.command,
        confidence=p.confidence,
        raw=raw,
    )
    sender.send(prediction)
```

This module deliberately stops short of writing that glue itself, per
spec ("do not integrate with MasterHub in this module").

## Troubleshooting common connection issues

**`CortexConnectionError: Timed out connecting to Cortex`**
The EMOTIV Launcher isn't running, or nothing is listening on
`wss://localhost:6868`. Open the Launcher and wait for it to fully
start, then retry.

**`CortexAuthError: Cortex access has not been granted for this CLIENT_ID`**
This is expected the first time you use a new Client ID. Open the
EMOTIV Launcher, find and approve the access-request popup for your
application, then rerun `run_live.py`.

**`authorize failed: Cortex error ...` mentioning an invalid client id/secret**
Double-check `CORTEX_CLIENT_ID` / `CORTEX_CLIENT_SECRET` (env vars take
precedence over `config.py`) against the values shown in
**My Account → Cortex Apps**.

**`HeadsetError: No headset found`**
The EPOC X isn't powered on, isn't in range, or its dongle isn't
plugged in. Confirm it appears in the EMOTIV Launcher's own device
list first — if it's not there, this module can't see it either.
Try `HeadsetManager.refresh()` to force a rescan.

**Predictions never arrive after "Subscribed to 'com' stream..."**
Mental commands require the headset to be worn correctly (all sensors
in good contact) and, for most EPOC X setups, at least one command has
to have been trained in EmotivBCI first. Check signal quality via
`HeadsetManager.read_device_diagnostics()` or the EMOTIV Launcher's own
signal-quality view.

**Connection drops and reconnects repeatedly**
Usually a flaky Bluetooth link or USB dongle range issue rather than
this module — check `cortex/logs/cortex.log` for the WebSocket close
code/message logged just before each reconnect attempt. The module
will keep retrying every `CORTEX_RECONNECT_DELAY` seconds
(`config.py`) and fully re-authenticates, re-creates the session, and
re-subscribes automatically once the connection is back.

**SSL/certificate errors on connect**
Cortex uses a self-signed certificate for its local WebSocket server.
`config.VERIFY_SSL` defaults to `False`, which is the standard,
documented workaround for this — only set it to `True` if you've
separately installed Emotiv's local CA certificate.





http://127.0.0.1:5000/cortex/status
http://127.0.0.1:5000/cortex/headset
http://127.0.0.1:5000/cortex/session
http://127.0.0.1:5000/cortex/state
http://127.0.0.1:5000/cortex/        main





_DASHBOARD_HTML = """
<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\">
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
  <title>Cortex Live Dashboard</title>
  <style>
    body { font-family: Arial, sans-serif; margin: 20px; background: #111827; color: #f9fafb; }
    h1 { margin-bottom: 8px; }
    .card { background: #1f2937; padding: 16px; border-radius: 10px; margin-bottom: 16px; box-shadow: 0 4px 10px rgba(0,0,0,0.25); }
    table { width: 100%; border-collapse: collapse; }
    th, td { padding: 10px; border-bottom: 1px solid #374151; text-align: left; }
    th { color: #9ca3af; font-weight: 600; }
    .pill { display: inline-block; padding: 4px 8px; border-radius: 999px; font-size: 12px; font-weight: bold; }
    .on { background: #065f46; color: #d1fae5; }
    .off { background: #7f1d1d; color: #fee2e2; }
    .muted { color: #9ca3af; }
  </style>
</head>
<body>
  <h1>Cortex Live Dashboard</h1>
  <div class=\"muted\">Auto-refreshing every second</div>
  <div class=\"card\">
    <table>
      <tr><th>Field</th><th>Value</th></tr>
      <tr><td>Connection</td><td id=\"connection\">-</td></tr>
      <tr><td>Authorization</td><td id=\"authorization\">-</td></tr>
      <tr><td>Battery %</td><td id=\"battery\">-</td></tr>
      <tr><td>Signal Quality</td><td id=\"signal\">-</td></tr>
      <tr><td>Headset Name</td><td id=\"headset\">-</td></tr>
      <tr><td>Session ID</td><td id=\"session\">-</td></tr>
      <tr><td>Current Gesture</td><td id=\"gesture\">-</td></tr>
      <tr><td>Confidence</td><td id=\"confidence\">-</td></tr>
      <tr><td>Accepted</td><td id=\"accepted\">-</td></tr>
      <tr><td>Rejected</td><td id=\"rejected\">-</td></tr>
      <tr><td>Duplicate</td><td id=\"duplicate\">-</td></tr>
      <tr><td>Commands Sent</td><td id=\"commands-sent\">-</td></tr>
      <tr><td>Current MasterHub Mode</td><td id=\"mode\">-</td></tr>
      <tr><td>Current Routed Command</td><td id=\"routed\">-</td></tr>
      <tr><td>Current Domain</td><td id=\"domain\">-</td></tr>
      <tr><td>HTTP Status</td><td id=\"http-status\">-</td></tr>
      <tr><td>Response Time</td><td id=\"response-time\">-</td></tr>
    </table>
  </div>
  <script>
    const base = window.location.pathname.replace(/\/$/, '');
    const stateUrl = `${base}/state`;

    function badge(value, onText = 'ON', offText = 'OFF') {
      const isTrue = value === true || value === 'true' || value === 1;
      return `<span class=\"pill ${isTrue ? 'on' : 'off'}\">${isTrue ? onText : offText}</span>`;
    }

    function formatValue(value) {
      if (value === null || value === undefined || value === '') return '-';
      if (typeof value === 'number') return Number.isFinite(value) ? value : '-';
      return value;
    }

    function updateView(data) {
      const status = data.status || {};
      const headset = data.headset || {};
      const session = data.session || {};
      const metrics = data.metrics || {};

      document.getElementById('connection').innerHTML = badge(status.connected, 'Connected', 'Disconnected');
      document.getElementById('authorization').innerHTML = badge(status.authorized, 'Authorized', 'Not Authorized');
      document.getElementById('last-error').textContent = formatValue(status.last_error);
      document.getElementById('retry-attempt').textContent = formatValue(status.retry_attempt);
      document.getElementById('battery').textContent = formatValue(headset.battery_percent);
      document.getElementById('signal').textContent = formatValue(headset.signal_quality);
      document.getElementById('headset').textContent = formatValue(headset.id || session.headset_id);
      document.getElementById('session').textContent = formatValue(session.id);
      document.getElementById('gesture').textContent = formatValue(metrics.current_gesture);
      document.getElementById('confidence').textContent = formatValue(metrics.confidence);
      document.getElementById('accepted').textContent = formatValue(metrics.accepted);
      document.getElementById('rejected').textContent = formatValue(metrics.rejected);
      document.getElementById('duplicate').textContent = formatValue(metrics.duplicates);
      document.getElementById('commands-sent').textContent = formatValue(metrics.commands_sent);
      document.getElementById('mode').textContent = formatValue(metrics.current_mode);
      document.getElementById('routed').textContent = formatValue(metrics.current_routed_command);
      document.getElementById('domain').textContent = formatValue(metrics.current_domain);
      document.getElementById('http-status').textContent = formatValue(metrics.http_status);
      document.getElementById('response-time').textContent = formatValue(metrics.response_time_ms);
    }

    function loadState() {
      fetch(stateUrl)
        .then((response) => response.json())
        .then((payload) => updateView(payload.state || payload))
        .catch(() => {});
    }

    loadState();
    setInterval(loadState, 1000);
  </script>
</body>
</html>
"""
