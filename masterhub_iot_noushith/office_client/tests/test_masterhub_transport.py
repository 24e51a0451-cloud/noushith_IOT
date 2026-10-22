"""Exercise real routing/transport code without production DB, broker or COM."""
import importlib.util
import json
import logging
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock

import pytest

from office_client.protocol import CommandReceiver
from services import office_results

ROOT = Path(__file__).resolve().parents[2]


def load(path):
    spec = importlib.util.spec_from_file_location('isolated_' + Path(path).stem, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def stub(monkeypatch, name, **values):
    module = ModuleType(name)
    module.__dict__.update(values)
    monkeypatch.setitem(sys.modules, name, module)
    return module


@pytest.fixture
def hub(monkeypatch):
    registry = MagicMock()
    registry.get_active_target.return_value = 'PC_TEST'
    registry.get.return_value = {'transport':'mqtt'}
    stub(monkeypatch, 'core.devices', device_registry=registry)
    stub(monkeypatch, 'services.logger_service', get_logger=logging.getLogger)
    stub(monkeypatch, 'services.event_store', record_event=MagicMock(), record_mqtt=MagicMock())
    stub(monkeypatch, 'services.hardware_config', read_config=lambda: {'host':'127.0.0.1','port':1883})
    for name in ('notepad','chrome','youtube','system_apps','gmail'):
        stub(monkeypatch, 'actions.desktop.' + name)
    mqtt_module = load('services/mqtt_service.py')
    uart_module = load('services/usb_service.py')
    monkeypatch.setitem(sys.modules, 'services.mqtt_service', mqtt_module)
    monkeypatch.setitem(sys.modules, 'services.usb_service', uart_module)
    handler = load('actions/desktop/handler.py').DesktopHandler()
    yield handler, mqtt_module, uart_module, registry


@pytest.mark.parametrize('transport', ['mqtt','usb','uart','serial'])
def test_hub_to_client_to_result_roundtrip(hub, tmp_path, transport):
    handler, mqtt_module, uart_module, registry = hub
    registry.get.return_value = {'transport':transport}
    outbound = []
    mqtt_module.mqtt_service.publish_json = lambda envelope, **kwargs: outbound.append(envelope) or True
    uart = uart_module.usb_service
    uart._connected = True; uart._port = 'COM_TEST'; uart._serial = MagicMock()
    uart._serial.write.side_effect = lambda raw: outbound.append(json.loads(raw)) or len(raw)
    published = handler.execute('office_excel_open')
    assert published['status'] == 'PENDING'
    assert len(outbound) == 1
    assert outbound[0]['command_id'] == published['command_id']
    execute = MagicMock(return_value={'success':True, 'status':'SUCCESS', 'message':'Workbook opened'})
    receiver = CommandReceiver('PC_TEST', execute, tmp_path / 'journal.db')
    response = receiver.handle(json.dumps(outbound[0]))
    receiver.close()
    if transport == 'mqtt':
        message = SimpleNamespace(topic='masterhub/devices/PC_TEST/ack', payload=json.dumps(response).encode(), retain=False)
        mqtt_module.mqtt_service._on_message(None, None, message)
    else:
        uart._running = True
        def read():
            uart._running = False
            return (json.dumps(response) + '\n').encode()
        uart._serial.readline.side_effect = read
        uart._rx_worker()
    result = office_results.get(published['command_id'])
    assert result['status'] == 'SUCCESS'
    assert result['message'] == 'Workbook opened'
    execute.assert_called_once()


def test_mqtt_failure_result_reaches_hub(hub):
    handler, mqtt_module, _, _ = hub
    mqtt_module.mqtt_service.publish_json = lambda *args, **kwargs: True
    published = handler.execute('office_word_open')
    response = {'protocol':'masterhub','version':'1.0','message_type':'command_result',
                'source':'PC_TEST','domain':'desktop','action':'office_word_open',
                'command_id':published['command_id'],'success':False,'status':'FAILED','error':'Office missing'}
    mqtt_module.mqtt_service._on_message(None, None, SimpleNamespace(
        topic='masterhub/devices/PC_TEST/error',payload=json.dumps(response).encode(), retain=False))
    assert office_results.get(published['command_id'])['error'] == 'Office missing'


def test_disconnect_is_not_execution_success(hub):
    handler, _, _, registry = hub
    registry.get.return_value = {'transport':'uart'}
    result = handler.execute('office_word_open')
    assert not result['success']
    assert 'result_url' not in result


def test_local_execution_and_unregistered_target(hub):
    handler, _, _, registry = hub
    handler._office_worker = MagicMock()
    handler._office_worker.execute.return_value = {'success':True,'status':'SUCCESS'}
    assert handler.execute('office_word_open', {'target':'local'})['success']
    handler._office_worker.execute.assert_called_once()
    registry.get.return_value = None
    assert not handler.execute('office_word_open', {'target':'UNKNOWN'})['success']


def test_edit_confirmation_checked_before_transport(hub):
    handler, mqtt_module, _, _ = hub
    mqtt_module.mqtt_service.publish_json = MagicMock()
    assert not handler.execute('office_word_delete', {'confirm':'false'})['success']
    mqtt_module.mqtt_service.publish_json.assert_not_called()


def test_existing_notepad_routing_is_preserved(hub):
    handler, mqtt_module, _, _ = hub
    mqtt_module.mqtt_service.publish_json = MagicMock(return_value=True)
    result = handler.execute('open_notepad')
    assert result['success']
    assert 'result_url' not in result
    envelope = mqtt_module.mqtt_service.publish_json.call_args.args[0]
    assert envelope['action'] == 'open_notepad'


def test_workflow_contains_office_without_displacing_other_apps(monkeypatch, hub):
    handler, mqtt_module, uart_module, registry = hub
    registry.get_active_target.return_value = 'Local Host'
    registry.get.return_value = {'transport':'local'}
    registry.list_all.return_value = []
    mobile = MagicMock()
    mobile.snapshot.return_value = {'online':False,'phone':{'control_enabled':False}}
    mobile.merge_target_presence.return_value = []
    stub(monkeypatch, 'services.mobile_mqtt_service', mobile_mqtt_service=mobile, selected_mobile_service=lambda:mobile)
    stub(monkeypatch, 'core.state', state_manager=SimpleNamespace(mode=SimpleNamespace(value='IDLE')))
    stub(monkeypatch, 'services.hardware_config', read_config=lambda: {
        'car_topic':'robotcar/test/control','chair_topic':'wheelchair/test/control'})
    workflow = load('services/workflow_service.py').build_workflow()
    desktop = next(domain for domain in workflow['domains'] if domain['id'] == 'desktop')
    apps = {device['id']:device for device in desktop['devices']}
    assert {'youtube','chrome','gmail','notepad','office_excel','office_word','office_powerpoint'} <= apps.keys()
    assert apps['notepad']['gesture'] == 'left+right'
    assert apps['office']['gesture'] == 'left'
    assert not apps['office']['parent']
    for app in ('excel','word','powerpoint'):
        assert apps['office_' + app]['parent'] == 'office'
        assert apps['office_' + app]['commands']


def test_release_includes_office_dependencies():
    files = {path.relative_to(ROOT).as_posix() for path in load('tools/package_release.py').release_files()}
    assert {'office_client/office.py','office_client/content.py','office_client/protocol.py'} <= files
