import json
from unittest.mock import patch
from pathlib import Path
from core.input_processor import InputProcessor
from core.state import Mode, state_manager
from core.engine import engine
from services.workflow_service import build_workflow

ROOT = Path(__file__).resolve().parents[1]


def test_every_displayed_gesture_matches_its_context():
    catalog = build_workflow()
    processor = InputProcessor()
    for domain in catalog['domains']:
        assert processor.normalize({'gesture': domain['gesture'], 'mode': 'IDLE'}) == domain['switch_command']
        for device in domain['devices']:
            if device['gesture']:
                assert processor.normalize({'gesture': device['gesture'], 'mode': domain['mode']}) == device['switch_command']
            for command in device['commands']:
                if command['gesture']:
                    resolved = processor.normalize({'gesture': command['gesture'], 'mode': device['mode']})
                    routes = json.loads((ROOT / 'mappings/command_map.json').read_text())
                    assert routes[resolved]['action'] == command['action']


def test_ordered_combinations_have_distinct_meanings():
    processor = InputProcessor()
    assert processor.normalize({'gesture': 'Push + Right', 'mode': 'JIOSAAVN_MODE'}) == 'mode_media'
    assert processor.normalize({'gesture': 'Right + Push', 'mode': 'JIOSAAVN_MODE'}) == 'media_volume_up'
    assert processor.normalize({'gesture': 'Right + Pull', 'mode': 'JIOSAAVN_MODE'}) == 'media_volume_down'
    assert processor.normalize({'gesture': 'Push + Left', 'mode': 'YOUTUBE_MODE'}) == 'mode_idle'


def test_manual_unmapped_commands_are_removed_and_bci_commands_retained():
    commands = {c['action']: c for d in build_workflow()['domains'] for device in d['devices'] for c in device['commands']}
    for action in ['open_calculator', 'open_calendar', 'youtube_mute', 'write_notepad']:
        assert action not in commands
    assert commands['car_stop']['gesture'] == 'left+right'
    assert commands['car_left360']['gesture'] == 'pull+left'
    assert commands['car_right360']['gesture'] == 'pull+right'
    assert commands['youtube_previous']['gesture'] == 'push'
    assert commands['compose_gmail']['gesture'] == 'push'
    assert commands['search_jiosaavn']['parameters'] == ['query']


def test_app_selection_opens_target_app_and_unassigned_gesture_is_noop():
    previous = state_manager.mode
    try:
        with patch('core.engine.desktop_handler.execute', return_value={'success': True}) as handler:
            result = engine.process('mode_youtube', {'target': 'TEST_PC'})
            assert result['success']
            handler.assert_called_once_with('open_youtube', {'target': 'TEST_PC'})
        with patch('core.engine.desktop_handler.execute') as handler:
            result = engine.process('neutral')
            assert result['type'] == 'no_op'
            handler.assert_not_called()
    finally:
        state_manager.transition(previous)


def test_chrome_scroll_focuses_window_before_scroll():
    from actions.desktop import chrome
    from unittest.mock import Mock
    window = Mock(isMinimized=False)
    with patch.object(chrome, '_require_pyautogui'), patch('pygetwindow.getWindowsWithTitle', return_value=[window]), patch.object(chrome, 'pyautogui') as gui, patch.object(chrome.time, 'sleep'):
        assert chrome.scroll_chrome('up')['success']
        window.activate.assert_called_once()
        gui.scroll.assert_called_once_with(5)
