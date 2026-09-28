"""Build the dashboard from command mappings and observed connection state."""
import json
import time
from fnmatch import fnmatch
from pathlib import Path

from core.devices import device_registry
from services.hardware_config import read_config
from services.mqtt_service import mqtt_service, get_all_online_devices, get_robot_car_state, get_wheelchair_state
from services.usb_service import usb_service

MAPPINGS = Path(__file__).resolve().parents[1] / 'mappings'


def load(name):
    return json.loads((MAPPINGS / name).read_text(encoding='utf-8'))


def connection(ready, label, detail=''):
    return {'ready': bool(ready), 'label': label, 'detail': detail}


def build_workflow():
    config = load('workflow_map.json')
    routes = load('command_map.json')
    modes = load('mode_map.json')['modes']
    hardware = read_config()
    now = time.time()
    ttl = config['heartbeat_timeout_seconds']
    broker = mqtt_service._connected

    def fresh(record):
        status = str(record.get('status', '')).upper()
        return bool(record.get('_last_seen', record.get('last_seen', 0))) and now - record.get('_last_seen', record.get('last_seen', 0)) < ttl and status not in ('OFFLINE', 'UNKNOWN', 'DISCOVERED') and not status.endswith(' OFFLINE')

    target_id = device_registry.get_active_target()
    target = device_registry.get(target_id)
    if not target:
        desktop = connection(False, 'No target selected')
    elif target['transport'] == 'local':
        desktop = connection(True, 'Local host available', target_id)
    elif target['transport'] in ('usb', 'uart', 'serial'):
        usb = usb_service.get_status()
        simulated = usb.get('port') in ('SIMULATED', 'LOOPBACK', 'TEST', 'MOCK')
        desktop = connection(usb.get('connected') and not simulated, 'Simulated USB' if simulated else 'USB connected' if usb.get('connected') else 'USB disconnected', target_id)
    else:
        ready = broker and target.get('status') == 'ONLINE' and fresh(target)
        desktop = connection(ready, 'Target online' if ready else 'Target offline', target_id)

    statuses = {'desktop': desktop, 'ai_ml': desktop}
    observed = get_all_online_devices()
    iot_ready = broker and any(fresh(v) and v.get('domain') not in ('desktop', 'robotcar', 'wheelchair') and (k == 'esp32' or v.get('states')) for k, v in list(observed.items()))
    statuses['iot'] = connection(iot_ready, 'Device online' if iot_ready else 'No device heartbeat' if broker else 'MQTT disconnected')
    
    mobility = {}
    from services.mobile_mqtt_service import mobile_mqtt_service
    mobile = mobile_mqtt_service.snapshot()
    mobility['mobile_jiosaavn'] = connection(mobile['online'] and mobile['phone'].get('control_enabled'),
        'Phone ready' if mobile['online'] and mobile['phone'].get('control_enabled') else 'Phone offline or control disabled')
    for name, state in [('robot_car', get_robot_car_state()), ('wheelchair', get_wheelchair_state())]:
        topic = hardware[config['devices'][name]['topic_setting']]
        matches = state['device_id'] == topic.split('/')[1]
        ready = broker and matches and state.get('online') and fresh(state)
        label = 'Device online' if ready else ('MQTT disconnected' if not broker else (str(state['status']) if matches and str(state['status']).upper().endswith('OFFLINE') else 'No device heartbeat'))
        mobility[name] = connection(ready, label, topic)
    any_mobility = any(mobility[k]['ready'] for k in ('robot_car', 'wheelchair'))
    statuses['embedded'] = connection(any_mobility, 'Device online' if any_mobility else 'No device heartbeat' if broker else 'MQTT disconnected', ' · '.join(f"{config['devices'][k]['label']}: {mobility[k]['label']}" for k in ('robot_car', 'wheelchair')))

    from core.state import state_manager
    domains = {key: {'id': key, **info, 'switch_command': modes[info['mode']]['switch_command'],
                     'connection': statuses[key], 'devices': []} for key, info in config['domains'].items()}

    bci_workflow = config.get('bci_workflow', {})
    
    for domain_id, domain_info in domains.items():
        domain_devices = []
        for dev_id, dev_info in config['devices'].items():
            if dev_info.get('domain') != domain_id:
                continue
            if dev_id not in bci_workflow:
                continue
            
            bci_items = bci_workflow.get(dev_id, [])
            commands = []
            for item in bci_items:
                cmd_id = item['id']
                route = routes.get(cmd_id, {})
                action = route.get('action', cmd_id) if isinstance(route, dict) else cmd_id
                fields = next((fields for pattern, fields in config['parameters'].items() if fnmatch(action, pattern)), [])
                commands.append({
                    'id': cmd_id,
                    'label': item.get('label', cmd_id.replace('_', ' ').capitalize()),
                    'gesture': item.get('gesture'),
                    'action': action,
                    'parameters': fields,
                    'immediate': action.endswith('_stop') or item.get('gesture') in ('left+right', 'right+left'),
                })
            
            dev_mode = dev_info.get('mode', domain_info.get('mode'))
            switch_cmd = modes.get(dev_mode, {}).get('switch_command') or domain_info['switch_command']
            
            domain_devices.append({
                'id': dev_id,
                'label': dev_info.get('label', dev_id.replace('_', ' ').title()),
                'gesture': dev_info.get('gesture'),
                'mode': dev_mode,
                'connection': mobility.get(dev_id, statuses[domain_id]),
                'commands': commands,
                'switch_command': switch_cmd,
            })
        domain_info['devices'] = domain_devices

    return {
        'domains': list(domains.values()),
        'active_target': target_id,
        # Mobile presence comes from masterhub/mobile/<id>/heartbeat, not the
        # PC-agent registry's masterhub/devices/+/status subscription.
        'targets': mobile_mqtt_service.merge_target_presence(device_registry.list_all()),
        'reset_command': modes['IDLE']['switch_command'],
        'state_mode': state_manager.mode.value,
        'navigation': config['navigation']
    }
