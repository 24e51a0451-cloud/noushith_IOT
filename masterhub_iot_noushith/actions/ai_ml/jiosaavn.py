"""Search JioSaavn and start the first song in MasterHub's controlled Chrome window."""
import time
from urllib.parse import quote

import requests
from actions.desktop.youtube import _endpoint, _call, _evaluate, _LOCK


def _tab():
    base = _endpoint(start=True)
    response = requests.get(base + '/json/list', timeout=3)
    response.raise_for_status()
    for tab in response.json():
        if tab.get('type') == 'page' and tab.get('url', '').startswith('https://www.jiosaavn.com/'):
            return tab
    response = requests.put(base + '/json/new?' + quote('https://www.jiosaavn.com/', safe=''), timeout=3)
    response.raise_for_status()
    return response.json()


def search_and_play(query):
    if not isinstance(query, str) or not query.strip() or len(query) > 500:
        raise ValueError('Enter a song title (up to 500 characters).')
    query = query.strip()
    url = 'https://www.jiosaavn.com/search/song/' + quote(query, safe='')
    with _LOCK:
        tab = _tab()
        navigation = _call(tab, 'Page.navigate', {'url': url})
        if navigation.get('errorText'):
            raise RuntimeError(navigation['errorText'])
        _call(tab, 'Page.bringToFront', {})
        time.sleep(1)
        _evaluate(tab, '''
            const end = Date.now() + 15000;
            while (Date.now() < end) {
                // Scope to a song result so album/playlist/header controls cannot win.
                const link = document.querySelector('main a[href*="/song/"], .c-list a[href*="/song/"]');
                if (link && !location.pathname.startsWith('/song/')) {
                    link.click(); return true;
                }
                await new Promise(r => setTimeout(r, 250));
            }
            throw new Error('No song result found. Check the query, connection or JioSaavn sign-in.');
        ''')
        time.sleep(1)
        _evaluate(tab, '''
            const end = Date.now() + 15000;
            while (Date.now() < end) {
                if (location.pathname.startsWith('/song/')) {
                    const buttons = [...document.querySelectorAll('main button, main [role="button"], main a, .o-block__body button, .o-block__body a')];
                    const play = buttons.find(el => el.getClientRects().length &&
                        /^(play|play song|play now)$/i.test((el.getAttribute('aria-label') || el.getAttribute('title') || el.textContent || '').trim()));
                    if (play) { play.click(); return true; }
                }
                await new Promise(r => setTimeout(r, 250));
            }
            throw new Error('The selected song has no available Play control.');
        ''')
        playing = _evaluate(tab, '''
            const end = Date.now() + 12000;
            while (Date.now() < end) {
                const media = [...document.querySelectorAll('audio, video')].find(m => !m.paused && m.readyState >= 2 && m.currentTime > 0);
                if (media || navigator.mediaSession?.playbackState === 'playing') return true;
                await new Promise(r => setTimeout(r, 250));
            }
            throw new Error('JioSaavn did not confirm playback. Check sign-in, availability or browser audio permissions.');
        ''')
        if playing is not True:
            raise RuntimeError('JioSaavn playback was not confirmed.')
    return {'success': True, 'query': query, 'url': url, 'playing': True}
