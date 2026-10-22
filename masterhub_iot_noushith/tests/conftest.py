"""Keep credential API tests away from the user's real .env file."""
import pytest


@pytest.fixture(autouse=True)
def isolated_cortex_settings(tmp_path, monkeypatch):
    from cortex import config, dashboard

    env_file = tmp_path / '.env'
    env_file.write_text("CORTEX_CLIENT_ID='test-client'\nCORTEX_CLIENT_SECRET='test-secret'\n", encoding='utf-8')
    monkeypatch.setattr(config, '_ENV_FILE', env_file)
    monkeypatch.setattr(dashboard, '_ENV_FILE', env_file)
    for name in ('CLIENT_ID', 'CLIENT_SECRET', 'LICENSE', 'CORTEX_URL'):
        monkeypatch.setattr(config, name, getattr(config, name))
    return env_file


# Each test gets a unique PostgreSQL schema; never use the application's database.
import os
import uuid
import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo


def _create_test_schema():
    base = os.getenv('TEST_DATABASE_URL')
    if not base:
        raise pytest.UsageError('Set TEST_DATABASE_URL to a disposable PostgreSQL database before running tests')
    name = 'masterhub_test_' + uuid.uuid4().hex
    with psycopg.connect(base, autocommit=True, connect_timeout=5) as db:
        db.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(name)))
    return base, name, make_conninfo(base, options='-c search_path=' + name)


def pytest_configure(config):
    config._masterhub_pg = _create_test_schema()
    config._previous_database_url = os.environ.get('DATABASE_URL')
    os.environ['DATABASE_URL'] = config._masterhub_pg[2]


def _drop_test_schema(base, name):
    with psycopg.connect(base, autocommit=True, connect_timeout=5) as db:
        db.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(name)))


def pytest_unconfigure(config):
    if hasattr(config, '_masterhub_pg'):
        _drop_test_schema(*config._masterhub_pg[:2])
        if config._previous_database_url is None:
            os.environ.pop('DATABASE_URL', None)
        else:
            os.environ['DATABASE_URL'] = config._previous_database_url


@pytest.fixture
def postgres_db():
    base, name, dsn = _create_test_schema()
    try:
        yield dsn
    finally:
        _drop_test_schema(base, name)

@pytest.fixture(autouse=True)
def isolated_runtime_events(tmp_path, monkeypatch):
    from services import event_store as storage
    store = storage.EventStore(tmp_path / 'event-outbox', autostart=False, instance_id='test-hub')
    monkeypatch.setattr(storage, 'event_store', store)
    yield store
    store.stop()
