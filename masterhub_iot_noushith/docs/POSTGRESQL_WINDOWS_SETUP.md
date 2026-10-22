# PostgreSQL setup on Windows

Masterhub now uses PostgreSQL for accounts, sessions, phone ownership, device registrations and MQTT identities. There is no SQLite fallback or Supabase background sync. PostgreSQL must be available when Masterhub starts. Retired database files and migration utilities have been removed.

## 1. Create the database and application login

Stop Masterhub before changing database settings. PostgreSQL 18 is installed at `C:\Program Files\PostgreSQL\18` on this computer; its Windows service is `postgresql-x64-18`. In Windows Services, ensure this service is Running.

Open **SQL Shell (psql)** from the Start menu. Accept `localhost`, database `postgres`, port `5432`, and username `postgres` (unless you changed these during installation). Enter the postgres password you chose during installation.

Run these commands separately in SQL Shell:

```sql
CREATE ROLE masterhub_app LOGIN;
\password masterhub_app
CREATE DATABASE masterhub OWNER masterhub_app;
```

The password command prompts twice for a new application password. Keep the admin password separate. `CREATE DATABASE` must run outside a transaction. If either name already exists, inspect it rather than dropping existing data.

If using pgAdmin instead: connect to PostgreSQL 18 with the installation password; create a Login/Group Role named `masterhub_app`, set its password and enable Can login; create a database named `masterhub`, with owner `masterhub_app`. Leave superuser privileges disabled.

## 2. Configure Masterhub

Edit the project's `.env` file locally:

```dotenv
PGHOST=localhost
PGPORT=5432
PGDATABASE=masterhub
PGUSER=masterhub_app
PGPASSWORD='your new application password'
```

Use your actual password and port. A nonempty `DATABASE_URL` overrides these fields; remove it or leave it blank when using the PG settings. Passwords in PG settings do not need URL encoding. Do not share this file.

In PowerShell, in the project folder:

```powershell
python -m pip install "psycopg[binary]==3.3.3"
python tools/check_postgresql.py
```

For a fresh Python environment, install `requirements.txt` instead. The check initializes the application tables and tests a write, read and rollback without leaving test rows.

## 3. Start Masterhub

```powershell
python app.py
```

Confirm that users can log in and saved registrations appear. Devices remain offline until fresh presence messages arrive. Accounts, registrations and history use PostgreSQL only. No hosted Supabase project is managed by this application.

## Testing

Tests require PostgreSQL and create isolated, uniquely named schemas. Use a disposable test database, never production:

```powershell
$env:TEST_DATABASE_URL = 'postgresql://test_user:test_password@localhost:5432/masterhub_test'
python -m pytest tests/test_mobile_accounts.py tests/test_mqtt_registration.py tests/test_android_source_protocol.py -q
```

The test role needs CREATE permission in that database. Tests remove only their generated schemas. Database connection errors at startup mean the service, port, login, password or database needs correction; there is no automatic fallback to an old store.

References: [PostgreSQL database creation](https://www.postgresql.org/docs/18/manage-ag-createdb.html), [psql password command](https://www.postgresql.org/docs/18/app-psql.html), [Psycopg installation](https://www.psycopg.org/psycopg3/docs/basic/install.html).
