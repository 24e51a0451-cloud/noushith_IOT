"""MQTT phone discovery and SQLite-backed unique device names."""
import atexit
import json
import logging
import re
import sqlite3
import threading
import time
import uuid

from core.account_store import database, DEFAULT_DATABASE
from core.devices import device_registry

log = logging.getLogger(__name__)


def register_device(payload, path=DEFAULT_DATABASE, registry=device_registry):
    device_id = str(uuid.UUID(payload.get('device_id', '')))
    username = payload.get('username')
    if not isinstance(username, str) or not re.fullmatch(r'[A-Za-z0-9_]{3,32}', username.strip()):
        raise ValueError('Use 3–32 letters, numbers or underscores for the username')
    username = username.strip().lower()
    platform = payload.get('device_type', '').lower()
    if platform not in ('android', 'ios'):
        raise ValueError('Expected Android or iOS device type')
    with database(path) as db:
        try:
            db.execute('''INSERT INTO mqtt_devices VALUES(?,?,?,?)
                          ON CONFLICT(device_id) DO UPDATE SET username=excluded.username,
                          device_type=excluded.device_type,updated_at=excluded.updated_at''',
                       (device_id, username, platform, int(time.time() * 1000)))
        except sqlite3.IntegrityError:
            raise ValueError('Username is already used by another device') from None
    prefix = 'bci/' + device_id
    record = registry.register(device_id, name=username, device_category='mobile', platform=platform,
                               capabilities=['ai_ml'], mqtt_prefix=prefix)
    return dict(status='REGISTERED', device_id=device_id, username=username, topic_prefix=prefix, device=record)


class MobileRegistrationService:
    def __init__(self):
        self.lock = threading.Lock()
        self.transport = None

    def start(self):
        with self.lock:
            if self.transport is not None:
                return
            from services.mobile_mqtt_service import MobileMQTTService
            transport = MobileMQTTService()
            transport.client.on_connect = lambda client, userdata, flags, rc: client.subscribe('bci/devices/register', qos=1) if rc == 0 else None
            transport.client.on_message = self.on_message
            transport.start()
            self.transport = transport

    def on_message(self, client, userdata, message):
        if message.topic != 'bci/devices/register' or message.retain or len(message.payload) > 4096:
            return
        try:
            payload = json.loads(message.payload)
            if not isinstance(payload, dict):
                return
            device_id = str(uuid.UUID(payload.get('device_id', '')))
            request_id = payload.get('request_id')
            if not isinstance(request_id, str) or not 1 <= len(request_id) <= 100:
                return
        except (ValueError, TypeError, AttributeError):
            return
        try:
            result = register_device(payload)
            from services.mobile_mqtt_service import service_for_device
            service_for_device(device_id).start()
        except (ValueError, TypeError, AttributeError) as error:
            result = dict(status='REJECTED', error=str(error), device_id=device_id)
        except Exception:
            log.exception('Unable to save MQTT device registration')
            result = dict(status='REJECTED', error='Registration unavailable. Please retry.', device_id=device_id)
        result['request_id'] = request_id
        client.publish(f'bci/{device_id}/registration', json.dumps(result), qos=1, retain=False)

    def stop(self):
        if self.transport:
            self.transport.stop()


mobile_registration = MobileRegistrationService()
atexit.register(mobile_registration.stop)
