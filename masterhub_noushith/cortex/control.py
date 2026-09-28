"""Live Cortex gestures use MasterHub's mappings and engine, without HTTP retries.

One neutral sample arms a temporal frame. Singles and ordered combinations
execute once when the configured workflow window ends, using fresh samples.
"""
import math
import threading
import time
from copy import deepcopy
from fnmatch import fnmatch

from core.devices import device_registry
from core.engine import engine
from core.input_processor import input_processor
from core.metrics import metrics_tracker
from core.state import state_manager
from prediction_pipeline.pipeline import PipelineResult, SendResult
from services.workflow_service import load
from simulator.config import DEFAULT_CONFIDENCE_THRESHOLD

MOTION_COMMANDS = {f'{device}_{action}' for device in ('car', 'chair')
                   for action in ('forward', 'back', 'left', 'right', 'left360', 'right360')}


class CortexControl:
    accepts_neutral = True
    hold_seconds = 0.0
    release_seconds = 0.0

    def __init__(self):
        self.lock = threading.RLock()
        self.config = load('workflow_map.json')
        self.routes = load('command_map.json')
        self.modes = load('mode_map.json')['modes']
        self.gestures = load('gesture_map.json')
        self.params = {}
        self.last_result = None
        self.motion_stop = None
        self.reset()

    def reset(self):
        with self.lock:
            self.generation = None
            self.context = None
            self.pending = None
            self.candidate = None
            self.candidate_since = None
            self.neutral_since = None
            self.released = False
            self.message = 'Return to neutral, then perform a mental command.'

    def choices(self, mode):
        choices = []
        for gesture, mapping in self.gestures.items():
            if gesture.startswith('_') or gesture == 'neutral':
                continue
            command = mapping.get(mode, mapping.get('default'))
            if not command or command == 'neutral':
                continue
            label = command.replace('mode_', 'Open ').replace('_', ' ').capitalize()
            for item in list(self.config['domains'].values()) + list(self.config['devices'].values()):
                if self.modes.get(item.get('mode'), {}).get('switch_command') == command:
                    label = item['label']
            for items in self.config['bci_workflow'].values():
                match = next((c for c in items if c['id'] == command), None)
                if match:
                    label = match['label']
            if gesture == self.config['navigation']['back']:
                label = 'Back'
            elif gesture == self.config['navigation']['main_menu']:
                label = 'Main menu'
            action = self.routes.get(command, {}).get('action', '')
            fields = next((v for k, v in self.config['parameters'].items() if fnmatch(action, k)), [])
            choices.append({'gesture': gesture, 'command': command, 'label': label,
                            'parameters': fields})
        return choices

    def snapshot(self):
        mode = state_manager.mode.value
        domain = next((dict(id=k, **v) for k, v in self.config['domains'].items() if v['mode'] == mode), None)
        device = next((dict(id=k, **v) for k, v in self.config['devices'].items() if v.get('mode') == mode), None)
        if device:
            domain = dict(id=device['domain'], **self.config['domains'][device['domain']])
        with self.lock:
            pending = self.pending
            return {'mode': mode, 'domain': domain, 'device': device,
                    'target': device_registry.get_active_target(), 'choices': self.choices(mode),
                    'parameters': deepcopy(self.params), 'message': self.message,
                    'pending': {'gesture': pending['gesture'],
                                'duration': pending['duration'],
                                'label': next((c['label'] for c in self.choices(mode) if c['gesture'] == pending['gesture']), 'Waiting for second gesture'),
                                'remaining': max(0, pending['deadline'] - time.monotonic())} if pending else None,
                    'last_result': deepcopy(self.last_result),
                    'threshold': DEFAULT_CONFIDENCE_THRESHOLD,
                    'hold_seconds': self.hold_seconds,
                    'sequence_seconds': metrics_tracker.get_temporal_window()}

    def set_parameters(self, command, params):
        known = next((c for mode in {m for g, v in self.gestures.items() if not g.startswith('_') for m in v}
                      for c in self.choices(mode) if c['command'] == command), None)
        if not known or not known['parameters']:
            raise ValueError('Select a mental command with input fields.')
        if not isinstance(params, dict) or set(params) - set(known['parameters']):
            raise ValueError('Only the displayed input fields are accepted.')
        if any(not isinstance(v, str) or len(v) > 10000 for v in params.values()):
            raise ValueError('Inputs must be text, up to 10000 characters each.')
        with self.lock:
            self.params[command] = dict(params)

    def stop_motion(self):
        with self.lock:
            stop = self.motion_stop
            self.motion_stop = None
        if stop:
            try:
                result = engine.process(stop, {'source': 'cortex'})
            except Exception as exc:
                result = {'success': False, 'error': str(exc)}
            with self.lock:
                self.last_result = dict(result, gesture='neutral', command=stop)
                self.message = 'Motion stopped.' if result.get('success') else 'Stop failed. Use the device stop control.'

    def process(self, prediction):
        from cortex import dashboard
        token = dashboard.control_token()
        now = time.monotonic()
        mode = state_manager.mode.value
        target = device_registry.get_active_target()
        gesture = prediction.command
        power = prediction.confidence
        empty = PipelineResult(False, prediction, reason='waiting')
        dispatch = None
        stop_motion = False
        with self.lock:
            if token is None:
                self.reset()
                return empty
            if token != self.generation or self.context != (mode, target):
                self.reset()
                self.generation, self.context = token, (mode, target)
            if gesture == 'neutral':
                self.candidate = None
                if self.neutral_since is None:
                    self.neutral_since = now
                if now - self.neutral_since >= self.release_seconds:
                    self.released = True
                    stop_motion = bool(self.motion_stop)
                    if not self.pending:
                        self.message = f'Ready. A command at {DEFAULT_CONFIDENCE_THRESHOLD:.0%} power starts the temporal window.'
            else:
                self.neutral_since = None
            valid = math.isfinite(power) and 0 <= power <= 1 and power >= DEFAULT_CONFIDENCE_THRESHOLD
            if gesture != 'neutral' and not valid and not self.pending:
                self.candidate = None
                self.message = 'Command power below threshold.'
            choices = {c['gesture']: c for c in self.choices(mode)}
            if self.pending and now >= self.pending['deadline']:
                dispatch, self.pending = self.pending, None
                self.released = False
                if dispatch['gesture'] not in choices:
                    dispatch = None
                    self.message = 'Window ended without an assigned command. Return to neutral and try again.'
            elif self.pending:
                first = self.pending['gesture']
                # A distinct second gesture is enough; neutral between gestures is optional.
                # Repeated packets of a held gesture never become another command.
                if valid and gesture != 'neutral' and '+' not in first and gesture != first:
                    combo = first + '+' + gesture
                    if combo in choices:
                        self.pending['gesture'] = combo
                        self.pending['power'] = min(self.pending['power'], power)
                        self.message = f"{choices[combo]['label']} captured. Executing when this window ends."
                    else:
                        self.pending = None
                        self.released = False
                        self.message = 'Combination not assigned. Frame cancelled; return to neutral to retry.'
            elif gesture != 'neutral' and valid and self.released:
                self.released = False
                if gesture in choices or any(g.startswith(gesture + '+') for g in choices):
                    duration = metrics_tracker.get_temporal_window()
                    self.pending = {'gesture': gesture, 'power': power, 'mode': mode,
                                    'target': target, 'token': token,
                                    'duration': duration, 'deadline': now + duration}
                    self.message = 'Window started. Add a second gesture for a combination, or wait for the single command.'
                else:
                    self.message = 'This mental command is not assigned in the current menu.'
        if stop_motion:
            self.stop_motion()
        if dispatch:
            return self._dispatch(dispatch, prediction)
        return empty

    def _dispatch(self, item, prediction):
        from cortex import dashboard
        if (dashboard.control_token() != item['token'] or state_manager.mode.value != item['mode']
                or device_registry.get_active_target() != item['target']):
            self.reset()
            return PipelineResult(False, prediction, reason='context_changed')
        start = time.perf_counter()
        command = input_processor.normalize({'gesture': item['gesture'], 'mode': item['mode']})
        if command in MOTION_COMMANDS and (prediction.command != item['gesture'] or prediction.confidence < DEFAULT_CONFIDENCE_THRESHOLD):
            self.message = 'Movement cancelled: keep the direction active until the window ends. Neutral stops motion.'
            return PipelineResult(False, prediction, reason='movement_released')
        choice = next((c for c in self.choices(item['mode']) if c['command'] == command), {})
        with self.lock:
            params = dict(self.params.get(command, {}))
        missing = [f for f in choice.get('parameters', []) if not params.get(f, '').strip()]
        if missing:
            result = {'success': False, 'command': command, 'error': 'Save inputs first: ' + ', '.join(missing)}
        else:
            params.update(source='cortex', gesture=item['gesture'], target=item['target'],
                          confidence=item['power'], confidence_threshold=DEFAULT_CONFIDENCE_THRESHOLD)
            try:
                # Stop the previous mobility target before navigating away or changing direction.
                self.stop_motion()
                result = engine.process(command, params)
            except Exception as exc:
                result = {'success': False, 'command': command, 'error': str(exc)}
        elapsed = (time.perf_counter() - start) * 1000
        with self.lock:
            if result.get('success') and command in MOTION_COMMANDS:
                self.motion_stop = 'car_stop' if command.startswith('car_') else 'chair_stop'
            self.last_result = dict(result, gesture=item['gesture'], command=command)
            self.message = 'Command accepted by MasterHub.' if result.get('success') else result.get('error', 'Command failed.')
        sent = SendResult(prediction, bool(result.get('success')), 200 if result.get('success') else 422,
                          elapsed, dict(result, gesture=item['gesture'], power=item['power']))
        return PipelineResult(sent.success, prediction, send_result=sent)


cortex_control = CortexControl()
