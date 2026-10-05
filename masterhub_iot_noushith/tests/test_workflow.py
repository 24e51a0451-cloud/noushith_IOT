import time
from unittest.mock import patch

from services import workflow_service as workflow
from core.devices import DeviceRegistry


def test_new_mapping_appears_without_frontend_changes():
    original = workflow.load
    def load(name):
        result = original(name)
        if name == 'workflow_map.json':
            result['bci_workflow']['youtube'].append({'id': 'new_tool_run', 'label': 'New Tool', 'gesture': 'push'})
        elif name == 'command_map.json':
            result['new_tool_run'] = {'domain': 'desktop', 'action': 'new_tool_run'}
        return result
    with patch.object(workflow, 'load', side_effect=load):
        data = workflow.build_workflow()
    assert any(c['id'] == 'new_tool_run' for d in data['domains'] for group in d['devices'] for c in group['commands'])


def test_mapping_aliases_are_not_duplicate_buttons():
    data = workflow.build_workflow()
    for domain in data['domains']:
        for device in domain['devices']:
            actions = [c['action'] for c in device['commands']]
            assert len(actions) == len(set(actions))


def test_broker_connection_alone_does_not_mean_device_online():
    with patch.object(workflow.mqtt_service, '_connected', True), patch.object(workflow, 'get_all_online_devices', return_value={}):
        domains = {d['id']: d for d in workflow.build_workflow()['domains']}
    assert not domains['iot']['connection']['ready']


def test_stale_desktop_heartbeat_is_offline():
    registry = DeviceRegistry()
    registry.register('test', status='ONLINE')
    registry.set_active_target('test')
    registry._devices['test']['last_seen'] = time.time() - 1000
    with patch.object(workflow, 'device_registry', registry), patch.object(workflow.mqtt_service, '_connected', True):
        domains = {d['id']: d for d in workflow.build_workflow()['domains']}
    assert not domains['desktop']['connection']['ready']


def test_registry_contains_no_demo_nodes():
    registry = DeviceRegistry()
    assert [d['device_id'] for d in registry.list_all()] == ['Local Host', 'PC_001']
    registry.register('new-remote')
    assert registry.get('new-remote')['status'] == 'OFFLINE'


def test_command_fields_and_unsupported_stub():
    commands = {c['action']: c for d in workflow.build_workflow()['domains'] for group in d['devices'] for c in group['commands']}
    assert commands['compose_gmail']['parameters'] == ['to', 'subject', 'body']
    assert commands['car_stop']['immediate'] is True
    assert 'album_search' not in commands


def test_iot_catalog_includes_left_light_command():
    domains = {domain['id']: domain for domain in workflow.build_workflow()['domains']}
    iot = domains['iot']
    assert [device['id'] for device in iot['devices']] == ['light', 'fan', 'pump']
    commands = {
        command['id']
        for device in iot['devices']
        for command in device['commands']
    }
    assert {'left_light_on', 'left_fan_on', 'left_pump_on'} <= commands
    assert 'device_tools' not in commands
