"""Old topics must never be selected, subscribed to, or processed."""
import json
from types import SimpleNamespace
from unittest.mock import Mock, patch
import pytest
from services.mobile_topics import get_device_topics
from services.mobile_registration import MobileRegistrationService
from services.mobile_mqtt_service import MobileMQTTService, service_for_device


def test_old_registration_is_ignored():
    client = Mock()
    message = SimpleNamespace(topic='bci/devices/register', retain=False,
                              payload=b'{"device_id":"old", "username":"phone"}')
    with patch('services.mobile_registration.register_device') as register:
        MobileRegistrationService().on_message(client, None, message)
        register.assert_not_called()
    client.publish.assert_not_called()


def test_old_environment_and_prefix_cannot_restore_old_topics(monkeypatch):
    monkeypatch.setenv('BCI_MOBILE_TOPIC_PREFIX', 'bci/phone')
    monkeypatch.setenv('BCI_MOBILE_COMMANDS_TOPIC', 'bci/phone/commands')
    service = MobileMQTTService(Mock(), device_id='phone', topic_prefix='bci/phone')
    assert set(service.topics.values()) == set(get_device_topics('phone').values())
    service._on_connect(service.client, None, None, 0)
    assert {call.args[0] for call in service.client.subscribe.call_args_list} == {
        'masterhub/mobile/phone/' + channel for channel in ('ack', 'status', 'heartbeat')}
    for channel in ('media', 'error', 'control'):
        service._on_message(None, None, SimpleNamespace(topic='masterhub/mobile/phone/' + channel,
            retain=False, payload=b'{"device_id":"phone", "status":"ONLINE"}'))
    assert not service.snapshot()['online']
    assert service.snapshot()['media'] == {}


def test_saved_old_device_routes_to_new_username_prefix():
    import services.mobile_mqtt_service as module
    with patch.dict(module._device_services, {}, clear=True), patch('core.devices.device_registry.get',
            return_value=dict(name='vyshnavi', mqtt_prefix='bci/old-uuid')):
        service = service_for_device('old-uuid')
        assert service.topics['commands'] == 'masterhub/mobile/vyshnavi/command'
        service.started = service.connected = True
        service.last_seen = __import__('time').time()
        service.phone = dict(control_enabled=True)
        with patch.object(service.client, 'publish', return_value=Mock(rc=0)) as publish:
            assert service.publish_command('PLAY_PAUSE', 1)['success']
            assert json.loads(publish.call_args.args[1])['target_device'] == 'vyshnavi'
        service.started = False


@pytest.mark.parametrize('device_id', ['', 'phone/name', '+', '#', 'phone/#'])
def test_invalid_topic_ids_are_rejected(device_id):
    with pytest.raises(ValueError):
        get_device_topics(device_id)
