"""Exercise live mental-command navigation; device handlers are isolated."""
import threading
from unittest.mock import patch

import pytest

from app import create_app
from core.engine import _DOMAIN_HANDLERS
from core.state import state_manager
from cortex import dashboard
from cortex.control import cortex_control as control
from cortex.prediction_mapper import map_mental_command, PredictionMappingError
from cortex.run_live import _process_prediction


@pytest.fixture
def live():
    from core.metrics import metrics_tracker
    metrics_tracker.set_temporal_window(4)
    dashboard.reset()
    state_manager.reset()
    control.reset()
    control.params.clear()
    control.last_result = None
    control.motion_stop = None
    client = create_app().test_client()
    dashboard.update_status(connected=True, authorized=True)
    dashboard.update_profile(current='trained-user')
    dashboard.update_prediction(gesture='neutral', confidence=0)
    client.post('/cortex/control', json={'enabled': True})
    clock = [100.0]

    def sample(gesture, dt=.4, power=.9):
        clock[0] += dt
        with patch('cortex.control.time.monotonic', return_value=clock[0]):
            _process_prediction(map_mental_command({'com': [gesture, power]}), control)

    def release():
        sample('neutral')
        sample('neutral')

    def command(gesture, wait=True):
        release()
        sample(gesture)
        sample(gesture)
        if wait:
            sample(gesture, 5)

    yield client, sample, release, command
    control.motion_stop = None
    control.reset()
    dashboard.reset()
    state_manager.reset()


@pytest.mark.parametrize('gestures,domain,action', [
    (['push', 'pull', 'left'], 'desktop', 'chrome_scroll_down'),
    (['left', 'push', 'right'], 'iot', 'left_light_on'),
    (['pull', 'push', 'left'], 'embedded', 'car_left'),
    (['right', 'push', 'push'], 'ai_ml', 'mobile_jiosaavn_play_pause'),
])
def test_live_headset_reaches_each_domain(live, gestures, domain, action):
    from contextlib import ExitStack
    client, sample, release, command = live
    with ExitStack() as stack:
        handlers = {name: stack.enter_context(patch.object(handler, 'execute', return_value={'success': True}))
                    for name, handler in _DOMAIN_HANDLERS.items()}
        for gesture in gestures:
            command(gesture)
        assert control.last_result['success']
        assert control.last_result['domain'] == domain
        assert control.last_result['action'] == action
        assert handlers[domain].called
        assert handlers[domain].call_args.args[1]['source'] == 'cortex'
        events = client.get('/api/activity-logs').json['logs']
        executed = [event for event in events if event['type'] == 'BCI']
        assert executed[-1]['status'] == 'SUCCESS'
        assert executed[-1]['domain'] == domain
        assert 'MASTERHUB_ACCEPTED' in executed[-1]['acknowledgement']


def test_hold_cannot_cascade_through_menus(live):
    client, sample, release, command = live
    command('push', wait=False)
    for _ in range(30):
        sample('push')
    assert state_manager.mode.value == 'DESKTOP_MODE'
    assert dashboard.live_snapshot()['metrics']['commands_sent'] == 1


def test_first_push_starts_window_without_extra_hold(live):
    client, sample, release, command = live
    sample('neutral', dt=0)
    sample('push', dt=0, power=.20)
    assert state_manager.mode.value == 'IDLE'
    assert control.pending['gesture'] == 'push'
    assert dashboard.live_snapshot()['metrics']['commands_sent'] == 0
    sample('neutral', dt=4)
    assert state_manager.mode.value == 'DESKTOP_MODE'


def test_repeated_action_requires_neutral_release(live):
    client, sample, release, command = live
    state_manager.maybe_switch_mode('mode_light')
    with patch.object(_DOMAIN_HANDLERS['iot'], 'execute', return_value={'success': True}) as handler:
        command('right', wait=False)
        for _ in range(20):
            sample('right')
        assert handler.call_count == 1
        command('right')
        assert handler.call_count == 2


def test_parameterized_command_requires_saved_inputs(live):
    client, sample, release, command = live
    state_manager.maybe_switch_mode('mode_chrome')
    with patch.object(_DOMAIN_HANDLERS['desktop'], 'execute', return_value={'success': True}) as handler:
        command('right')
        handler.assert_not_called()
        assert 'Save inputs' in control.last_result['error']
        assert client.post('/cortex/workflow', json={'command':'chrome_search', 'params':{'query':'robotics'}}).status_code == 409
        client.post('/cortex/control', json={'enabled':False})
        assert client.post('/cortex/workflow', json={'command':'chrome_search', 'params':{'query':'robotics'}}).status_code == 200
        client.post('/cortex/control', json={'enabled':True})
        command('right')
        assert handler.call_args.args[1]['query'] == 'robotics'


def test_pause_and_manual_mode_change_require_new_neutral(live):
    client, sample, release, command = live
    sample('neutral', dt=0)
    client.post('/cortex/control', json={'enabled': False})
    sample('push', dt=0)
    assert state_manager.mode.value == 'IDLE'
    client.post('/cortex/control', json={'enabled': True})
    sample('push', dt=0)
    assert state_manager.mode.value == 'IDLE'
    sample('neutral', dt=0)
    sample('push', dt=0)
    assert control.pending is not None
    state_manager.maybe_switch_mode('mode_iot')
    sample('push', dt=0)
    assert state_manager.mode.value == 'IOT_MODE'


def test_failure_is_visible_and_not_retried(live):
    client, sample, release, command = live
    state_manager.maybe_switch_mode('mode_light')
    with patch.object(_DOMAIN_HANDLERS['iot'], 'execute', return_value={'success':False, 'error':'Device offline'}) as handler:
        command('right', wait=False)
        for _ in range(20):
            sample('right')
        assert handler.call_count == 1
        assert control.snapshot()['last_result']['error'] == 'Device offline'
        assert client.get('/cortex/logs').json['logs'][-1]['status'] == 'FAILED'
        assert 'Device offline' in client.get('/cortex/logs').json['logs'][-1]['acknowledgement']


def test_monitor_explains_gate_without_executing_or_flooding(live):
    client, sample, release, command = live
    client.post('/cortex/control', json={'enabled': False})
    client.post('/cortex/logs/clear')
    for _ in range(20):
        sample('right')
    logs = client.get('/cortex/logs').json['logs']
    assert len(logs) == 1
    assert logs[0]['command'] == 'MONITOR'
    assert 'Enable Control' in logs[0]['acknowledgement']
    assert state_manager.mode.value == 'IDLE'


def test_acknowledgement_reaches_terminal_logger(live):
    client, sample, release, command = live
    with patch('cortex.dashboard.log.info') as terminal:
        command('right')
    assert any(call.args[1] == 'BCI' and call.args[6] == 'SUCCESS'
               and 'MASTERHUB_ACCEPTED' in call.args[7]
               for call in terminal.call_args_list)


def test_low_power_reports_threshold_gate(live):
    client, sample, release, command = live
    release()
    sample('right', power=.1)
    entry = client.get('/cortex/logs').json['logs'][-1]
    assert 'below threshold' in entry['acknowledgement']
    assert state_manager.mode.value == 'IDLE'


def test_mobility_stops_on_neutral_and_pause(live):
    client, sample, release, command = live
    state_manager.maybe_switch_mode('mode_car')
    with patch.object(_DOMAIN_HANDLERS['embedded'], 'execute', return_value={'success':True}) as handler:
        command('left', wait=True)
        release()
        assert handler.call_args.args[0] == 'car_stop'
        command('left', wait=True)
        client.post('/cortex/control', json={'enabled':False})
        assert handler.call_args.args[0] == 'car_stop'


def test_freshness_guard_does_not_depend_on_browser(live):
    client, sample, release, command = live
    last = dashboard.live_snapshot()['predictions'][-1]['received_at']
    with patch('cortex.dashboard.time.time', return_value=last + 4):
        assert not dashboard.control_enabled()


def test_nested_result_logging_does_not_deadlock():
    thread = threading.Thread(target=lambda: dashboard.update_pipeline_result(commands_sent=True), daemon=True)
    thread.start()
    thread.join(timeout=1)
    assert not thread.is_alive()


@pytest.mark.parametrize('power', [float('nan'), float('inf'), -.1, 1.1])
def test_malformed_power_cannot_reach_control(power):
    with pytest.raises(PredictionMappingError):
        map_mental_command({'com':['push', power]})


def test_standalone_console_and_input_validation(live):
    client, *_ = live
    page = client.get('/cortex/').get_data(as_text=True)
    assert 'id="bciChoices"' in page and 'id="bciOutcome"' in page
    assert client.post('/cortex/control', json=[]).status_code == 400
    client.post('/cortex/control', json={'enabled':False})
    assert client.post('/cortex/workflow', json={'command':'unknown','params':{}}).status_code == 400


def test_live_choices_include_combinations(live):
    client, *_ = live
    assert {'push+right', 'push+left'} <= {c['gesture'] for c in control.snapshot()['choices']}


def test_forward_waits_for_window_and_neutral_stops(live):
    client, sample, release, command = live
    state_manager.maybe_switch_mode('mode_car')
    with patch.object(_DOMAIN_HANDLERS['embedded'], 'execute', return_value={'success': True}) as handler:
        sample('neutral', dt=0)
        sample('push', dt=0, power=.20)
        assert handler.call_count == 0
        sample('push', dt=4, power=.20)
        assert handler.call_count == 1
        assert handler.call_args.args[0] == 'car_forward'
        sample('push', dt=0)
        assert handler.call_count == 1
        sample('neutral', dt=0)
        assert handler.call_args.args[0] == 'car_stop'
        assert handler.call_count == 2


def test_profile_loading_cannot_claim_success_while_disconnected(live):
    client, *_ = live
    with patch('cortex.service.get_runner', return_value=None):
        assert client.post('/cortex/profiles/load', json={'profile':'new-user'}).status_code == 409
    assert dashboard.live_snapshot()['status']['current_profile'] == 'trained-user'


def test_profile_switch_unloads_only_our_profile():
    from unittest.mock import Mock
    from cortex.profile import ProfileManager, ProfileError
    client = Mock()
    profiles = ProfileManager(client)
    client.call.side_effect = [{'name':'old','loadedByThisApp':True}, {}, {}]
    assert profiles.load_profile('token','headset','new')
    calls = client.call.call_args_list
    assert calls[1].args[1]['status'] == 'unload'
    assert calls[1].args[1]['profile'] == ''
    assert calls[2].args[1]['status'] == 'load'
    client.call.reset_mock()
    client.call.side_effect = [{'name':'other','loadedByThisApp':False}]
    with pytest.raises(ProfileError, match='EMOTIV'):
        profiles.load_profile('token','headset','new')
    assert client.call.call_count == 1


def test_failed_profile_query_does_not_reuse_cached_profile():
    from unittest.mock import Mock
    from cortex.profile import ProfileManager
    profiles = ProfileManager(Mock())
    profiles.current_profile = 'old'
    profiles.client.call.side_effect = RuntimeError('Disconnected')
    assert profiles.get_current_profile('token','headset') is None


@pytest.mark.parametrize('power,executes', [(0.20, True), (0.199, False), (0.73, True)])
def test_power_threshold_boundary(live, power, executes):
    client, sample, release, command = live
    assert control.snapshot()['threshold'] == .20
    state_manager.maybe_switch_mode('mode_light')
    with patch.object(_DOMAIN_HANDLERS['iot'], 'execute', return_value={'success': True}) as handler:
        release()
        sample('right', power=power)
        sample('right', power=power)
        assert handler.call_count == 0
        sample('neutral', dt=4)
        assert handler.call_count == int(executes)
        if executes:
            event = client.get('/api/activity-logs').json['logs'][-1]
            assert event['type'] == 'BCI'
            assert event['status'] == 'SUCCESS'


def test_profile_selected_after_connection_is_detected(live):
    from unittest.mock import Mock
    from cortex.run_live import LiveRunner
    client, *_ = live
    dashboard.update_profile(current='')
    runner = LiveRunner.__new__(LiveRunner)
    runner.headset_info = Mock(id='headset')
    runner.auth = Mock(token='token')
    runner.profiles = Mock()
    runner.profiles.get_current_profile.return_value = 'avanish'
    runner._refresh_profile()
    assert dashboard.live_snapshot()['status']['current_profile'] == 'avanish'
    assert client.post('/cortex/control', json={'enabled': True}).status_code == 200
    runner.profiles.load_profile.assert_not_called()


def test_current_profile_detection_survives_profile_list_failure(live):
    from unittest.mock import Mock
    from cortex.run_live import LiveRunner
    runner = LiveRunner.__new__(LiveRunner)
    runner.headset_info = Mock(id='headset')
    runner.auth = Mock(token='token')
    runner.profiles = Mock()
    runner.profiles.query_profiles.side_effect = RuntimeError('List unavailable')
    runner.profiles.get_current_profile.return_value = 'avanish'
    runner._refresh_profile(discover=True)
    assert dashboard.live_snapshot()['status']['current_profile'] == 'avanish'


def test_startup_loads_saved_available_profile(live, isolated_cortex_settings):
    from unittest.mock import Mock
    from cortex.run_live import LiveRunner
    with isolated_cortex_settings.open('a') as config:
        config.write("CORTEX_PROFILE='avanish'\n")
    runner = LiveRunner.__new__(LiveRunner)
    runner.headset_info = Mock(id='headset')
    runner.auth = Mock(token='token')
    runner.profiles = Mock()
    runner.profiles.query_profiles.return_value = ['iot', 'avanish']
    runner.profiles.get_current_profile.side_effect = [None, 'avanish']
    runner._refresh_profile(discover=True)
    runner.profiles.load_profile.assert_called_once_with('token', 'headset', 'avanish')
    assert dashboard.live_snapshot()['status']['current_profile'] == 'avanish'


@pytest.mark.parametrize('second,expected', [('right', 'IOT_MODE'), ('left', 'IDLE')])
@pytest.mark.parametrize('window', [2, 4, 8])
def test_headset_combination_waits_until_original_deadline(live, second, expected, window):
    from core.metrics import metrics_tracker
    client, sample, release, command = live
    metrics_tracker.set_temporal_window(window)
    state_manager.maybe_switch_mode('mode_light')
    with patch.object(_DOMAIN_HANDLERS['iot'], 'execute') as handler:
        sample('neutral', dt=0)
        sample('push', dt=0, power=.20)
        deadline = control.pending['deadline']
        sample(second, dt=.5, power=.20)
        assert control.pending['gesture'] == 'push+' + second
        assert control.pending['deadline'] == deadline
        assert state_manager.mode.value == 'LIGHT_MODE'
        sample('neutral', dt=window-.51)
        assert state_manager.mode.value == 'LIGHT_MODE'
        sample('neutral', dt=.02)
        assert state_manager.mode.value == expected
        handler.assert_not_called()
        logs = [e for e in client.get('/api/activity-logs').json['logs'] if e['type'] == 'BCI']
        assert len(logs) == 1
        assert logs[0]['gesture'] == 'push+' + second


def test_invalid_combination_cancels_without_fallback(live):
    client, sample, release, command = live
    sample('neutral', dt=0)
    sample('push', dt=0)
    sample('pull', dt=1)
    sample('neutral', dt=5)
    assert control.pending is None
    assert state_manager.mode.value == 'IDLE'
    assert dashboard.live_snapshot()['metrics']['commands_sent'] == 0


def test_pause_cancels_captured_combination(live):
    client, sample, release, command = live
    state_manager.maybe_switch_mode('mode_light')
    sample('neutral', dt=0)
    sample('push', dt=0)
    sample('right', dt=1)
    client.post('/cortex/control', json={'enabled': False})
    client.post('/cortex/control', json={'enabled': True})
    sample('neutral', dt=10)
    assert state_manager.mode.value == 'LIGHT_MODE'
    assert control.pending is None


def test_window_changes_apply_to_next_frame_only(live):
    from core.metrics import metrics_tracker
    client, sample, release, command = live
    sample('neutral', dt=0)
    sample('push', dt=0)
    deadline = control.pending['deadline']
    metrics_tracker.set_temporal_window(8)
    assert control.pending['duration'] == 4
    sample('neutral', dt=4)
    assert state_manager.mode.value == 'DESKTOP_MODE'
    sample('neutral', dt=0)
    sample('pull', dt=0)
    assert control.pending['duration'] == 8


def test_second_gesture_below_threshold_does_not_form_combination(live):
    client, sample, release, command = live
    sample('neutral', dt=0)
    sample('push', dt=0)
    sample('right', dt=1, power=.19)
    assert control.pending['gesture'] == 'push'
    sample('neutral', dt=3)
    assert state_manager.mode.value == 'DESKTOP_MODE'


def test_media_combination_is_assembled_and_delayed(live):
    client, sample, release, command = live
    state_manager.maybe_switch_mode('mode_jiosaavn')
    with patch.object(_DOMAIN_HANDLERS['ai_ml'], 'execute', return_value={'success': True}) as handler:
        sample('neutral', dt=0)
        sample('right', dt=0)
        sample('neutral', dt=.5)
        sample('push', dt=.5)
        handler.assert_not_called()
        sample('neutral', dt=3)
        handler.assert_called_once()
        assert handler.call_args.args[0] == 'volume_up'


def test_expired_connection_cannot_dispatch_pending_frame(live):
    client, sample, release, command = live
    sample('neutral', dt=0)
    sample('push', dt=0)
    dashboard.update_status(connected=False, authorized=False)
    sample('right', dt=5)
    assert state_manager.mode.value == 'IDLE'
    assert dashboard.live_snapshot()['metrics']['commands_sent'] == 0
