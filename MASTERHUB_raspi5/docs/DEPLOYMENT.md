# MasterHub deployment pipeline

One Flask application serves the existing dashboard and API. One PostgreSQL connection configuration stores accounts, device registrations, and events. The currently configured PostgreSQL server is retained; no database is dropped or migrated.

## Validate and package

Use Python 3.12+ and Node 24. Install `requirements-production.txt` and `tests/requirements.txt`. Set `TEST_DATABASE_URL` to a disposable PostgreSQL database whose role can create schemas. Never point it at the application database.

```powershell
python -m pip install -r requirements-production.txt -r tests/requirements.txt
python -m pytest tests -q
node --test tests/test_dashboard_security.cjs tests/test_dashboard_temporal.cjs
python tools/package_release.py
```

The GitHub Actions workflow runs these gates with PostgreSQL 18 and a local Mosquitto broker, then publishes the compact source ZIP. It runs only after this folder is committed and pushed to GitHub. This workspace currently has no Git repository. The ZIP excludes secrets, research outputs, build caches, backups and live data. It is a source release, not a database backup.

## Configure and start

Extract the ZIP into a new directory, create a virtual environment, and install `requirements-production.txt`. Copy `.env.example` to `.env` and configure the existing PostgreSQL server using either PG fields or DATABASE_URL. Do not configure a second database. Preserve MASTERHUB_INSTANCE_ID, data/event-outbox, and .runtime/hardware.json when upgrading this installation. Back up PostgreSQL before upgrading; do not delete the previous installation until verified.

Set MASTERHUB_OPERATOR_USER and MASTERHUB_OPERATOR_PASSWORD to a unique random password of at least 32 characters. Generate one with `python -c "import secrets; print(secrets.token_urlsafe(32))"`. Keep it in the server environment or private .env. Run:

```powershell
python tools/check_postgresql.py
python serve.py
```

Open /dashboard and enter the operator credentials in the browser prompt. Native control clients must send HTTP Basic credentials. Android account login, registration, logout and authenticated phone registration retain their existing bearer-token contract; phone accounts do not grant operator privileges. /healthz is a public liveness check and does not prove database or hardware readiness. The protected database activity panel reports storage health.

The bundled prediction sender and live test harness read MASTERHUB_OPERATOR_USER and MASTERHUB_OPERATOR_PASSWORD from their environment. Configure those values when pointing them at a protected server. To replay a recorded prediction file in a fresh release, supply your own recording with the simulator's `--file` option; personal recordings are not included in release packages.

Waitress runs a single process because the controller, MQTT connections and BCI state are in memory. Do not start multiple app workers or replicas. Its bounded thread pool also serves live event streams: this installation is intended for a small operator group. Desktop actions require an interactive Windows user session; a headless service cannot control that desktop. Keep calibration and temporal framing unchanged.

For remote use, put a TLS reverse proxy in front of the loopback listener and require HTTPS. Always configure operator credentials when using a proxy; otherwise loopback traffic cannot distinguish proxy visitors from local users. Restrict the port with a firewall. Do not trust arbitrary forwarded headers. MQTT access controls/TLS must also be configured on the existing broker and devices before exposing them outside a trusted network.

Verify operator login, dashboard status, PostgreSQL activity, and a safe hardware command after deployment. Stop actuators before restarting. Roll back by stopping the new process and restarting the preserved old installation with the same database; no destructive schema migration is introduced here. Deployment is a deliberate host operation, not an automatic push to a machine controlling actuators.
