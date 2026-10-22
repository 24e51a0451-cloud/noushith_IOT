import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from flask import Flask
from services import event_store as storage
from api.history import history_bp


@pytest.fixture
def store(tmp_path, postgres_db, monkeypatch):
    result = storage.EventStore(tmp_path / 'events', postgres_db, 'hub-one', autostart=False)
    monkeypatch.setattr(storage, 'event_store', result)
    return result


def test_restart_retry_and_idempotent_replay(store, monkeypatch):
    store.record('ack', 'phone', 'EXECUTED', {'password': 'secret', 'nested': {'access_token': 'private'}}, 'cmd-1')
    queued = next(store.spool.glob('*.json'))
    backup = queued.read_text()
    assert 'secret' not in backup and 'private' not in backup
    original = storage.database
    monkeypatch.setattr(storage, 'database', Mock(side_effect=OSError('unreachable')))
    assert store.flush_once() == 0
    assert queued.exists()
    monkeypatch.setattr(storage, 'database', original)
    resumed = storage.EventStore(store.spool, store.dsn, 'hub-one', autostart=False)
    assert resumed.flush_once() == 1
    queued.write_text(backup)
    assert resumed.flush_once() == 1
    rows = resumed.history()
    assert len(rows) == 1 and rows[0]['command_id'] == 'cmd-1'
    assert not list(store.spool.glob('*.json'))


def test_history_filters_pagination_and_instance_isolation(store):
    for i in range(3):
        store.record('status', 'device-' + str(i), 'ONLINE', {'retained': True})
    store.flush_once()
    rows = store.history(limit=2)
    assert len(rows) == 2
    assert len(store.history(before=rows[-1]['sequence'])) == 1
    assert len(store.history(device_id='device-1', kind='status')) == 1
    other = storage.EventStore(store.spool, store.dsn, 'other-hub', autostart=False)
    assert other.history() == []


def test_api_unavailable_and_validation(store, monkeypatch):
    app = Flask(__name__)
    app.register_blueprint(history_bp)
    client = app.test_client()
    assert client.get('/api/database/activity?limit=999').status_code == 400
    store.record('command', 'phone', 'PENDING', {}, 'cmd')
    store.flush_once()
    assert client.get('/api/database/activity').json['events'][0]['status'] == 'PENDING'
    monkeypatch.setattr(store, 'history', Mock(side_effect=OSError('private connection details')))
    response = client.get('/api/database/activity')
    assert response.status_code == 503
    assert 'private connection' not in response.text


def test_mobile_ack_recorded_after_restart_without_in_memory_command(store):
    from services.mobile_mqtt_service import MobileMQTTService
    service = MobileMQTTService(client=Mock(), device_id='test-phone')
    service._on_message(None, None, SimpleNamespace(topic=service.topics['ack'], retain=False,
        payload=json.dumps(dict(command_id='old-command', status='EXECUTED')).encode()))
    store.flush_once()
    row = store.history()[0]
    assert row['kind'] == 'ack' and row['command_id'] == 'old-command'


def test_retained_status_and_uncorrelated_ack_remain_explicit(store):
    from services.mobile_mqtt_service import MobileMQTTService
    service = MobileMQTTService(client=Mock(), device_id='phone', topic_prefix='bci/username')
    service._on_message(None, None, SimpleNamespace(topic=service.topics['status'], retain=True,
        payload=b'{"status":"ONLINE"}'))
    service._on_message(None, None, SimpleNamespace(topic=service.topics['ack'], retain=False,
        payload=b'{"status":"EXECUTED"}'))
    store.flush_once()
    assert store.history(kind='ack')[0]['status'] == 'UNCONFIRMED'
    assert store.history(kind='status')[0]['payload']['retained'] is True
    assert not service.snapshot()['online']


def test_mqtt_topic_identity_and_cortex_activity_saved(store):
    storage.record_mqtt('masterhub/devices/pc1/ack', {'command_id': 'command-1', 'status':'EXECUTED'})
    storage.record_mqtt('iot/device/node1/status', {'status':'ONLINE'})
    from cortex.dashboard import log_command_event
    log_command_event(command='LEFT', domain='iot')
    store.flush_once()
    assert store.history(device_id='pc1')[0]['command_id'] == 'command-1'
    assert store.history(device_id='node1')[0]['status'] == 'ONLINE'
    assert store.history(kind='activity')[0]['payload']['command'] == 'LEFT'


def test_engine_records_rejections_without_changing_result(store, monkeypatch):
    from core.engine import Engine
    engine = Engine()
    result = {'success': False, 'error': 'rejected'}
    monkeypatch.setattr(engine, '_process', lambda command, params: result)
    assert engine.process('STOP', {'target': 'device1'}) is result
    store.flush_once()
    assert store.history(kind='command_result')[0]['status'] == 'FAILED'
    assert store.history(kind='command_request')[0]['device_id'] == 'device1'


def test_bad_queue_file_does_not_block_valid_events(store):
    store.spool.mkdir(parents=True)
    (store.spool / '000-bad.json').write_text('broken')
    store.record('status', 'device', 'ONLINE')
    assert store.flush_once() == 1
    assert store.health()['quarantined'] == 1
    assert len(store.history()) == 1


def test_dashboard_renders_saved_activity(store):
    from app import create_app
    app = create_app()
    app.testing = True
    response = app.test_client().get('/dashboard')
    assert response.status_code == 200
    assert b'id="databaseHistory"' in response.data
    assert b'database-history.js' in response.data
