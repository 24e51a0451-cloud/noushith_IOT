import json

import pytest

from core.devices import DeviceRegistry


def test_categories_survive_restart_and_removal(tmp_path):
    path = tmp_path / 'devices.json'
    registry = DeviceRegistry(path)
    registry.register('LAPTOP_TEST', name='Desk laptop')
    registry.register('PHONE_TEST', device_category='mobile', status='ONLINE')
    saved = {d['device_id']: d for d in json.loads(path.read_text())['devices']}
    assert saved['LAPTOP_TEST']['device_category'] == 'laptop'
    assert saved['PHONE_TEST']['device_type'] == 'mobile'
    assert saved['PHONE_TEST']['platform'] == 'android'
    assert saved['PHONE_TEST']['capabilities'] == ['ai_ml']
    reloaded = DeviceRegistry(path)
    assert reloaded.get('PHONE_TEST')['status'] == 'OFFLINE'
    reloaded.register('PHONE_TEST', name='Updated phone')
    reloaded.update_status('PHONE_TEST', 'ONLINE')
    assert reloaded.get('PHONE_TEST')['device_category'] == 'mobile'
    assert reloaded.unregister('PHONE_TEST')
    assert DeviceRegistry(path).get('PHONE_TEST') is None
    assert DeviceRegistry(path).get('LAPTOP_TEST')['name'] == 'Desk laptop'


def test_invalid_category_does_not_register(tmp_path):
    registry = DeviceRegistry(tmp_path / 'devices.json')
    with pytest.raises(ValueError):
        registry.register('INVALID', device_category='tablet')
    assert registry.get('INVALID') is None


def test_registration_api_persists_category(tmp_path, monkeypatch):
    from app import app
    from api import routes

    path = tmp_path / 'devices.json'
    monkeypatch.setattr(routes, 'device_registry', DeviceRegistry(path))
    client = app.test_client()
    for category in ('mobile', 'laptop'):
        response = client.post('/api/devices/register', json={
            'device_id': category + '_TEST', 'device_category': category,
        })
        assert response.status_code == 201
        assert response.json['device']['device_category'] == category
        assert DeviceRegistry(path).get(category + '_TEST')['device_category'] == category
    assert client.post('/api/devices/register', json={
        'device_id': 'INVALID', 'device_category': 'tablet',
    }).status_code == 400
