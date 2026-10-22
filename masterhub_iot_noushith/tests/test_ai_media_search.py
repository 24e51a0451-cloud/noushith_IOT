from unittest.mock import patch
import pytest
from actions.ai_ml import jiosaavn
from actions.ai_ml.handler import AIMLHandler
from actions.media_jiosaavn_mobile import execute
from services.workflow_service import build_workflow


@patch('services.mobile_mqtt_service.MobileMQTTService.start')
def test_both_media_menus_contain_only_requested_controls(_start):
    domain = next(d for d in build_workflow()['domains'] if d['id'] == 'ai_ml')
    assert [(d['id'], d['gesture']) for d in domain['devices']] == [
        ('mobile_jiosaavn', 'push'), ('desktop_jiosaavn', 'pull')]
    for device in domain['devices']:
        assert len(device['commands']) == 6
        commands = {c['gesture']: c for c in device['commands']}
        assert set(commands) == {'push', 'pull', 'left', 'right', 'right+push', 'right+pull'}
        assert commands['right']['parameters'] == ['query']
        assert commands['left']['label'] == 'Play / Pause'


def test_desktop_search_waits_for_playback_confirmation():
    with patch.object(jiosaavn, '_tab', return_value={}), patch.object(jiosaavn, '_call', return_value={}) as call, patch.object(jiosaavn, '_evaluate', return_value=True) as evaluate, patch.object(jiosaavn.time, 'sleep'):
        result = AIMLHandler().execute('search_jiosaavn', {'query': 'Song & Artist', 'target': 'local'})
        assert result['playing'] is True
        assert call.call_args_list[0].args[2]['url'].endswith('Song%20%26%20Artist')
        assert evaluate.call_count == 3


def test_failed_playback_is_not_reported_as_success():
    with patch.object(jiosaavn, '_tab', return_value={}), patch.object(jiosaavn, '_call', return_value={}), patch.object(jiosaavn, '_evaluate', side_effect=[True, True, False]), patch.object(jiosaavn.time, 'sleep'):
        with pytest.raises(RuntimeError, match='not confirmed'):
            jiosaavn.search_and_play('Song')


def test_search_from_bci_with_submitted_query_reaches_phone():
    with patch('actions.media_jiosaavn_mobile.mobile_mqtt_service') as service:
        execute('mobile_jiosaavn_search', {'query': ' Song ', 'source': 'cortex'})
        service.publish_command.assert_called_once_with('SEARCH', 1.0, 'Song', origin='bci_prediction')


@pytest.mark.parametrize('query', ['', '   ', None, 'x' * 501])
def test_invalid_query_never_opens_browser(query):
    with patch.object(jiosaavn, '_tab') as tab:
        with pytest.raises(ValueError):
            jiosaavn.search_and_play(query)
        tab.assert_not_called()
