"""Independent MQTT transport for the Android companion. No hardware broker state."""
import atexit
from services.event_store import record_event, record_mqtt
import copy
import json
import os
from pathlib import Path
import threading
import time
import uuid
from collections import OrderedDict

import paho.mqtt.client as mqtt
from dotenv import load_dotenv
from services.mobile_topics import MOBILE_DEVICE_ID, get_device_topics

load_dotenv(Path(__file__).resolve().parents[1] / '.env')


class MobileMQTTService:
    def __init__(self, client=None, device_id=None, topic_prefix=None):
        self.host = os.getenv('BCI_MOBILE_MQTT_HOST', '52.21.249.6')
        self.port = int(os.getenv('BCI_MOBILE_MQTT_PORT', '1883'))
        self.device_id = device_id or MOBILE_DEVICE_ID
        # Saved prefixes can choose a name only within the current namespace.
        self.topic_device_id = (topic_prefix.rstrip('/').removeprefix('masterhub/mobile/')
                                if topic_prefix and topic_prefix.startswith('masterhub/mobile/')
                                else self.device_id)
        self.topics = get_device_topics(self.topic_device_id)
        self.topics['commands'] = self.topics.pop('command')
        self.timeout = float(os.getenv('BCI_MOBILE_ACK_TIMEOUT', '8'))
        self.heartbeat_timeout = float(os.getenv('BCI_MOBILE_HEARTBEAT_TIMEOUT', '35'))
        self.client = client or mqtt.Client(client_id='masterhub-mobile-' + uuid.uuid4().hex[:12])
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message
        self.client.reconnect_delay_set(1, 30)
        if os.getenv('BCI_MOBILE_MQTT_USERNAME'):
            self.client.username_pw_set(os.environ['BCI_MOBILE_MQTT_USERNAME'], os.getenv('BCI_MOBILE_MQTT_PASSWORD'))
        if os.getenv('BCI_MOBILE_MQTT_TLS', '').lower() == 'true':
            ca_file = os.getenv('BCI_MOBILE_MQTT_CA_FILE')
            if ca_file:
                ca_file = str(Path(__file__).resolve().parents[1] / ca_file)
            self.client.tls_set(ca_certs=ca_file or None)
        self.lock = threading.RLock()
        self.started = self.connected = False
        self.last_seen = 0
        self.phone = {}
        self.media = {}
        self.last_error = {}
        self.commands = OrderedDict()

    def start(self):
        with self.lock:
            if self.started:
                return
            self.client.connect_async(self.host, self.port, keepalive=30)
            self.client.loop_start()
            self.started = True

    def stop(self):
        with self.lock:
            started, self.started = self.started, False
        if started:
            self.client.disconnect()
            self.client.loop_stop()

    def _on_connect(self, client, userdata, flags, rc):
        record_event("connection", self.device_id, "BROKER_CONNECTED" if rc == 0 else "BROKER_FAILED", {"return_code": rc})
        with self.lock:
            self.connected = rc == 0
        if rc == 0:
            for name in ('ack', 'status', 'heartbeat'):
                client.subscribe(self.topics[name], qos=1)

    def _on_disconnect(self, client, userdata, rc):
        record_event("connection", self.device_id, "BROKER_DISCONNECTED", {"return_code": rc})
        with self.lock:
            self.connected = False
            self.last_seen = 0

    def _on_message(self, client, userdata, message):
        try:
            if len(message.payload) > 65536:
                return
            data = json.loads(message.payload)
            if not isinstance(data, dict):
                return
        except (ValueError, UnicodeError):
            return
        if message.topic not in (self.topics['ack'], self.topics['status'], self.topics['heartbeat']):
            return
        if data.get('device_id') != self.topic_device_id:
            return
        if message.retain and message.topic != self.topics['status']:
            return
        record_mqtt(message.topic, data, device_id=self.device_id, retained=message.retain)
        with self.lock:
            if message.topic == self.topics['ack']:
                if not isinstance(data.get('command_id'), str):
                    return
                item = self.commands.get(data['command_id'])
                if item and item['status'] in ('PENDING', 'TIMEOUT') and data.get('status') in ('SUCCESS', 'FAILED', 'REJECTED'):
                    item.update(status=data['status'], ack=data)
            elif message.topic in (self.topics['status'], self.topics['heartbeat']):
                data = dict(data)
                state = str(data.get('status', '')).upper()
                if message.topic == self.topics['heartbeat'] and state != 'ALIVE':
                    return
                if message.topic == self.topics['status'] and state not in ('ONLINE', 'OFFLINE'):
                    return
                if state in ('ONLINE', 'OFFLINE'):
                    data['online'] = state != 'OFFLINE'
                remote = str(data.get('remote_state', '')).upper()
                if state == 'OFFLINE':
                    data['control_enabled'] = False
                elif message.topic == self.topics['status']:
                    data['control_enabled'] = remote == 'ACTIVE'
                self.phone.update(data)
                # Retained online announcements cannot establish fresh liveness.
                if data.get('online') is False:
                    self.last_seen = 0
                elif not message.retain:
                    self.last_seen = time.time()

    def snapshot(self):
        with self.lock:
            now = time.time()
            online = bool(self.connected and self.last_seen and now - self.last_seen < self.heartbeat_timeout)
            can_send = bool(online and self.phone.get('control_enabled') is True)
            for item in self.commands.values():
                if item['status'] == 'PENDING' and now > item['deadline']:
                    item['status'] = 'TIMEOUT'
                    record_event('command_result', self.device_id, 'TIMEOUT', item, command_id=item['command_id'])
            return copy.deepcopy({
                'broker_connected': self.connected,
                'online': online, 'can_send': can_send,
                'presence_unknown': False,
                'last_seen': self.last_seen, 'phone': self.phone,
                'media': self.media, 'commands': list(self.commands.values())[-50:],
                'broker_host': self.host, 'broker_port': self.port, 'topics': self.topics,
                'last_error': self.last_error,
            })

    def merge_target_presence(self, targets):
        """Use the phone heartbeat as the source of truth for its target pill.

        The generic device registry only understands PC-agent status topics.  A
        mobile target may still be registered there for selection, but its
        liveness is published on the separate mobile namespace.
        """
        snapshot = self.snapshot()
        merged = []
        for target in targets:
            target = dict(target)
            if target.get('device_category') == 'mobile' and target.get('device_id') != self.device_id:
                service = service_for_device(target['device_id'])
                service.start()
                presence = service.snapshot()
                target.update(status='ONLINE' if presence['online'] else 'OFFLINE', last_seen=presence['last_seen'],
                              connection_source='mobile_heartbeat')
            if target.get('device_id') == self.device_id:
                target['status'] = 'ONLINE' if snapshot['online'] else 'OFFLINE'
                target['last_seen'] = snapshot['last_seen']
                target['transport'] = 'mqtt'
                target['platform'] = 'android'
                target['connection_source'] = 'mobile_heartbeat'
            merged.append(target)
        return merged

    def publish_command(self, command, confidence, query='', origin='dashboard'):
        self.start()
        with self.lock:
            if not self.snapshot()['online'] and not self.snapshot()['can_send']:
                return {'success': False, 'error': 'Phone offline or heartbeat unavailable'}
            if self.phone.get('control_enabled') is not True:
                return {'success': False, 'error': 'Enable remote control on the phone'}
            now = time.time()
            if command == 'LAUNCH':
                command = 'Right_JioSaavn'
            if command == 'Right_Return_to_Home':
                return {'success': False, 'error': 'Android contract does not support Return to Home'}
            if command == 'Right_Play_Pause':
                command = 'PLAY_PAUSE'
            identifier = str(uuid.uuid4())
            timeout = max(self.timeout, 45) if command == 'SEARCH' else self.timeout
            payload = dict(command=command, confidence=confidence, query=query,
                           target_device=self.topic_device_id,
                           origin=origin, timestamp=int(now * 1000),
                           command_id=identifier, expires_at=int((now + timeout) * 1000))
            item = dict(command_id=identifier, command=command, status='PENDING', deadline=now + timeout)
            self.commands[identifier] = item
            while len(self.commands) > 200:
                self.commands.popitem(last=False)
            info = self.client.publish(self.topics['commands'], json.dumps(payload), qos=1, retain=False)
            if info.rc != mqtt.MQTT_ERR_SUCCESS:
                item['status'] = 'FAILED'
                record_mqtt(self.topics['commands'], payload, device_id=self.device_id, outgoing=True, status='FAILED')
                return {'success': False, 'error': 'MQTT publish failed', 'command_id': identifier}
            record_mqtt(self.topics['commands'], payload, device_id=self.device_id, outgoing=True, status='PENDING')
            return {'success': True, 'status': 'PENDING', 'command_id': identifier,
                    'detail': 'Sent to phone; awaiting execution acknowledgement'}


mobile_mqtt_service = MobileMQTTService()
atexit.register(mobile_mqtt_service.stop)

_device_services = {}
_services_lock = threading.Lock()


def service_for_device(device_id):
    if device_id == mobile_mqtt_service.device_id:
        return mobile_mqtt_service
    with _services_lock:
        from core.devices import device_registry
        device = device_registry.get(device_id) or {}
        existing = _device_services.get(device_id)
        prefix = device.get('mqtt_prefix', '')
        if not prefix.startswith('masterhub/mobile/'):
            prefix = 'masterhub/mobile/' + (device.get('name') if prefix else device_id)
        command_topic = prefix.rstrip('/') + '/command'
        if existing and prefix and existing.topics['commands'] != command_topic:
            existing.stop()
            del _device_services[device_id]
        if device_id not in _device_services:
            _device_services[device_id] = MobileMQTTService(device_id=device_id, topic_prefix=prefix)
        return _device_services[device_id]


def selected_mobile_service(target=None):
    from core.devices import device_registry
    target = target or device_registry.get_active_target()
    device = device_registry.get(target)
    if device and device.get('device_category') == 'mobile':
        return service_for_device(target)
    return mobile_mqtt_service


def stop_registered_services():
    with _services_lock:
        services = list(_device_services.values())
    for service in services:
        service.stop()


atexit.register(stop_registered_services)
