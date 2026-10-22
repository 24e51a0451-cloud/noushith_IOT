"""Focused tank tests, runnable with unittest without PostgreSQL or hardware."""
import ast
import json
import os
from pathlib import Path
import uuid
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from flask import Blueprint, Flask, jsonify, request
from services import tank_monitor as tank
from services.web_security import reject_cross_origin_mutation, require_operator

ROOT = Path(__file__).resolve().parents[1]


def load_definitions(path, names, namespace):
    # Execute the real handlers without importing unrelated database/hardware singletons.
    tree = ast.parse((ROOT / path).read_text(encoding='utf-8'))
    tree.body = [node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name in names]
    exec(compile(tree, str(path), 'exec'), namespace)


class TankTests(unittest.TestCase):
    def setUp(self):
        temp = ROOT / 'artifacts' / ('tank-test-' + uuid.uuid4().hex)
        temp.mkdir()
        def cleanup():
            for file in temp.iterdir():
                file.unlink()
            temp.rmdir()
        self.addCleanup(cleanup)
        self.addCleanup(patch.stopall)
        patch.object(tank, 'PATH', temp / 'tank.json').start()
        patch.dict(os.environ, {'MASTERHUB_TANK_DEVICE_ID': 'esp32', 'MASTERHUB_TANK_STALE_SECONDS': '30'}).start()

    def reading(self, **overrides):
        packet = dict(distance=84, float=0, rssi=-87, _timestamp=100)
        packet.update(overrides)
        return tank.snapshot({'esp32': packet}, {}, True, now=103)

    def test_height_conversion_persistence_and_calculation(self):
        tank.save_config({'height': 300, 'unit': 'cm'})
        self.assertEqual(tank.read_config()['height_cm'], 300)
        self.assertEqual(self.reading()['percent'], 72)
        self.assertEqual(self.reading()['water_depth_cm'], 216)
        tank.save_config({'height': 10, 'unit': 'ft'})
        self.assertAlmostEqual(tank.read_config()['height_cm'], 304.8)
        self.assertAlmostEqual(self.reading()['percent'], 72.4409448819)
        tank.save_config({'height': round(5000 / 30.48, 10), 'unit': 'ft'})
        self.assertEqual(tank.read_config()['height_cm'], 5000)

    def test_invalid_heights_do_not_replace_saved_setting(self):
        tank.save_config({'height': 300, 'unit': 'cm'})
        for value in [None, True, '', 'nan', 'inf', -1, 0, 4.99, 5001, [], {}]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                tank.save_config({'height': value, 'unit': 'cm'})
        for data in [None, [], {'height': 300, 'unit': 'm'}]:
            with self.assertRaises(ValueError):
                tank.save_config(data)
        self.assertEqual(tank.read_config()['height_cm'], 300)

    def test_missing_invalid_and_boundary_distance(self):
        self.assertIsNone(self.reading()['percent'])
        tank.save_config({'height': 300, 'unit': 'cm'})
        self.assertEqual(self.reading(distance=0)['percent'], 100)
        self.assertEqual(self.reading(distance=300)['percent'], 0)
        for value in [None, True, -1, 301, 'nan', 'inf', [], {}]:
            with self.subTest(value=value):
                reading = self.reading(distance=value)
                self.assertIsNone(reading['percent'])
                self.assertEqual(reading['status'], 'invalid')

    def test_float_is_independent_and_unknown_is_not_normal(self):
        self.assertEqual(self.reading(float='1')['float_value'], 1)
        self.assertTrue(any('overflow' in s for s in self.reading(float=1)['warnings']))
        for value in [None, 2, True, 'bad', {}]:
            self.assertIsNone(self.reading(float=value)['float_value'])

    def test_freshness_retained_and_identity(self):
        tank.save_config({'height': 300, 'unit': 'cm'})
        self.assertEqual(self.reading()['status'], 'live')
        for data in [{'_retained': True}, {'_timestamp': None}, {'_timestamp': 1}, {'_timestamp': 200}]:
            self.assertEqual(self.reading(**data)['status'], 'stale')
        self.assertEqual(tank.snapshot({'other': {'distance': 10}}, {}, True)['status'], 'no_data')
        self.assertEqual(tank.snapshot({'esp32': {'distance': 84, '_timestamp': 100}}, {}, False, 103)['status'], 'stale')

    def test_corrupt_settings_do_not_break_status(self):
        tank.PATH.write_text('{broken')
        self.assertIsNone(self.reading()['config']['height_cm'])
        self.assertTrue(self.reading()['warnings'])

    def test_routes_validation_security_and_no_publish(self):
        broker = Mock(_connected=True, host='test', port=1883)
        bp = Blueprint('tank_test', __name__, url_prefix='/api')
        namespace = dict(api_bp=bp, jsonify=jsonify, request=request, tank_monitor=tank,
                         mqtt_service=broker, get_all_sensor_data=lambda: {'esp32': {'distance': 84}},
                         get_all_device_states=lambda: {}, get_all_online_devices=lambda: {}, LAST_ACKS={})
        load_definitions('api/routes.py', {'get_iot_status', 'set_tank_height'}, namespace)
        app = Flask(__name__)
        app.before_request(reject_cross_origin_mutation)
        app.before_request(require_operator)
        app.register_blueprint(bp)
        client = app.test_client()
        self.assertEqual(client.post('/api/iot/tank-height', json={'height': 0, 'unit': 'cm'}).status_code, 400)
        response = client.post('/api/iot/tank-height', json={'height': 300, 'unit': 'cm'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['tank']['percent'], 72)
        status = client.get('/api/iot/status').json
        self.assertTrue({'sensors', 'states', 'last_acks', 'tank'} <= status.keys())
        self.assertEqual(client.post('/api/iot/tank-height', json={'height': 400, 'unit': 'cm'}, headers={'Origin': 'https://foreign.test'}).status_code, 403)
        self.assertEqual(client.get('/api/iot/status', environ_overrides={'REMOTE_ADDR': '10.0.0.1'}).status_code, 403)
        with patch.object(tank, 'save_config', side_effect=OSError):
            self.assertEqual(client.post('/api/iot/tank-height', json={'height': 300, 'unit': 'cm'}).status_code, 503)
        broker.publish.assert_not_called()
        broker.publish_json.assert_not_called()

    def test_mqtt_sensor_metadata_and_background_start(self):
        sensors = {}
        namespace = dict(json=json, os=os, threading=__import__('threading'), time=Mock(time=lambda:100),
                         uuid=uuid, mqtt=Mock(), read_config=lambda: {'host':'test', 'port':1883},
                         BROKER_HOST='test', BROKER_PORT=1883, DEFAULT_TOPIC='iot/esp32/action', KEEPALIVE=60,
                         log=Mock(), record_mqtt=Mock(), record_event=Mock(), LATEST_SENSORS=sensors,
                         DEVICE_STATES={}, ONLINE_DEVICES={}, LAST_ACKS={})
        load_definitions('services/mqtt_service.py', {'MQTTService'}, namespace)
        service = namespace['MQTTService']()
        service.start()
        service.start()
        service._client.connect_async.assert_called_once_with('test', 1883, 60)
        service._client.loop_start.assert_called_once()
        service._on_message(None, None, SimpleNamespace(topic='iot/device/tank-A/sensor', payload=b'{"distance":84,"float":1}', retain=True))
        self.assertEqual(sensors['tank-A']['_timestamp'], 100)
        self.assertTrue(sensors['tank-A']['_retained'])
        service._on_message(None, None, SimpleNamespace(topic='iot/esp32/sensor', payload=b'{"deviceId":"gateway","distance":84}', retain=False))
        self.assertIs(sensors['esp32'], sensors['gateway'])
        self.assertFalse(sensors['esp32']['_retained'])
        service._on_message(None, None, SimpleNamespace(topic='iot/esp32/status', payload=b'{"deviceId":"gateway","lastSensor":{"distance":12}}', retain=False))
        self.assertEqual(sensors['esp32']['distance'], 84)


if __name__ == '__main__':
    unittest.main()
