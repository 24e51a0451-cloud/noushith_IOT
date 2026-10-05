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


def test_uuid_rename_and_restart(tmp_path):
    path = tmp_path / 'hub.db'
    registry = DeviceRegistry(database_path=path)
    payload = body()
    first = register_device(payload, path, registry)
    assert first['topic_prefix'] == 'bci/' + payload['device_id']
    assert register_device(payload, path, registry)['device_id'] == first['device_id']
    payload['username'] = 'Sathwik1'
    renamed = register_device(payload, path, registry)
    assert renamed['username'] == 'sathwik1'
    assert renamed['device_id'] == first['device_id']
    assert renamed['topic_prefix'] == first['topic_prefix']
    assert DeviceRegistry(database_path=path).get(first['device_id'])['name'] == 'sathwik1'
    with database(path) as db:
        assert db.execute('SELECT COUNT(*) FROM mqtt_devices').fetchone()[0] == 1


def test_duplicate_username_and_failed_rename_leave_identity_intact(tmp_path):
    path = tmp_path / 'hub.db'
    registry = DeviceRegistry(database_path=path)
    first = body('alice')
    second = body('bob')
    register_device(first, path, registry)
    register_device(second, path, registry)
    with pytest.raises(ValueError, match='already used'):
        register_device(dict(second, username='ALICE'), path, registry)
    assert registry.get(second['device_id'])['name'] == 'bob'
    with database(path) as db:
        assert db.execute('SELECT username FROM mqtt_devices WHERE device_id=?', (second['device_id'],)).fetchone()[0] == 'bob'


def test_concurrent_username_claims(tmp_path):
    path = tmp_path / 'hub.db'
    registry = DeviceRegistry(database_path=path)
    def attempt(_):
        try:
            register_device(body('same_name'), path, registry)
            return True
        except ValueError:
            return False
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(attempt, range(2))) == [False, True]


def test_mqtt_ack_correlated_and_not_retained():
    payload = body()
    client = Mock()
    service = MobileRegistrationService()
    message = SimpleNamespace(topic='bci/devices/register', retain=False, payload=json.dumps(payload).encode())
    with patch('services.mobile_registration.register_device', return_value=dict(status='REGISTERED', device_id=payload['device_id'])), \
         patch('services.mobile_mqtt_service.service_for_device'):
        service.on_message(client, None, message)
    args, kwargs = client.publish.call_args
    assert args[0] == f"bci/{payload['device_id']}/registration"
    assert json.loads(args[1])['request_id'] == 'request-1'
    assert kwargs == dict(qos=1, retain=False)
    client.reset_mock()
    message.retain = True
    service.on_message(client, None, message)
    client.publish.assert_not_called()


def test_dispatch_contains_uuid_target_and_uses_plural_commands():
    device_id = str(uuid.uuid4())
    client = Mock()
    client.publish.return_value.rc = 0
    service = MobileMQTTService(client=client, device_id=device_id, topic_prefix='bci/' + device_id)
    service.started = service.connected = True
    import time
    service.last_seen = time.time()
    service.phone = dict(control_enabled=True)
    assert service.publish_command('NEXT', 1)['success']
    args = client.publish.call_args.args
    assert args[0] == f'bci/{device_id}/commands'
    assert json.loads(args[1])['target_device'] == device_id
