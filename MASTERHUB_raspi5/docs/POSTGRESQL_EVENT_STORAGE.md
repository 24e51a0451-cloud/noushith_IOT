# Runtime event storage

Masterhub records new operational activity in PostgreSQL's `public.runtime_events` table. The dashboard's **Saved Activity** panel reads these records through `/api/database/activity` and refreshes every five seconds. It supports device and event filters and loading older records. Opening an event shows its payload, topic and command ID where supplied.

## Recorded activity

- Hardware MQTT broker connection/disconnection and incoming status, acknowledgements, errors and sensor messages.
- Outgoing hardware MQTT commands, marked published or failed. Published does not mean the device executed the command.
- Mobile broker connections, incoming status/heartbeats, acknowledgements, errors and media messages; outgoing commands and observed acknowledgement timeouts.
- USB connections, command requests/results, and parsed incoming JSON messages.
- Engine command requests/results, dashboard command activity and Cortex connection changes.

Events carry a unique ID, installation ID, receipt time in UTC milliseconds, event kind, device ID, reported status, optional command ID, topic and JSON payload. Commands without a device acknowledgement remain unconfirmed; acknowledgements without command IDs are not paired with arbitrary commands. Retained MQTT messages are marked as retained. Saved history is not a live availability indicator. Existing heartbeat logic continues to determine live dashboard status.

Only new activity is captured. Previous in-memory events cannot be recovered retroactively. Acknowledgement packets are saved even after a restart when their original pending command is no longer in memory. Timeouts are recorded when the existing mobile status check detects them; this is not a new background timeout scheduler.

## Connection and deployment

The same PostgreSQL connection settings used for accounts also store runtime events. No Supabase dependency is required. DevOps can provide a PostgreSQL server and server-only connection URL:

```dotenv
DATABASE_URL='postgresql://APPLICATION_USER:URL_ENCODED_PASSWORD@HOST:5432/DATABASE?sslmode=require'
MASTERHUB_INSTANCE_ID=masterhub-main
```

Use the provider's required TLS settings, including certificate verification where supplied. Alternatively use the existing PGHOST/PGPORT/PGDATABASE/PGUSER/PGPASSWORD settings, plus PGSSLMODE. DATABASE_URL takes precedence. Never add credentials to browser JavaScript.

Keep MASTERHUB_INSTANCE_ID unchanged when moving this installation to another server or restoring its database; history queries are scoped to this ID. Use a different ID for another installation. This grouping does not implement multi-user authorization or make multiple Masterhub processes safe for shared control; friend access remains out of scope.

Run `python tools/check_postgresql.py` with the configured connection to create/verify tables, then restart Masterhub. Schema initialization currently requires the application role to create tables/indexes in the target schema. `database/schema.sql` contains the matching initial schema for DevOps review/provisioning. Do not point Masterhub at an empty cloud database before restoring the existing accounts/registrations if those should be retained.

## Database outages and recovery

Events first enter an atomic local file outbox in `data/event-outbox`. A background writer commits batches to PostgreSQL. It deletes queued files only after commit. A unique event ID makes replay safe if the process stops after committing but before deleting files. Database failure leaves files for retry every five seconds, including after restart. Opening the dashboard starts recovery of an existing backlog; new events also start the writer.

The control path performs a small local disk write but does not wait for PostgreSQL. If the disk is full, unavailable, or the event exceeds the size limit, an event cannot be queued: the error is logged and the dashboard reports the count. Invalid queued JSON is retained with an `.invalid` extension for inspection and does not block other events. Protect this folder like application data and use persistent storage in a container deployment. Do not delete it while events are pending.

The panel reports queued events, storage problems and unavailable history. During an outage it may show previously loaded history, explicitly marked as out of date. Common password/token/secret fields and credentials embedded in URLs are redacted before queuing, but arbitrary device text can still contain sensitive application data.

No automatic retention/deletion policy is enabled. DevOps should monitor database and outbox disk usage and agree an event retention policy before long-running production use. Clearing the existing live Activity Log does not delete Saved Activity.

## Inspecting data

In pgAdmin, select the configured database and run:

```sql
SELECT received_at, kind, device_id, status, command_id, payload
FROM public.runtime_events
ORDER BY sequence DESC
LIMIT 100;
```

## Validation

Regression coverage includes real PostgreSQL writes, outage retries, restart/replay without duplicates, secret-field redaction, history filtering/pagination and installation separation, unavailable-database responses, mobile late/uncorrelated acknowledgements, retained status, engine rejection history, malformed outbox recovery, dashboard rendering and existing hardware/mobile behavior. Tests use isolated schemas in a disposable PostgreSQL server, not production.
