"""Bounded, correlated Office execution results for the existing PC transports."""
from collections import OrderedDict
from threading import Lock
import time

_lock = Lock()
_results = OrderedDict()


def expect(command_id, target, action):
    with _lock:
        while len(_results) >= 512:
            _results.popitem(last=False)
        _results[command_id] = {'success': True, 'status': 'PENDING', 'command_id': command_id,
                                'target': target, 'action': action, 'domain': 'desktop', 'created': time.monotonic()}


def receive(data, source=None):
    if not isinstance(data, dict) or not isinstance(data.get('command_id'), str):
        return False
    with _lock:
        expected = _results.get(data.get('command_id'))
        if not expected or expected['status'] != 'PENDING':
            return False
        if (data.get('protocol') != 'masterhub' or data.get('version') != '1.0' or
                data.get('message_type') != 'command_result' or data.get('domain') != 'desktop' or
                data.get('source') != expected['target'] or (source and source != expected['target']) or
                data.get('action') != expected['action'] or
                data.get('status') not in ('SUCCESS', 'FAILED', 'NEEDS_USER_ACTION') or
                type(data.get('success')) is not bool or
                data['success'] != (data['status'] == 'SUCCESS')):
            return False
        expected.update({key: data[key] for key in ('success', 'status', 'error', 'message', 'path') if key in data})
        return True


def get(command_id):
    with _lock:
        result = _results.get(command_id)
        if result is None:
            return None
        result = dict(result)
        if result['status'] == 'PENDING' and time.monotonic() - result['created'] > 90:
            result.update(success=False, status='UNKNOWN', error='No execution confirmation; check the client before retrying')
        result.pop('created')
        return result
