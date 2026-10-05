import json
from types import SimpleNamespace
from unittest.mock import patch, MagicMock

import pytest
from services import hardware_config
from services.mqtt_service import MQTTService, ROBOT_CAR_STATE
from actions.embedded.handler import embedded_handler
from app import app


@pytest.fixture
def config_file(tmp_path, monkeypatch):
    monkeypatch.setattr(hardware_config, 'PATH', tmp_path / 'hardware.json')


def test_settings_persist_and_route_exact_topic(config_file):
    saved = hardware_config.save_config({'car_topic': 'robotcar/AA:BB/control'})
    assert hardware_config.read_config() == saved
    with patch('actions.embedded.handler.mqtt_service.publish', return_value=True) as publish:
        result = embedded_handler.execute('car_stop')
    publish.assert_called_once_with(payload='LIFTCARSTOP', topic='robotcar/AA:BB/control')
    assert result['hardware_confirmed'] is False
    assert result['ack_topic'] == 'robotcar/AA:BB/ack'


@pytest.mark.parametrize('value', ['robotcar/+/control', 'wheelchair/id/control', 'robotcar//control', '', None])
def test_bad_topics_do_not_persist(config_file, value):
    with pytest.raises(ValueError):
        hardware_config.save_config({'car_topic': value})
    assert not hardware_config.PATH.exists()


@pytest.mark.parametrize('payload,online', [(b'CAR ONLINE', True), (b'CAR OFFLINE', False), (b'{"status":"ONLINE"}', True), (b'{"status":"OFFLINE"}', False)])
def test_firmware_plain_text_and_json_status(config_file, payload, online):
    client = MQTTService()
    message = SimpleNamespace(topic='robotcar/98:A3:16:BF:2C:C0/status', payload=payload)
    with patch.dict(ROBOT_CAR_STATE, dict(ROBOT_CAR_STATE)):
        client._on_message(None, None, message)
        assert ROBOT_CAR_STATE['online'] is online


def test_another_device_does_not_replace_selected_car(config_file):
    client = MQTTService()
    with patch.dict(ROBOT_CAR_STATE, dict(ROBOT_CAR_STATE)):
        original = dict(ROBOT_CAR_STATE)
        client._on_message(None, None, SimpleNamespace(topic='robotcar/OTHER/status', payload=b'ONLINE'))
        assert ROBOT_CAR_STATE == original


def test_mqtt_instances_have_distinct_client_ids(config_file):
    assert MQTTService().client_id != MQTTService().client_id


def test_publish_wait_is_bounded(config_file):
    client = MQTTService()
    client._client = MagicMock()
    client._connected = True
    assert client.publish('LIFTCARSTOP')
    client._client.publish.return_value.wait_for_publish.assert_called_once_with(timeout=5)


def test_cortex_buttons_start_and_stop_real_service():
    with app.test_client() as client:
        with patch('cortex.service.start_cortex') as start:
            assert client.post('/cortex/connect').status_code == 202
            start.assert_called_once()
        with patch('cortex.service.stop_cortex') as stop:
            assert client.post('/cortex/disconnect').status_code == 200
            stop.assert_called_once()


def test_invalid_hardware_settings_return_error(config_file):
    with app.test_client() as client:
        response = client.post('/api/hardware/config', json={'port': 99999})
        assert response.status_code == 400
        assert not hardware_config.PATH.exists()


def test_workflow_commands_are_registered():
    from services.workflow_service import build_workflow, load
    commands = [c['id'] for d in build_workflow()['domains'] for g in d['devices'] for c in g['commands']]
    assert commands
    assert set(commands) <= load('command_map.json').keys()
