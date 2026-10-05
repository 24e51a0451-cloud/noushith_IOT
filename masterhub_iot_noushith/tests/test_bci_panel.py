import json
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app import create_app
from cortex import dashboard
from cortex.run_live import _process_prediction, _receive_prediction, _raw_message_queue


def setup_function():
    dashboard.reset()


def ready():
    dashboard.update_status(connected=True, authorized=True)
    dashboard.update_profile(current="trained-user")
    dashboard.update_prediction(gesture="neutral", confidence=0.0)


def test_embedded_panel_and_stream():
    client = create_app().test_client()
    page = client.get('/dashboard').get_data(as_text=True)
    assert 'id="bciPanel"' in page and 'id="bciConnect"' in page
    ready()
    response = client.get('/cortex/events', buffered=False)
    payload = json.loads(next(response.response).decode().removeprefix('data: '))
    response.close()
    assert payload['streaming'] is True
    assert payload['predictions'][-1]['action'] == 'neutral'
    assert payload['control_enabled'] is False


def test_monitor_receives_predictions_without_executing():
    pipeline = Mock()
    _process_prediction(SimpleNamespace(command='push', confidence=.9), pipeline)
    pipeline.process.assert_not_called()
    assert dashboard.live_snapshot()['predictions'][-1]['action'] == 'push'


def test_control_requires_live_profile_and_disarms_on_disconnect():
    client = create_app().test_client()
    assert client.post('/cortex/control', json={'enabled': True}).status_code == 409
    assert client.post('/cortex/control', json={'enabled': 'true'}).status_code == 400
    ready()
    assert client.post('/cortex/control', json={'enabled': True}).status_code == 200
    assert dashboard.control_enabled()
    dashboard.update_status(connected=False)
    assert not dashboard.control_enabled()
    assert not dashboard.live_snapshot()['streaming']


def test_stale_stream_disarms_and_does_not_resume_control():
    client = create_app().test_client()
    ready()
    client.post('/cortex/control', json={'enabled': True})
    last = dashboard.live_snapshot()['predictions'][-1]['received_at']
    with patch('cortex.dashboard.time.time', return_value=last + 4):
        dashboard.update_prediction(gesture='push', confidence=.9)
    assert not dashboard.control_enabled()


def test_receive_publishes_even_when_command_worker_is_busy():
    ready()
    client = create_app().test_client()
    client.post('/cortex/control', json={'enabled': True})
    for command in ['push', 'pull', 'left']:
        _receive_prediction({'com': [command, .8], 'time': 1})
    assert dashboard.live_snapshot()['predictions'][-1]['action'] == 'left'
    assert _raw_message_queue.qsize() == 1
    assert _raw_message_queue.get_nowait()['com'][0] == 'left'


def test_control_routes_non_neutral_sample():
    ready()
    create_app().test_client().post('/cortex/control', json={'enabled': True})
    pipeline = Mock()
    pipeline.process.return_value = SimpleNamespace(filter_result=None, stabilizer_result=None, send_result=None)
    _process_prediction(SimpleNamespace(command='push', confidence=.9), pipeline)
    pipeline.process.assert_called_once()
