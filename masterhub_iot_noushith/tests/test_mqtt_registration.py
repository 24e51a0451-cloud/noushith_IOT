import json
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from unittest.mock import Mock, patch
import uuid

import pytest
from core.account_store import database
from core.devices import DeviceRegistry
from services.mobile_registration import register_device, MobileRegistrationService
from services.mobile_mqtt_service import MobileMQTTService


def body(name='sathwik', device_id=None):
    return dict(device_id=device_id or str(uuid.uuid4()), username=name, device_type='Android', request_id='request-1')


def test_uuid_rename_and_restart(tmp_path, postgres_db):
    path = postgres_db
    registry = DeviceRegistry(database_path=path)
    payload = body()
    first = register_device(payload, path, registry)
    assert first['topic_prefix'] == 'masterhub/mobile/sathwik'
    assert register_device(payload, path, registry)['device_id'] == first['device_id']
    payload['username'] = 'Sathwik1'
    renamed = register_device(payload, path, registry)
    assert renamed['username'] == 'sathwik1'
    assert renamed['device_id'] == first['device_id']
    assert renamed['topic_prefix'] == 'masterhub/mobile/sathwik1'
    assert DeviceRegistry(database_path=path).get(first['device_id'])['name'] == 'sathwik1'
    with database(path) as db:
        assert db.execute('SELECT COUNT(*) FROM mqtt_devices').fetchone()['count'] == 1


def test_duplicate_username_and_failed_rename_leave_identity_intact(tmp_path, postgres_db):
    path = postgres_db
    registry = DeviceRegistry(database_path=path)
    first = body('alice')
    second = body('bob')
    register_device(first, path, registry)
    register_device(second, path, registry)
    with pytest.raises(ValueError, match='already used'):
        register_device(dict(second, username='ALICE'), path, registry)
    assert registry.get(second['device_id'])['name'] == 'bob'
    with database(path) as db:
        assert db.execute('SELECT username FROM mqtt_devices WHERE device_id=%s', (second['device_id'],)).fetchone()['username'] == 'bob'


def test_concurrent_username_claims(tmp_path, postgres_db):
    path = postgres_db
    registry = DeviceRegistry(database_path=path)
    def attempt(_):
        try:
            register_device(body('same_name'), path, registry)
            return True
        except ValueError:
            return False
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(attempt, range(2))) == [False, True]


