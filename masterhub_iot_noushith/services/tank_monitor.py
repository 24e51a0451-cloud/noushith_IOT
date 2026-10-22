"""Read-only tank telemetry with local, persisted height calibration."""
import json
import math
import os
from pathlib import Path
from threading import RLock
import time

PATH = Path(__file__).resolve().parents[1] / '.runtime' / 'tank.json'
LOCK = RLock()


def number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        return None
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (ValueError, OverflowError):
        return None


def validate_config(data):
    if not isinstance(data, dict) or data.get('unit') not in ('cm', 'ft'):
        raise ValueError('Choose cm or ft for the tank height.')
    height = number(data.get('height'))
    height_cm = height * (30.48 if data['unit'] == 'ft' else 1) if height is not None else None
    if height_cm is not None:
        height_cm = round(height_cm, 8)
    if height_cm is None or not 5 <= height_cm <= 5000:
        raise ValueError('Tank height must be between 5 and 5000 cm (0.164042–164.041995 ft).')
    return {'height': height, 'unit': data['unit'], 'height_cm': height_cm}


def read_config():
    with LOCK:
        if not PATH.exists():
            return {'height': None, 'unit': 'cm', 'height_cm': None}
        return validate_config(json.loads(PATH.read_text(encoding='utf-8')))


def save_config(data):
    config = validate_config(data)
    with LOCK:
        PATH.parent.mkdir(parents=True, exist_ok=True)
        temporary = PATH.with_suffix('.tmp')
        temporary.write_text(json.dumps(config, allow_nan=False), encoding='utf-8')
        temporary.replace(PATH)
    return config


def snapshot(sensors, states, connected, now=None):
    now = time.time() if now is None else now
    # shortcut: one selected tank; add per-sensor calibration if the gateway multiplexes tanks.
    device_id = os.getenv('MASTERHUB_TANK_DEVICE_ID', 'esp32').strip() or 'esp32'
    packet = sensors.get(device_id)
    packet = dict(packet) if isinstance(packet, dict) else {}
    warnings = []
    try:
        config = read_config()
    except (OSError, ValueError):
        config = {'height': None, 'unit': 'cm', 'height_cm': None}
        warnings.append('Saved tank height is unavailable. Enter and save the height again.')
    distance = number(packet.get('distance'))
    height = config['height_cm']
    percent = depth = None
    if height is None:
        warnings.append('Set the tank height to calculate the water level.')
    elif packet:
        if distance is None or distance < 0 or distance > height:
            warnings.append('Invalid sensor distance. Check the reading, height and sensor mounting.')
        else:
            depth = height - distance
            percent = 100 * depth / height
    float_value = packet.get('float')
    float_value = int(float_value) if isinstance(float_value, (int, float, str)) and str(float_value) in ('0', '1', '0.0', '1.0') else None
    if float_value == 1:
        warnings.append('Float sensor reports overflow. No automatic pump action is taken.')
    received = number(packet.get('_timestamp'))
    age = now - received if received is not None and 0 < received <= now else None
    stale_after = number(os.getenv('MASTERHUB_TANK_STALE_SECONDS', '30'))
    stale_after = stale_after if stale_after is not None and stale_after > 0 else 30
    stale = bool(packet) and (not connected or packet.get('_retained', False) or age is None or age > stale_after)
    if stale:
        warnings.append('Stale or unverified reading. Values are last known, not a fresh measurement.')
    pump = states.get(device_id, {})
    pump = pump.get('pump') if isinstance(pump, dict) else None
    if isinstance(pump, str):
        pump = pump.upper() if pump.upper() in ('ON', 'OFF') else None
    elif isinstance(pump, (bool, int)) and pump in (0, 1):
        pump = 'ON' if pump else 'OFF'
    else:
        pump = None
    return dict(config=config, device_id=device_id, distance_cm=distance,
                water_depth_cm=depth, percent=percent, float_value=float_value,
                rssi=number(packet.get('rssi')), pump=pump, mqtt_connected=bool(connected),
                received_at=received, age_seconds=round(age, 1) if age is not None else None,
                stale_after_seconds=stale_after,
                status='no_data' if not packet else 'stale' if stale else 'invalid' if percent is None and height is not None else 'live',
                warnings=warnings)
