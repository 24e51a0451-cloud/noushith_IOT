"""Mobile registration, command receipt, and lifecycle contract."""
import json
import time
import uuid
from types import SimpleNamespace
from unittest.mock import Mock, patch

from core.devices import DeviceRegistry
from services.mobile_mqtt_service import MobileMQTTService
from services.mobile_registration import MobileRegistrationService, register_device


def packet(topic, payload, retain=False):
    return SimpleNamespace(topic=topic, payload=json.dumps(payload).encode(), retain=retain)


def test_dedicated_registration_and_conflict(postgres_db):
    registry = DeviceRegistry(database_path=postgres_db)
    client = Mock()
    service = Mock()
    discovery = MobileRegistrationService()
    identifier = str(uuid.uuid4())
    register = lambda payload, **kwargs: register_device(payload, postgres_db, registry, **kwargs)
    with patch('services.mobile_registration.register_device', side_effect=register), patch(
            'services.mobile_mqtt_service.service_for_device', return_value=service):
        data = dict(device_uuid=identifier, requested_name='Vyshnavi', platform='android',
                    capabilities=['media', 'jiosaavn'], app_version='1.0.0', timestamp=1757400000000)
        discovery.on_message(client, None, packet('masterhub/mobile/register', data))
        assert client.publish.call_args.args[0] == f'masterhub/mobile/{identifier}/register_ack'
        assert json.loads(client.publish.call_args.args[1]) == dict(
            status='APPROVED', device_id='vyshnavi', device_uuid=identifier,
            topic_prefix='masterhub/mobile/vyshnavi', message='Registered successfully in PostgreSQL')
        assert client.publish.call_args.kwargs == dict(qos=1, retain=False)
        assert registry.get(identifier)['mqtt_prefix'] == 'masterhub/mobile/vyshnavi'
        assert 'jiosaavn' in registry.get(identifier)['capabilities']
        discovery.on_message(client, None, packet('masterhub/mobile/register', data))
        assert json.loads(client.publish.call_args.args[1])['status'] == 'APPROVED'
        data['device_uuid'] = str(uuid.uuid4())
        discovery.on_message(client, None, packet('masterhub/mobile/register', data))
        assert json.loads(client.publish.call_args.args[1])['error'] == 'Username already taken'
        client.reset_mock()
        discovery.on_message(client, None, packet('masterhub/mobile/register', data, True))
        discovery.on_message(client, None, packet('masterhub/mobile/vyshnavi/status', data))
        client.publish.assert_not_called()


def test_registration_subscription_and_invalid_requests():
    client = Mock()
    discovery = MobileRegistrationService()
    discovery.on_connect(client, None, None, 0)
    client.subscribe.assert_called_once_with('masterhub/mobile/register', qos=1)
    with patch('services.mobile_registration.register_device') as register:
        discovery.on_message(client, None, packet('masterhub/mobile/register', {'device_uuid': '../bad'}))
        client.publish.assert_not_called()
        discovery.on_message(client, None, packet('masterhub/mobile/register', dict(
            device_uuid=str(uuid.uuid4()), requested_name='bad/name', platform='android')))
        assert json.loads(client.publish.call_args.args[1])['status'] == 'REJECTED'
        register.assert_not_called()


def test_new_command_receipts_and_lifecycle():
    client = Mock()
    client.publish.return_value.rc = 0
    service = MobileMQTTService(client, device_id=str(uuid.uuid4()), topic_prefix='masterhub/mobile/vyshnavi')
    service.started = service.connected = True
    def receive(channel, data, retain=False):
        service._on_message(client, None, packet(service.topics[channel], dict(data, device_id='vyshnavi'), retain))
    receive('status', dict(device_id='vyshnavi', status='ONLINE', remote_state='ACTIVE'), True)
    assert not service.snapshot()['online']
    receive('heartbeat', dict(device_id='vyshnavi', status='alive', battery_level=84))
    assert service.snapshot()['can_send']
    result = service.publish_command('Right_Play_Pause', .89, 'Kesariya', origin='bci_prediction')
    payload = json.loads(client.publish.call_args.args[1])
    assert payload['command'] == 'PLAY_PAUSE'
    assert payload['target_device'] == 'vyshnavi'
    assert payload['origin'] == 'bci_prediction'
    assert payload['timestamp'] < payload['expires_at']
    receive('ack', dict(command_id=result['command_id'], status='SUCCESS', tier_used='Tier 1: MediaController'))
    assert service.snapshot()['commands'][-1]['status'] == 'SUCCESS'
    result = service.publish_command('PLAY_PAUSE', .62)
    receive('ack', dict(command_id=result['command_id'], status='FAILED', code='CONFIDENCE_BELOW_THRESHOLD', error='Below threshold'))
    assert service.snapshot()['commands'][-1]['ack']['code'] == 'CONFIDENCE_BELOW_THRESHOLD'
    receive('status', dict(status='OFFLINE', reason='Connection lost / abrupt disconnect'), True)
    assert not service.snapshot()['can_send']
