"""Existing Masterhub v1 envelope, with durable duplicate protection."""
import json
import re
import sqlite3
import threading
import time

from office_client.office import OFFICE_ACTIONS, validate

MAX_FRAME = 65536


class CommandReceiver:
    def __init__(self, device_id, execute, journal):
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', device_id):
            raise ValueError('device_id must contain only letters, digits, underscore or hyphen')
        self.device_id = device_id
        self.execute = execute
        self.lock = threading.Lock()
        self.db = sqlite3.connect(str(journal), check_same_thread=False)
        self.db.execute('CREATE TABLE IF NOT EXISTS commands (id TEXT PRIMARY KEY, body TEXT, result TEXT, created REAL)')
        self.db.commit()

    def handle(self, raw, retained=False):
        data = {}
        try:
            if len(raw) > MAX_FRAME:
                raise ValueError('Command frame is too large')
            data = json.loads(raw)
            if not isinstance(data, dict):
                data = {}
                raise ValueError('Command must be a JSON object')
            if retained:
                raise ValueError('Retained commands are not executable')
            if (data.get('protocol'), data.get('version'), data.get('message_type')) != ('masterhub', '1.0', 'command'):
                raise ValueError('Expected a Masterhub v1 command envelope')
            if data.get('target') != self.device_id or data.get('domain') != 'desktop':
                raise ValueError('Wrong target or domain')
            command_id = data.get('command_id')
            if not isinstance(command_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', command_id):
                raise ValueError('Invalid command_id')
            action = data.get('action')
            if not isinstance(action, str) or action not in OFFICE_ACTIONS:
                raise ValueError('Unsupported Office action')
            params = data.get('params', {})
            validate(action, params)
            timestamp = data.get('timestamp')
            if type(timestamp) not in (int, float) or not -30 <= time.time() - timestamp <= 120:
                raise ValueError('Command expired or timestamp invalid; synchronize the PC clocks')
            body = json.dumps([data['target'], action, params], sort_keys=True)
            with self.lock:
                row = self.db.execute('SELECT body, result FROM commands WHERE id=?', (command_id,)).fetchone()
                if row:
                    if row[0] != body:
                        raise ValueError('command_id was reused with different content')
                    if row[1]:
                        return json.loads(row[1])
                    return self.response(data, {'success': False, 'status': 'NEEDS_USER_ACTION',
                                               'error': 'Previous execution was interrupted; check the document before sending a new command'})
                self.db.execute('DELETE FROM commands WHERE created < ?', (time.time() - 86400,))
                self.db.execute('INSERT INTO commands VALUES (?, ?, NULL, ?)', (command_id, body, time.time()))
                self.db.commit()
                try:
                    result = self.execute(action, params)
                except Exception as error:
                    result = {'success': False, 'status': 'FAILED', 'error': str(error)}
                response = self.response(data, result)
                self.db.execute('UPDATE commands SET result=? WHERE id=?', (json.dumps(response), command_id))
                self.db.commit()
                return response
        except (ValueError, TypeError, UnicodeError) as error:
            return self.response(data, {'success': False, 'status': 'FAILED', 'error': str(error)})

    def response(self, data, result):
        return {**result, 'protocol': 'masterhub', 'version': '1.0', 'message_type': 'command_result',
                'command_id': data.get('command_id'), 'source': self.device_id, 'domain': 'desktop',
                'action': data.get('action'), 'timestamp': time.time()}

    def close(self):
        self.db.close()
