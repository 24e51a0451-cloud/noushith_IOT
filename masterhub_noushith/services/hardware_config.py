"""Persist the broker and exact firmware topics without changing command payloads."""
import json
import os
from pathlib import Path
from threading import RLock

PATH = Path(__file__).resolve().parents[1] / '.runtime' / 'hardware.json'
LOCK = RLock()
DEFAULTS = {
    'host': os.getenv('MQTT_HOST', '52.21.249.6'), 'port': int(os.getenv('MQTT_PORT', '1883')),
    'car_topic': os.getenv('ROBOT_CAR_TOPIC', 'robotcar/98:A3:16:BF:2C:C0/control'),
    'chair_topic': os.getenv('WHEELCHAIR_TOPIC', 'wheelchair/98:A3:16:BF:2C:C1/control'),
}

def read_config():
    with LOCK:
        return {**DEFAULTS, **(json.loads(PATH.read_text()) if PATH.exists() else {})}

def save_config(data):
    if not isinstance(data, dict):
        raise ValueError('Settings must be a JSON object')
    config = {**read_config(), **{k: v for k, v in data.items() if k in DEFAULTS}}
    if not isinstance(config['host'], str) or not config['host'].strip() or any(c.isspace() for c in config['host']):
        raise ValueError('Enter a broker hostname or IP address')
    try:
        config['port'] = int(config['port'])
    except (ValueError, TypeError):
        raise ValueError('Port must be between 1 and 65535')
    if not 1 <= config['port'] <= 65535:
        raise ValueError('Port must be between 1 and 65535')
    for key in ('car_topic', 'chair_topic'):
        topic = config[key]
        prefix = 'robotcar' if key == 'car_topic' else 'wheelchair'
        if not isinstance(topic, str) or len(topic.split('/')) != 3 or topic.split('/')[0] != prefix or topic.split('/')[2] != 'control' or not topic.split('/')[1] or any(c in topic for c in '+#\x00'):
            raise ValueError(f'{key} must be {prefix}/DEVICE_ID/control without wildcards')
    with LOCK:
        PATH.parent.mkdir(exist_ok=True)
        temp = PATH.with_suffix('.tmp')
        temp.write_text(json.dumps(config, indent=2))
        temp.replace(PATH)
    return config
