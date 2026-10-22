"""Offline transport/contract tests; never connect to the public broker."""
import json
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from services.mobile_mqtt_service import MobileMQTTService
from actions.media_jiosaavn_mobile import execute, COMMANDS


class MobileTests(unittest.TestCase):
    def test_mobile_namespace_is_separate_from_desktop(self):
        with patch.dict('os.environ', {}, clear=True):
            service = MobileMQTTService(Mock())
        self.assertEqual((service.host, service.port), ('52.21.249.6', 1883))
        self.assertEqual(service.topics['commands'], 'masterhub/mobile/MOBILE_001/command')
        for channel in ('ack', 'status', 'heartbeat'):
            self.assertEqual(service.topics[channel], 'masterhub/mobile/MOBILE_001/' + channel)
        self.assertTrue(all(not topic.startswith('masterhub/devices/') for topic in service.topics.values()))

    def test_desktop_topic_is_still_pc_scoped(self):
        from services.mqtt_service import mqtt_service
        with patch.object(mqtt_service, 'publish_json', return_value=True) as publish:
            mqtt_service.send_pc_agent_command('PC_001', 'ai_ml', 'next_track')
        self.assertEqual(publish.call_args.kwargs['topic'], 'masterhub/devices/PC_001/command')
        self.assertEqual(publish.call_args.args[0]['action'], 'next_track')

    def setUp(self):
        discovery = patch('services.mobile_registration.mobile_registration.start')
        discovery.start()
        self.addCleanup(discovery.stop)
        self.client = Mock()
        self.client.publish.return_value.rc = 0
        self.service = MobileMQTTService(self.client)
        self.service.connected = True
        self.service.last_seen = time.time()
        self.service.phone = {'control_enabled': True}

    def message(self, name, data, retained=False):
        self.service._on_message(None, None, SimpleNamespace(topic=self.service.topics[name], payload=json.dumps(dict(data, device_id=self.service.topic_device_id)).encode(), retain=retained))

    def test_contract_and_correlated_ack(self):
        result = self.service.publish_command('Right_Next_Song', 0.82)
        payload = json.loads(self.client.publish.call_args.args[1])
        self.assertEqual(payload['confidence'], 0.82)
        self.assertEqual(set(payload), {'command_id', 'command', 'target_device', 'origin', 'confidence', 'query', 'expires_at', 'timestamp'})
        self.assertEqual(self.client.publish.call_args.kwargs, {'qos': 1, 'retain': False})
        self.message('ack', {'command_id': 'wrong', 'status': 'SUCCESS'})
        self.assertEqual(self.service.snapshot()['commands'][0]['status'], 'PENDING')
        self.message('ack', {'command_id': result['command_id'], 'status': 'SUCCESS'})
        self.assertEqual(self.service.snapshot()['commands'][0]['status'], 'SUCCESS')
        self.message('ack', {'command_id': result['command_id'], 'status': 'FAILED'})
        self.assertEqual(self.service.snapshot()['commands'][0]['status'], 'SUCCESS')

    def test_offline_and_retained_heartbeat(self):
        self.service.last_seen = 0
        self.message('heartbeat', {'status': 'alive'}, retained=True)
        self.assertFalse(self.service.snapshot()['online'])
        self.assertFalse(self.service.publish_command('NEXT', 1)['success'])
        self.client.publish.assert_not_called()

    def test_mobile_heartbeat_overrides_stale_generic_target_status(self):
        target = {'device_id': 'MOBILE_001', 'status': 'OFFLINE', 'transport': 'mqtt'}
        merged = self.service.merge_target_presence([target])
        self.assertEqual(merged[0]['status'], 'ONLINE')
        self.assertEqual(merged[0]['connection_source'], 'mobile_heartbeat')
        self.assertEqual(merged[0]['platform'], 'android')

        self.service.last_seen = 0
        merged = self.service.merge_target_presence([dict(target, status='ONLINE')])
        self.assertEqual(merged[0]['status'], 'OFFLINE')

    def test_mobile_presence_does_not_change_pc_targets(self):
        target = {'device_id': 'PC_001', 'status': 'OFFLINE', 'transport': 'mqtt'}
        self.assertEqual(self.service.merge_target_presence([target]), [target])

    def test_timeout_and_late_ack(self):
        result = self.service.publish_command('NEXT', 1)
        self.service.commands[result['command_id']]['deadline'] = 0
        self.assertEqual(self.service.snapshot()['commands'][0]['status'], 'TIMEOUT')
        self.message('ack', {'command_id': result['command_id'], 'status': 'SUCCESS'})
        self.assertEqual(self.service.snapshot()['commands'][0]['status'], 'SUCCESS')

    def test_search_has_time_for_app_launch_and_playback_ack(self):
        self.service.timeout = 8
        result = self.service.publish_command('SEARCH', 1, 'Song')
        payload = json.loads(self.client.publish.call_args.args[1])
        self.assertEqual(payload['expires_at'] - payload['timestamp'], 45000)
        self.assertAlmostEqual(self.service.commands[result['command_id']]['deadline'],
                               payload['expires_at'] / 1000, places=2)
        self.service.publish_command('NEXT', 1)
        payload = json.loads(self.client.publish.call_args.args[1])
        self.assertEqual(payload['expires_at'] - payload['timestamp'], 8000)

    def test_handlers_validate_and_preserve_parameters(self):
        with patch('actions.media_jiosaavn_mobile.mobile_mqtt_service') as service:
            execute('mobile_jiosaavn_search', {'query': 'A R Rahman', 'confidence': .73})
            service.publish_command.assert_called_once_with('SEARCH', .73, 'A R Rahman', origin='dashboard')
            service.reset_mock()
            for params in ({'query': ''}, {'query': 'music', 'confidence': float('nan')}, {'query': 'music', 'Is_Actionable': False}):
                self.assertFalse(execute('mobile_jiosaavn_search', params)['success'])
            service.publish_command.assert_not_called()

    def test_mobile_dispatch_bypasses_pc_target(self):
        from actions.ai_ml.handler import ai_ml_handler
        with patch('actions.media_jiosaavn_mobile.mobile_mqtt_service') as service:
            service.publish_command.return_value = {'success': True, 'status': 'PENDING'}
            result = ai_ml_handler.execute('mobile_jiosaavn_next', {'target': 'PC_OTHER'})
            self.assertTrue(result['success'])
            service.publish_command.assert_called_once_with('Right_Next_Song', 1.0, '', origin='dashboard')

    def test_mappings_match_all_input_paths(self):
        root = Path(__file__).resolve().parents[1] / 'mappings'
        load = lambda name: json.loads((root / name).read_text(encoding='utf-8'))
        routes = load('command_map.json')
        gestures = load('gesture_map.json')
        bci = load('bci_master_map.json')['phase_2_and_3_workflows']['ai_ml']['mobile_jiosaavn']['commands']
        for command in COMMANDS:
            self.assertEqual(routes[command], {'domain': 'ai_ml', 'action': command})
        for command, item in bci.items():
            self.assertEqual(gestures[item['gesture']]['MOBILE_JIOSAAVN_MODE'], command)
        self.assertEqual(bci['mobile_jiosaavn_search']['gesture'], 'right')
        self.assertNotIn('mobile_jiosaavn_launch', bci)
        self.assertEqual(gestures['push+right']['MOBILE_JIOSAAVN_MODE'], 'mode_media')
        self.assertEqual(gestures['push+left']['MOBILE_JIOSAAVN_MODE'], 'mode_idle')

    def test_http_preserves_top_level_query_and_confidence(self):
        from app import create_app
        with patch('actions.media_jiosaavn_mobile.mobile_mqtt_service') as service:
            service.publish_command.return_value = {'success': True, 'status': 'PENDING', 'command_id': 'http-test'}
            response = create_app().test_client().post('/api/command', json={
                'command': 'mobile_jiosaavn_search', 'query': 'music', 'confidence': .9})
            self.assertEqual(response.status_code, 200)
            service.publish_command.assert_called_once_with('SEARCH', .9, 'music', origin='dashboard')

    def test_status_endpoint_uses_mobile_cache(self):
        from app import create_app
        with patch('api.jiosaavn.mobile_mqtt_service') as service:
            service.snapshot.return_value = {'online': True, 'media': {'title': 'Test'}}
            client = create_app().test_client()
            self.assertEqual(client.get('/api/jiosaavn/media').get_json()['media']['title'], 'Test')
            self.assertTrue(client.get('/api/jiosaavn/status').get_json()['online'])

    def test_dashboard_has_phone_panel(self):
        from app import create_app
        response = create_app().test_client().get('/dashboard')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data.count(b'id="mobileJiosaavnStatus"'), 1)
        self.assertIn(b'/static/jiosaavn-mobile.js', response.data)


if __name__ == '__main__':
    unittest.main()
