"""Independent MQTT transport for the Android companion. No hardware broker state."""
import atexit
import copy
import json
import os
import threading
import time
import uuid
from collections import OrderedDict

import paho.mqtt.client as mqtt
from dotenv import load_dotenv

load_dotenv()


class MobileMQTTService:
    def __init__(self, client=None):
        self.host = os.getenv('BCI_MOBILE_MQTT_HOST', '52.21.249.6')
        self.port = int(os.getenv('BCI_MOBILE_MQTT_PORT', '1883'))
        prefix = os.getenv('BCI_MOBILE_TOPIC_PREFIX', 'masterhub/mobile/MOBILE_001').rstrip('/')
        self.device_id = prefix.rsplit('/', 1)[-1] or 'MOBILE_001'
        self.topics = {name: os.getenv('BCI_MOBILE_' + name.upper() + '_TOPIC', prefix + '/' + ('command' if name == 'commands' else name))
                       for name in ('commands', 'ack', 'error', 'media', 'status', 'heartbeat', 'control')}
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
            self.client.tls_set()
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
        with self.lock:
            self.connected = rc == 0
        if rc == 0:
            for name in ('ack', 'error', 'media', 'status', 'heartbeat'):
                client.subscribe(self.topics[name], qos=1)

    def _on_disconnect(self, client, userdata, rc):
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
        with self.lock:
            if message.topic == self.topics['ack']:
                item = self.commands.get(data.get('command_id'))
                if item and item['status'] in ('PENDING', 'TIMEOUT') and data.get('status') in ('EXECUTED', 'FAILED', 'UNCONFIRMED', 'REJECTED'):
                    item.update(status=data['status'], ack=data)
            elif message.topic == self.topics['error']:
                self.last_error = dict(data, received_at=time.time())
            elif message.topic == self.topics['media']:
                self.media = dict(data, received_at=time.time())
            elif message.topic in (self.topics['status'], self.topics['heartbeat']):
                self.phone = data
                # Retained online announcements cannot establish fresh liveness.
                if data.get('online') is False:
                    self.last_seen = 0
                elif not message.retain:
                    self.last_seen = time.time()

    def snapshot(self):
        with self.lock:
            now = time.time()
            for item in self.commands.values():
                if item['status'] == 'PENDING' and now > item['deadline']:
                    item['status'] = 'TIMEOUT'
            return copy.deepcopy({
                'broker_connected': self.connected,
                'online': bool(self.connected and self.last_seen and now - self.last_seen < self.heartbeat_timeout),
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
            if target.get('device_id') == self.device_id:
                target['status'] = 'ONLINE' if snapshot['online'] else 'OFFLINE'
                target['last_seen'] = snapshot['last_seen']
                target['transport'] = 'mqtt'
                target['platform'] = 'android'
                target['connection_source'] = 'mobile_heartbeat'
            merged.append(target)
        return merged

    def publish_command(self, command, confidence, query=''):
        self.start()
        with self.lock:
            if not self.snapshot()['online']:
                return {'success': False, 'error': 'Phone offline or heartbeat unavailable'}
            if self.phone.get('control_enabled') is not True:
                return {'success': False, 'error': 'Enable remote control on the phone'}
            now = time.time()
            identifier = str(uuid.uuid4())
            payload = dict(command=command, confidence=confidence, Is_Actionable=True, query=query,
                           command_id=identifier, issued_at=int(now * 1000), expires_at=int((now + self.timeout) * 1000))
            item = dict(command_id=identifier, command=command, status='PENDING', deadline=now + self.timeout)
            self.commands[identifier] = item
            while len(self.commands) > 200:
                self.commands.popitem(last=False)
            info = self.client.publish(self.topics['commands'], json.dumps(payload), qos=1, retain=False)
            if info.rc != mqtt.MQTT_ERR_SUCCESS:
                item['status'] = 'FAILED'
                return {'success': False, 'error': 'MQTT publish failed', 'command_id': identifier}
            return {'success': True, 'status': 'PENDING', 'command_id': identifier,
                    'detail': 'Sent to phone; awaiting execution acknowledgement'}


mobile_mqtt_service = MobileMQTTService()
atexit.register(mobile_mqtt_service.stop)
