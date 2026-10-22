"""MQTT phone discovery and PostgreSQL-backed unique device names."""
import atexit
import json
import logging
import re
import psycopg
import threading
import time
import uuid

from core.account_store import database, DEFAULT_DATABASE
from core.devices import device_registry
from services.mobile_topics import TOPIC_DISCOVERY, TOPIC_REGISTER_ACK

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
    capabilities = payload.get('capabilities', [])
    if not isinstance(capabilities, list) or not all(isinstance(item, str) for item in capabilities):
        raise ValueError('capabilities must be a list of strings')
    with database(path) as db:
        try:
            db.execute('''INSERT INTO mqtt_devices VALUES(%s,%s,%s,%s)
                          ON CONFLICT(device_id) DO UPDATE SET username=excluded.username,
                          device_type=excluded.device_type,updated_at=excluded.updated_at''',
                       (device_id, username, platform, int(time.time() * 1000)))
        except psycopg.errors.UniqueViolation:
            raise ValueError('Username is already used by another device') from None
    prefix = 'masterhub/mobile/' + username
    record = registry.register(device_id, name=username, device_category='mobile', platform=platform,
                               capabilities=list(dict.fromkeys(['ai_ml'] + capabilities)), mqtt_prefix=prefix)
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
            transport.client.on_connect = self.on_connect
            transport.client.on_message = self.on_message
            transport.start()
            self.transport = transport

    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            client.subscribe(TOPIC_DISCOVERY, qos=1)

    def on_registration(self, client, message):
        if message.retain or len(message.payload) > 4096:
            return
        try:
            payload = json.loads(message.payload)
            if not isinstance(payload, dict):
                return
            identifier = str(uuid.UUID(payload.get('device_uuid', '')))
        except (ValueError, TypeError, AttributeError):
            return
        try:
            name = payload.get('requested_name')
            if not isinstance(name, str) or not re.fullmatch(r'[A-Za-z0-9_]{3,32}', name.strip()):
                raise ValueError('Use 3-32 letters, numbers or underscores for the username')
            name = name.strip().lower()
            capabilities = payload.get('capabilities', [])
            prefix = 'masterhub/mobile/' + name
            register_device(dict(device_id=identifier, username=name,
                                 device_type=payload.get('platform', ''), capabilities=capabilities))
            from services.mobile_mqtt_service import service_for_device
            service_for_device(identifier).start()
            result = dict(status='APPROVED', device_id=name, device_uuid=identifier,
                          topic_prefix=prefix, message='Registered successfully in PostgreSQL')
        except (ValueError, TypeError, AttributeError) as error:
            detail = str(error)
            if detail == 'Username is already used by another device':
                detail = 'Username already taken'
            result = dict(status='REJECTED', device_uuid=identifier, error=detail)
        except Exception:
            log.exception('Unable to save MQTT device registration')
            result = dict(status='REJECTED', device_uuid=identifier,
                          error='Registration unavailable. Please retry.')
        client.publish(TOPIC_REGISTER_ACK.format(device_uuid=identifier), json.dumps(result), qos=1, retain=False)

    def on_message(self, client, userdata, message):
        if message.topic == TOPIC_DISCOVERY:
            self.on_registration(client, message)

    def stop(self):
        if self.transport:
            self.transport.stop()


mobile_registration = MobileRegistrationService()
atexit.register(mobile_registration.stop)
