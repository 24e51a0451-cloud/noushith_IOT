"""YouTube commands use a dedicated Chrome profile and its loopback DevTools endpoint."""
import json
import subprocess
import threading
import time
from pathlib import Path
from urllib.parse import quote

import requests
import websocket
from actions.desktop.gmail import find_chrome_path

_PROFILE = Path(__file__).resolve().parents[2] / '.runtime' / 'youtube-chrome'
_LOCK = threading.RLock()


def _endpoint(start=False):
    port_file = _PROFILE / 'DevToolsActivePort'
    def read():
        port = int(port_file.read_text().splitlines()[0])
        base = f'http://127.0.0.1:{port}'
        requests.get(base + '/json/version', timeout=1).raise_for_status()
        return base
    try:
        return read()
    except (OSError, ValueError, IndexError, requests.RequestException):
        if not start:
            raise RuntimeError('Open or search YouTube from MasterHub first.')
    chrome = find_chrome_path()
    if not chrome:
        raise RuntimeError('Google Chrome was not found on this PC.')
    _PROFILE.mkdir(parents=True, exist_ok=True)
    subprocess.Popen([chrome, f'--user-data-dir={_PROFILE}', '--remote-debugging-port=0',
                      '--remote-debugging-address=127.0.0.1', '--no-first-run', 'about:blank'])
    for _ in range(40):
        try:
            return read()
        except (OSError, ValueError, IndexError, requests.RequestException):
            time.sleep(.2)
    raise RuntimeError('Chrome did not start its media control connection.')


def _tab(create=False):
    base = _endpoint(start=create)
    tabs = requests.get(base + '/json/list', timeout=2).json()
    for tab in tabs:
        if tab.get('type') == 'page' and tab.get('url', '').startswith('https://www.youtube.com/'):
            return tab
    if create:
        response = requests.put(base + '/json/new?' + quote('https://www.youtube.com/', safe=''), timeout=3)
        response.raise_for_status()
        return response.json()
    raise RuntimeError('No YouTube tab is open in the MasterHub Chrome window.')


def _call(tab, method, params):
    ws = websocket.create_connection(tab['webSocketDebuggerUrl'], timeout=25, suppress_origin=True)
    try:
        ws.send(json.dumps({'id': 1, 'method': method, 'params': params}))
        while True:
            message = json.loads(ws.recv())
            if message.get('id') != 1:
                continue
            if 'error' in message:
                raise RuntimeError(message['error']['message'])
            return message.get('result', {})
    finally:
        ws.close()


def _evaluate(tab, body):
    result = _call(tab, 'Runtime.evaluate', {'expression': '(async () => {' + body + '})()',
                   'awaitPromise': True, 'returnByValue': True, 'userGesture': True})
    if result.get('exceptionDetails'):
        detail = result['exceptionDetails']
        raise RuntimeError(detail.get('exception', {}).get('description', detail.get('text', 'YouTube control failed')))
    return result.get('result', {}).get('value')


def open_youtube(wait=3.5, query=None):
    if query:
        return search_youtube(query, wait)
    with _LOCK:
        tab = _tab(create=True)
        _call(tab, 'Page.bringToFront', {})
    return {'success': True, 'action': 'open_youtube'}


def search_youtube(query, wait=4.0):
    if not query or not query.strip():
        raise ValueError('Enter a YouTube search query.')
    with _LOCK:
        tab = _tab(create=True)
        _call(tab, 'Page.navigate', {'url': 'https://www.youtube.com/results?search_query=' + quote(query)})
        _call(tab, 'Page.bringToFront', {})
        # Wait for navigation before evaluating in the new document.
        time.sleep(1)
        _evaluate(tab, '''
            const end = Date.now() + 15000;
            while (Date.now() < end) {
                const link = document.querySelector('ytd-video-renderer a#video-title[href*="/watch?"]');
                if (link) { link.click(); return true; }
                await new Promise(r => setTimeout(r, 250));
            }
            throw new Error('No video result found. Check YouTube consent, connection, or search query.');
        ''')
        time.sleep(1)
        _evaluate(tab, '''
            const end = Date.now() + 15000;
            while (Date.now() < end) {
                const video = document.querySelector('video');
                if (video && location.pathname === '/watch' && video.readyState >= 2) {
                    await video.play(); return true;
                }
                await new Promise(r => setTimeout(r, 250));
            }
            throw new Error('The selected video did not become ready to play.');
        ''')
    return {'success': True, 'action': 'search_youtube', 'query': query, 'playing': True}


def play_youtube(query, wait=3.0):
    result = search_youtube(query, wait)
    result['action'] = 'play_youtube'
    return result


def _control(action, script):
    with _LOCK:
        value = _evaluate(_tab(), "const video = document.querySelector('video'); if (!video) throw new Error('No video is loaded.'); " + script)
    return {'success': True, 'action': action, 'value': value}


def youtube_volume_up(step=5):
    amount = max(0, min(100, int(step))) / 100
    return _control('youtube_volume_up', f'video.volume = Math.min(1, video.volume + {amount}); video.muted = false; return video.volume;')


def youtube_volume_down(step=5):
    amount = max(0, min(100, int(step))) / 100
    return _control('youtube_volume_down', f'video.volume = Math.max(0, video.volume - {amount}); return video.volume;')


def youtube_mute(wait=.2):
    return _control('youtube_mute', 'video.muted = !video.muted; return video.muted;')


def pause_youtube(wait=.2):
    return _control('youtube_pause', 'if (video.paused) await video.play(); else video.pause(); return !video.paused;')


def next_youtube(wait=.3):
    return _control('youtube_next', "const next = document.querySelector('.ytp-next-button'); if (!next) throw new Error('Next video unavailable'); next.click(); return true;")


def previous_youtube(wait=.3):
    return _control('youtube_previous', 'history.back(); return true;')


def stop_ad_monitor():
    """Compatibility hook for Chrome close; no background mouse automation is used."""
