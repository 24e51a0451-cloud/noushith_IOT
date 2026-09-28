from unittest.mock import patch, Mock
import pytest
from actions.desktop import youtube, gmail
from actions.desktop.handler import DesktopHandler
from actions.media.handler import MediaHandler


def test_search_plays_first_result_and_encodes_query():
    with patch.object(youtube, '_tab', return_value={}), patch.object(youtube, '_call') as call, patch.object(youtube, '_evaluate', return_value=True) as evaluate, patch.object(youtube.time, 'sleep'):
        result = youtube.search_youtube('music & chill')
    assert result['playing']
    assert call.call_args_list[0].args[2]['url'].endswith('music%20%26%20chill')
    assert 'link.click()' in evaluate.call_args_list[0].args[1]
    assert 'await video.play()' in evaluate.call_args_list[1].args[1]


def test_search_failure_is_not_reported_as_playing():
    with patch.object(youtube, '_tab', return_value={}), patch.object(youtube, '_call'), patch.object(youtube.time, 'sleep'), patch.object(youtube, '_evaluate', side_effect=RuntimeError('No video result')):
        with pytest.raises(RuntimeError, match='No video result'):
            youtube.search_youtube('missing')


@pytest.mark.parametrize('function,fragment', [(youtube.youtube_volume_up, 'Math.min(1'), (youtube.youtube_volume_down, 'Math.max(0'), (youtube.youtube_mute, 'video.muted = !video.muted')])
def test_audio_targets_video_without_keyboard_focus(function, fragment):
    with patch.object(youtube, '_tab', return_value={}), patch.object(youtube, '_evaluate', return_value=True) as evaluate:
        assert function()['success']
    assert fragment in evaluate.call_args.args[1]


def test_gmail_uses_configured_chrome_profile():
    with patch.object(gmail, 'find_chrome_path', return_value='chrome.exe'), patch.object(gmail.subprocess, 'Popen') as launch, patch.object(gmail.time, 'sleep'):
        assert gmail.open_gmail()['success']
    assert launch.call_args.args[0] == ['chrome.exe', *gmail.CHROME_ARGS, 'https://mail.google.com']


def test_missing_chrome_reports_failure():
    with patch.object(gmail, 'find_chrome_path', return_value=None):
        assert not gmail.open_gmail()['success']


def test_agent_dispatch_supports_gmail_and_mute():
    handler = DesktopHandler()
    with patch.object(gmail, 'compose_gmail', return_value={'success': True}) as compose:
        assert handler.execute('compose_gmail', {'to': 'test@example.com', 'subject': 'Subject', 'body': 'Body'})['success']
    compose.assert_called_once_with(to='test@example.com', subject='Subject', body='Body')
    with patch.object(youtube, 'youtube_mute', return_value={'success': True}):
        assert handler.execute('youtube_mute')['success']
    assert not handler.execute('open_outlook')['success']


def test_jiosaavn_dispatch():
    with patch.object(gmail, 'open_url_robust', return_value=True) as launch:
        result = MediaHandler().execute('open_jiosaavn')
    assert result['success'] and result['domain'] == 'ai_ml'
    launch.assert_called_once_with('https://www.jiosaavn.com/')
