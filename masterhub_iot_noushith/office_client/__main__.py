"""Run one Office client with MQTT, UART, or both; no startup automation."""
import argparse
import json
import logging
import os
from pathlib import Path
from queue import Queue, Full, Empty
import threading
import time

from office_client.office import OfficeWorker, OFFICE_ACTIONS
from office_client.protocol import CommandReceiver, MAX_FRAME

log = logging.getLogger('office-client')


def main():
    parser = argparse.ArgumentParser(description='Masterhub Office client (MQTT / direct UART)')
    parser.add_argument('--config', required=True, help='Client JSON configuration path')
    args = parser.parse_args()
    config = json.loads(Path(args.config).read_text(encoding='utf-8'))
    device_id = config['device_id']
    mqtt_config = config.get('mqtt', {})
    serial_config = config.get('uart', {})
    if not mqtt_config.get('host') and not serial_config.get('port'):
        parser.error('Configure mqtt.host and/or uart.port')
    data_dir = Path(os.environ.get('LOCALAPPDATA', Path.home())) / 'MasterhubOffice' / device_id
    # Validate the ID before using it in filesystem paths or MQTT topics.
    import re
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', device_id):
        parser.error('Invalid device_id')
    data_dir.mkdir(parents=True, exist_ok=True)
    from logging.handlers import RotatingFileHandler
    logging.basicConfig(level=logging.INFO, handlers=[logging.StreamHandler(), RotatingFileHandler(
        data_dir / 'client.log', maxBytes=1_000_000, backupCount=3, encoding='utf-8')])
    # One process per identity prevents two receivers owning the same document session.
    import msvcrt
    instance = (data_dir / 'instance.lock').open('a+b')
    instance.seek(0)
    if not instance.read(1):
        instance.write(b'0')
        instance.flush()
    instance.seek(0)
    try:
        msvcrt.locking(instance.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError:
        parser.error('An Office client with this device_id is already running')
    worker = OfficeWorker(config.get('output_dir'))
    receiver = CommandReceiver(device_id, worker.execute, data_dir / 'commands.sqlite3')
    incoming = Queue(maxsize=32)
    stop = threading.Event()
    client = None
    serial_thread = None
    heartbeat_thread = None
    prefix = f'masterhub/devices/{device_id}'

    def status(online=True):
        return {'protocol': 'masterhub', 'version': '1.0', 'message_type': 'status',
                'source': device_id, 'device_id': device_id, 'status': 'ONLINE' if online else 'OFFLINE',
                'timestamp': time.time(), 'params': {'capabilities': sorted(OFFICE_ACTIONS)}}

    def submit(raw, reply, retained=False):
        if len(raw) > MAX_FRAME:
            log.warning('Oversized command rejected')
            return
        try:
            incoming.put_nowait((raw, reply, retained))
        except Full:
            # No execution occurred. Dropping is safer than replaying commands after a backlog.
            log.warning('Command queue full; command not accepted')

    def mqtt_heartbeat():
        while not stop.wait(20):
            if client.is_connected():
                client.publish(prefix + '/status', json.dumps(status()), qos=1, retain=True)

    def serial_loop():
        import serial
        while not stop.is_set():
            try:
                with serial.Serial(serial_config['port'], int(serial_config.get('baudrate', 115200)),
                                   timeout=0.2, write_timeout=2) as port:
                    write_lock = threading.Lock()

                    def reply(value, connection=port, lock=write_lock):
                        with lock:
                            connection.write((json.dumps(value) + '\n').encode('utf-8'))

                    reply(status())
                    buffer = bytearray()
                    discard = False
                    heartbeat = time.monotonic()
                    log.info('UART connected on %s', serial_config['port'])
                    while not stop.is_set():
                        for value in port.read(min(port.in_waiting or 1, 4096)):
                            if value == 10:
                                if buffer and not discard:
                                    submit(bytes(buffer), reply)
                                buffer.clear()
                                discard = False
                            elif not discard:
                                buffer.append(value)
                                if len(buffer) > MAX_FRAME:
                                    buffer.clear()
                                    discard = True
                        if time.monotonic() - heartbeat >= 20:
                            reply(status())
                            heartbeat = time.monotonic()
            except Exception as error:
                log.warning('UART unavailable: %s', error)
                stop.wait(2)

    try:
        if mqtt_config.get('host'):
            import paho.mqtt.client as mqtt
            client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f'masterhub-office-{device_id}')
            username = os.environ.get('MASTERHUB_MQTT_USERNAME') or mqtt_config.get('username')
            password = os.environ.get('MASTERHUB_MQTT_PASSWORD')
            if username:
                client.username_pw_set(username, password)
            if mqtt_config.get('tls'):
                client.tls_set(ca_certs=mqtt_config.get('ca_file'))
            client.will_set(prefix + '/status', json.dumps(status(False)), qos=1, retain=True)
            client.reconnect_delay_set(min_delay=1, max_delay=30)

            def publish_result(value):
                channel = '/ack' if value.get('success') else '/error'
                client.publish(prefix + channel, json.dumps(value), qos=1, retain=False)

            def connected(connection, userdata, flags, reason, properties):
                if reason == 0:
                    connection.subscribe(prefix + '/command', qos=1)
                    connection.publish(prefix + '/status', json.dumps(status()), qos=1, retain=True)
                    log.info('MQTT connected')
                else:
                    log.error('MQTT connection rejected: %s', reason)

            client.on_connect = connected
            client.on_message = lambda connection, userdata, message: submit(message.payload, publish_result, message.retain)
            client.connect_async(mqtt_config['host'], int(mqtt_config.get('port', 8883 if mqtt_config.get('tls') else 1883)), 30)
            client.loop_start()
            heartbeat_thread = threading.Thread(target=mqtt_heartbeat, daemon=True)
            heartbeat_thread.start()
        if serial_config.get('port'):
            serial_thread = threading.Thread(target=serial_loop, daemon=True)
            serial_thread.start()
        log.info('Ready: %s. No applications opened; waiting for Office commands.', device_id)
        while not stop.is_set():
            try:
                raw, reply, retained = incoming.get(timeout=0.5)
            except Empty:
                continue
            try:
                result = receiver.handle(raw, retained)
                reply(result)
                log.info('Command %s: %s', result.get('command_id'), result.get('status'))
            except Exception:
                log.exception('Command processing or response delivery failed; no automatic retry')
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        if heartbeat_thread:
            heartbeat_thread.join(timeout=2)
        if client:
            client.publish(prefix + '/status', json.dumps(status(False)), qos=1, retain=True)
            client.disconnect()
            client.loop_stop()
        if serial_thread:
            serial_thread.join(timeout=3)
        receiver.close()
        worker.stop()
        instance.close()


if __name__ == '__main__':
    main()
