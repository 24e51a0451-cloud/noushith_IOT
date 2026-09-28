import threading
from unittest.mock import Mock

import pytest

from cortex import config, dashboard
from cortex.auth import CortexAuth
from cortex.cortex_client import CortexClient
from cortex.run_live import LiveRunner


def api_client():
    from flask import Flask
    app = Flask(__name__)
    app.register_blueprint(dashboard.cortex_bp)
    return app.test_client()


def test_credentials_round_trip_and_new_connection(isolated_cortex_settings):
    secret = "quote' slash\\ stars*** dollar${HOME} # and equals="
    result = api_client().post('/cortex/credentials', json={
        'client_id': 'new-client', 'client_secret': secret,
        'cortex_url': 'wss://127.0.0.1:6868',
    })
    assert result.status_code == 200
    assert config.reload_credentials()[:2] == ('new-client', secret)
    assert CortexAuth(Mock()).credentials.client_secret == secret
    assert CortexClient().url == 'wss://127.0.0.1:6868'
    assert secret not in api_client().get('/cortex/credentials').text


def test_failed_write_preserves_original(isolated_cortex_settings, monkeypatch):
    before = isolated_cortex_settings.read_bytes()
    monkeypatch.setattr(dashboard.os, 'replace', Mock(side_effect=OSError('disk unavailable')))
    result = api_client().post('/cortex/credentials', json={'client_secret': 'replacement'})
    assert result.status_code == 500
    assert isolated_cortex_settings.read_bytes() == before
    assert config.reload_credentials()[1] == 'test-secret'


def test_partial_save_failure_cannot_mix_credentials(isolated_cortex_settings, monkeypatch):
    import dotenv
    original = dotenv.set_key
    before = isolated_cortex_settings.read_bytes()

    def fail_second_key(path, key, value, **kwargs):
        if key == 'CORTEX_CLIENT_SECRET':
            raise OSError('write failed')
        return original(path, key, value, **kwargs)

    monkeypatch.setattr(dotenv, 'set_key', fail_second_key)
    response = api_client().post('/cortex/credentials', json={
        'client_id': 'replacement-id', 'client_secret': 'replacement-secret',
    })
    assert response.status_code == 500
    assert isolated_cortex_settings.read_bytes() == before


def test_concurrent_saves_preserve_unrelated_settings(isolated_cortex_settings):
    from concurrent.futures import ThreadPoolExecutor
    with isolated_cortex_settings.open('a', encoding='utf-8') as output:
        output.write("MQTT_HOST='unchanged'\n")
    with ThreadPoolExecutor(max_workers=2) as workers:
        results = list(workers.map(dashboard._update_env_file, [
            {'CORTEX_CLIENT_ID': 'replacement'}, {'CORTEX_URL': 'wss://127.0.0.1:6868'},
        ]))
    assert len(results) == 2
    assert config.reload_credentials()[0] == 'replacement'
    assert config.reload_credentials()[3] == 'wss://127.0.0.1:6868'
    assert "MQTT_HOST='unchanged'" in isolated_cortex_settings.read_text()


@pytest.mark.parametrize('payload', [
    {'client_id': 12}, {'client_secret': 'one\nOTHER=two'},
    {'cortex_url': 'https://localhost'}, {'cortex_url': 'wss://localhost:bad'},
    ['invalid'],
])
def test_invalid_settings_do_not_change_file(payload, isolated_cortex_settings):
    before = isolated_cortex_settings.read_bytes()
    assert api_client().post('/cortex/credentials', json=payload).status_code == 400
    assert isolated_cortex_settings.read_bytes() == before


def test_blank_and_masked_secret_preserved():
    for secret in ('', api_client().get('/cortex/credentials').get_json()['client_secret']):
        assert api_client().post('/cortex/credentials', json={'client_secret': secret}).status_code == 200
        assert config.reload_credentials()[1] == 'test-secret'


def test_retired_socket_cannot_clear_new_connection():
    client = CortexClient(auto_reconnect=False)
    current, retired = Mock(), Mock()
    client._ws = current
    client._on_open(current)
    client._on_close(retired, 1000, '')
    assert client.connected
    client._on_close(current, 1000, '')
    assert not client.connected
    client._on_open(retired)
    assert not client.connected


def test_runner_owns_reconnect_and_handles_cancel_warning():
    runner = LiveRunner()
    assert runner.client.auto_reconnect is False
    runner._on_warning({'warning': {'code': 0}})
    assert runner._reconnect_requested.is_set()


def test_disconnect_rebuilds_once_and_stops(monkeypatch):
    runner = LiveRunner()
    runner.client = Mock(connected=False)
    runner.pipeline = Mock()
    runner._authenticate_and_prepare = Mock(side_effect=runner.stop_event.set)
    runner.run_forever(runner.stop_event)
    runner.client.connect.assert_called_once()
    runner._authenticate_and_prepare.assert_called_once()
    assert runner.client.close.call_count >= 2
    runner.pipeline.stop_motion.assert_called_once()


def test_save_schedules_reconnect(monkeypatch):
    from cortex import service
    runner = Mock()
    monkeypatch.setattr(service, '_runner', runner)
    assert api_client().post('/cortex/credentials', json={'client_id': 'updated'}).status_code == 200
    runner.request_reconnect.assert_called_once()


def test_headset_lookup_uses_documented_id():
    from cortex.headset import HeadsetManager
    client = Mock()
    client.call.return_value = []
    HeadsetManager(client).get_info('INSIGHT-test')
    client.call.assert_called_once_with('queryHeadsets', {'id': 'INSIGHT-test'})
