"""Mental-command startup must work without licensed activation quota."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from cortex import session as session_module
from cortex.cortex_client import CortexRequestError
from cortex.run_live import LiveRunner, _receive_prediction
from cortex.session import SessionManager


@pytest.mark.parametrize('configured_status', ['active', 'open'])
def test_live_startup_and_reconnect_do_not_activate(monkeypatch, configured_status):
    monkeypatch.setattr(session_module, 'SESSION_STATUS', configured_status)
    runner = LiveRunner.__new__(LiveRunner)
    runner.auth = Mock()
    runner.auth.login_and_authorize.return_value = 'test-token'
    runner.headset_info = None
    runner.headsets = Mock()
    runner.headsets.ensure_connected.return_value = SimpleNamespace(
        id='test-headset', status='connected', firmware='test',
    )
    runner.headsets.read_device_diagnostics.return_value = SimpleNamespace(
        battery_percent=90, signal_quality=4,
    )
    client = Mock()

    def call(method, params):
        if method == 'createSession':
            if params['status'] == 'active':
                raise CortexRequestError(-32019, 'Session limit reached')
            return {'id': 'test-session', 'status': 'open'}
        pytest.fail(f'Unexpected Cortex call: {method}')

    client.call.side_effect = call
    runner.sessions = SessionManager(client)
    runner.streams = Mock()
    runner._refresh_profile = Mock()
    monkeypatch.setattr('cortex.run_live.bci_logger.log_headset_connected', Mock())

    # The same preparation flow is used on startup and after reconnecting.
    for _ in range(2):
        runner._authenticate_and_prepare()
        assert runner.sessions.current.status == 'open'
        runner.streams.subscribe_mental_commands.assert_called_with(
            'test-token', 'test-session', on_prediction_raw=_receive_prediction,
        )
    assert client.call.call_count == 2
    runner.auth.authorize.assert_not_called()
