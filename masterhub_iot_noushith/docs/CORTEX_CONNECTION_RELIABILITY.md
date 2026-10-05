# Cortex connection recovery

Restart MasterHub after updating the Python files. Open Connection Settings,
enter the real Emotiv application client ID and secret, and save. A blank
secret preserves the saved secret. Saving confirms persistence; successful
authorization is shown separately by the connection status. Approve the
application in EMOTIV Launcher when prompted, then connect the headset.

Settings are quoted and saved atomically to the project `.env`. Saved Cortex
values take precedence over inherited environment values. Other environment
settings are preserved. New connections reload the complete saved credential
pair and URL. Saving while connected requests recovery with the new settings.

One runner owns socket connection, authorization, session creation, and stream
subscription. It retries startup and dropped connections, and rebuilds the
session when Cortex reports canceled streams, a closed session, or logout.
Stop requests cancel retries. Connection loss resets command processing and
stops active motion before recovery.

Cortex warning semantics: https://emotiv.gitbook.io/cortex-api/warning-objects

Regression checks (use pytest so credential API tests use isolated files):

```powershell
python -m pytest tests/test_cortex_stability.py tests/test_cortex_retry.py tests/test_cortex_control.py tests/test_bci_panel.py -q
```

For hardware verification, connect and confirm live samples, briefly disconnect
the headset or restart Cortex, then confirm that authorization, session, and
samples recover. Repeat after restarting MasterHub to verify saved credentials.
