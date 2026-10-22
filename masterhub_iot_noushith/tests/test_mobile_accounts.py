import json
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock, patch

import pytest

from core import account_store
from core.devices import DeviceRegistry


@pytest.fixture
def client(tmp_path, monkeypatch, postgres_db):
    from app import create_app
    from api import accounts
    app = create_app()
    database_path = postgres_db
    app.config.update(TESTING=True, MASTERHUB_DATABASE=database_path)
    monkeypatch.setattr(accounts, 'device_registry', DeviceRegistry(database_path=database_path))
    accounts._attempts.clear()
    with app.test_client() as client:
        yield client, database_path, accounts.device_registry


def signup(client, username='test_user'):
    response = client.post('/api/auth/register', json=dict(username=username, password='test password 123'))
    assert response.status_code == 201
    return response.json


def phone(client, token, installation='test-installation-0001'):
    return client.post('/api/mobile/devices/register', headers={'Authorization': 'Bearer ' + token},
                       json=dict(installation_id=installation, name='Test Phone', device_category='mobile', platform='android'))


def test_registration_login_uniqueness_and_secret_storage(client):
    client, path, _ = client
    result = signup(client, 'Test_User')
    assert result['user']['username'] == 'test_user'
    assert client.post('/api/auth/register', json=dict(username='TEST_USER', password='another password')).status_code == 409
    login = client.post('/api/auth/login', json=dict(username='TEST_USER', password='test password 123'))
    assert login.status_code == 200
    assert login.json['token'] != result['token']
    assert client.post('/api/auth/login', json=dict(username='test_user', password='wrong password')).status_code == 401
    with account_store.database(path) as db:
        assert db.execute('SELECT password_hash FROM users').fetchone()['password_hash'] != 'test password 123'
        assert db.execute('SELECT token_hash FROM sessions LIMIT 1').fetchone()['token_hash'] != result['token']


def test_phone_id_is_stable_and_isolated_by_owner(client):
    client, path, registry = client
    first = signup(client)
    registered = phone(client, first['token'])
    assert registered.status_code == 201
    device = registered.json['device']
    assert device['device_category'] == 'mobile'
    assert registered.json['mqtt']['prefix'] == 'masterhub/mobile/' + device['device_id']
    assert phone(client, first['token']).json['device']['device_id'] == device['device_id']
    second = signup(client, 'other_user')
    assert phone(client, second['token']).json['device']['device_id'] != device['device_id']
    assert phone(client, first['token'], 'different-installation-001').json['device']['device_id'] != device['device_id']
    assert registry.get(device['device_id'])
    assert DeviceRegistry(database_path=path).get(device['device_id'])['name'] == 'Test Phone'


def test_expired_and_logged_out_sessions_cannot_register(client):
    client, path, _ = client
    result = signup(client)
    assert phone(client, 'invalid-token').status_code == 401
    client.post('/api/auth/logout', headers={'Authorization': 'Bearer ' + result['token']})
    assert phone(client, result['token']).status_code == 401
    result = client.post('/api/auth/login', json=dict(username='test_user', password='test password 123')).json
    with account_store.database(path) as db:
        db.execute('UPDATE sessions SET expires_at=0')
    assert phone(client, result['token']).status_code == 401


def test_bad_requests_and_throttling(client):
    client, _, _ = client
    assert client.post('/api/auth/register', json=[]).status_code == 400
    assert client.post('/api/auth/register', json=dict(username='bad name', password='12345678')).status_code == 400
    assert client.post('/api/auth/register', json=dict(username='valid', password='short')).status_code == 400
    for _ in range(7):
        client.post('/api/auth/login', json={})
    assert client.post('/api/auth/login', json={}).status_code == 429


def test_simultaneous_username_claims_have_one_winner(tmp_path, postgres_db):
    path = postgres_db
    with account_store.database(path):
        pass
    def register(_):
        try:
            account_store.authenticate(path, dict(username='same_user', password='test password 123'), True)
            return True
        except ValueError:
            return False
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(register, range(2))) == [False, True]


def test_json_migration_is_once_and_deletion_persists(tmp_path, postgres_db):
    legacy = tmp_path / 'devices.json'
    database_path = postgres_db
    registry = DeviceRegistry(legacy)
    registry.register('OLD_LAPTOP')
    migrated = DeviceRegistry(legacy, database_path)
    assert migrated.get('OLD_LAPTOP')
    assert migrated.unregister('OLD_LAPTOP')
    assert DeviceRegistry(legacy, database_path).get('OLD_LAPTOP') is None
    assert 'OLD_LAPTOP' in legacy.read_text()  # Original JSON is a preserved migration input.


def test_mobile_routing_preserves_command_contract(monkeypatch):
    import services.mobile_mqtt_service as transport
    import core.devices as devices
    from actions.media_jiosaavn_mobile import execute
    registry = DeviceRegistry()
    registry.register('MOBILE_TEST', device_category='mobile')
    registry.set_active_target('MOBILE_TEST')
    monkeypatch.setattr(devices, 'device_registry', registry)
    mock_service = Mock()
    with patch.object(transport, 'service_for_device', return_value=mock_service) as factory:
        execute('mobile_jiosaavn_next')
        factory.assert_called_once_with('MOBILE_TEST')
        mock_service.publish_command.assert_called_once_with('Right_Next_Song', 1.0, '', origin='dashboard')
    service = transport.MobileMQTTService(client=Mock(), device_id='MOBILE_TEST')
    assert service.topics['commands'] == 'masterhub/mobile/MOBILE_TEST/command'
    assert service.topics['heartbeat'] == 'masterhub/mobile/MOBILE_TEST/heartbeat'
