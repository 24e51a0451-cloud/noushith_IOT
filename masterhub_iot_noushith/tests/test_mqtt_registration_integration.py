"""Local-broker integration; never connects to the configured external broker."""
import json
from pathlib import Path
import queue
import shutil
import socket
import subprocess
import threading
import time
from unittest.mock import patch
import uuid

import paho.mqtt.client as mqtt
import pytest
from core.devices import DeviceRegistry
from services.mobile_registration import MobileRegistrationService, register_device
from services.mobile_mqtt_service import MobileMQTTService


def test_registration_rename_and_targeted_delivery_over_local_broker(tmp_path):
    executable = shutil.which('mosquitto') or r'C:\Program Files\Mosquitto\mosquitto.exe'
    if not Path(executable).exists():
        pytest.skip('Local Mosquitto is not installed')
    with socket.socket() as bound:
        bound.bind(('127.0.0.1', 0))
        port = bound.getsockname()[1]
    config = tmp_path / 'mosquitto.conf'
    config.write_text(f'listener {port} 127.0.0.1\nallow_anonymous true\npersistence false\n')
    process = subprocess.Popen([executable, '-c', str(config)], stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    clients = []
    try:
        for _ in range(50):
            try:
                with socket.create_connection(('127.0.0.1', port), timeout=.1):
                    break
            except OSError:
                time.sleep(.1)
        server = mqtt.Client(client_id='test-discovery')
        phone = mqtt.Client(client_id='test-phone')
        clients.extend([server, phone])
        registered = threading.Event()
        subscribed = threading.Event()
        inbox = queue.Queue()
        discovery = MobileRegistrationService()
        server.on_connect = lambda c, u, f, rc: c.subscribe('bci/devices/register', 1)
        server.on_subscribe = lambda *args: registered.set()
        server.on_message = discovery.on_message
        phone.on_subscribe = lambda *args: subscribed.set()
        phone.on_message = lambda c, u, message: inbox.put((message.topic, json.loads(message.payload)))
        server.connect('127.0.0.1', port); server.loop_start()
        phone.connect('127.0.0.1', port); phone.loop_start()
        device_id = str(uuid.uuid4())
        prefix = 'bci/' + device_id
        phone.subscribe([(prefix + '/registration', 1), (prefix + '/commands', 1)])
        assert registered.wait(5) and subscribed.wait(5)
        database_path = tmp_path / 'hub.db'
        registry = DeviceRegistry(database_path=database_path)
        with patch('services.mobile_registration.register_device', side_effect=lambda payload: register_device(payload, database_path, registry)), \
             patch('services.mobile_mqtt_service.service_for_device'):
            for username in ('sathwik', 'sathwik1'):
                phone.publish('bci/devices/register', json.dumps(dict(device_id=device_id, username=username,
                              device_type='Android', request_id=username)), qos=1)
                topic, reply = inbox.get(timeout=5)
                assert topic == prefix + '/registration'
                assert reply['status'] == 'REGISTERED'
                assert reply['username'] == username and reply['device_id'] == device_id
                assert reply['request_id'] == username
        sender = MobileMQTTService(client=server, device_id=device_id, topic_prefix=prefix)
        sender.started = sender.connected = True
        sender.last_seen = time.time()
        sender.phone = dict(control_enabled=True)
        assert sender.publish_command('Right_Next_Song', 1)['success']
        topic, command = inbox.get(timeout=5)
        assert topic == prefix + '/commands' and command['target_device'] == device_id
        assert registry.get(device_id)['name'] == 'sathwik1'
    finally:
        for client in clients:
            client.disconnect(); client.loop_stop()
        process.terminate()
        process.wait(timeout=5)
