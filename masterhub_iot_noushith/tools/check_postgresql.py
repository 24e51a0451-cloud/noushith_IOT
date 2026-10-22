"""Check PostgreSQL connectivity and initialize Masterhub tables."""
from pathlib import Path
import sys
import uuid
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import psycopg
from core.account_store import database


def main():
    try:
        with database() as db:
            print('Connected to PostgreSQL; Masterhub tables are ready.')
            identifier = 'check_' + uuid.uuid4().hex
            with db.transaction(force_rollback=True):
                db.execute('INSERT INTO mqtt_devices VALUES (%s,%s,%s,%s)',
                           (identifier, identifier, 'android', 0))
                assert db.execute('SELECT device_id FROM mqtt_devices WHERE device_id=%s',
                                  (identifier,)).fetchone()['device_id'] == identifier
            print('PASS: write/read/rollback check; no test data retained.')
    except psycopg.errors.InsufficientPrivilege:
        sys.exit(
            'PostgreSQL login succeeded, but the configured user lacks database/schema permissions. '
            'For the default setup, connect to database masterhub as postgres in pgAdmin or SQL Shell and run: '
            'GRANT USAGE, CREATE ON SCHEMA public TO masterhub_app;'
        )
    except (psycopg.Error, ValueError):
        sys.exit('PostgreSQL check failed. Check the Windows service and PG settings in .env.')


if __name__ == '__main__':
    main()
