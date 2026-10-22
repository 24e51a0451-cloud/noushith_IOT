"""Durable event outbox: MQTT/control paths never wait for a database connection."""
import atexit
import hashlib
import json
import logging
import os
from pathlib import Path
import re
import socket
import threading
import time
import uuid

from psycopg.types.json import Jsonb
from core.account_store import database

log = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parents[1]
SECRET = re.compile(r'password|secret|token|authorization|api.?key|credential', re.I)
URL_SECRET = re.compile(r'([a-z][a-z0-9+.-]*://)[^\s/@]+:[^\s/@]+@', re.I)


def sanitize(value):
    if isinstance(value, dict):
        return {str(k): '[redacted]' if SECRET.search(str(k)) else sanitize(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [sanitize(v) for v in value[:200]]
    if isinstance(value, str):
        return URL_SECRET.sub(r'\1[redacted]@', value)[:8192]
    if value is None or isinstance(value, (int, float, bool)):
        return value
    return str(value)[:256]


class EventStore:
    def __init__(self, spool=None, dsn=None, instance_id=None, autostart=True):
        self.spool = Path(spool or os.getenv('MASTERHUB_EVENT_SPOOL', str(ROOT / 'data/event-outbox')))
        self.dsn = dsn
        self.instance_id = instance_id or os.getenv('MASTERHUB_INSTANCE_ID') or hashlib.sha256(
            (socket.gethostname() + str(ROOT)).encode()).hexdigest()[:24]
        self.autostart = autostart
        self.lock = threading.Lock()
        self.flush_lock = threading.Lock()
        self.wake = threading.Event()
        self.stopped = threading.Event()
        self.thread = None
        self.last_error = None
        self.last_saved_at = None
        self.failed_records = 0

    def record(self, kind, device_id='', status='', payload=None, command_id=None, topic=''):
        try:
            event = dict(event_id=str(uuid.uuid4()), instance_id=self.instance_id,
                         received_at=time.time_ns() // 1_000_000, kind=str(kind)[:40],
                         device_id=str(device_id or '')[:200], status=str(status or '')[:80],
                         command_id=str(command_id)[:200] if command_id else None,
                         topic=str(topic)[:512], payload=sanitize(payload))
            encoded = json.dumps(event, allow_nan=False)
            if len(encoded.encode('utf-8')) > 131072:
                raise ValueError('Event exceeds storage limit')
            self.spool.mkdir(parents=True, exist_ok=True)
            final = self.spool / (str(event['received_at']) + '-' + event['event_id'] + '.json')
            temporary = final.with_suffix('.tmp')
            with temporary.open('x', encoding='utf-8') as stream:
                stream.write(encoded)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, final)
            if self.autostart:
                self.start()
            self.wake.set()
            return event['event_id']
        except Exception as error:
            self.failed_records += 1
            self.last_error = 'Could not queue event: ' + type(error).__name__
            log.error(self.last_error)
            return None

    def start(self):
        with self.lock:
            if self.thread and self.thread.is_alive():
                return
            self.stopped.clear()
            self.thread = threading.Thread(target=self._run, name='postgres-event-writer', daemon=True)
            self.thread.start()

    def _run(self):
        while not self.stopped.is_set():
            self.wake.clear()
            saved = self.flush_once()
            if saved:
                continue
            self.wake.wait(5)

    def flush_once(self):
        with self.flush_lock:
            files = sorted(self.spool.glob('*.json'))[:100]
            if not files:
                return 0
            try:
                events = []
                for path in files:
                    try:
                        event = json.loads(path.read_text(encoding='utf-8'))
                        if not isinstance(event, dict) or not all(key in event for key in (
                                'event_id', 'instance_id', 'received_at', 'kind', 'device_id',
                                'status', 'command_id', 'topic', 'payload')):
                            raise ValueError('Invalid queued event')
                        events.append((path, event))
                    except (ValueError, UnicodeError):
                        path.replace(path.with_suffix('.invalid'))
                        log.error('Invalid queued event quarantined; inspect event outbox')
                if not events:
                    return 0
                with database(self.dsn) as db:
                    for _, event in events:
                        db.execute('''INSERT INTO runtime_events
                            (event_id,instance_id,received_at,kind,device_id,status,command_id,topic,payload)
                            VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(event_id) DO NOTHING''',
                            tuple(event[k] for k in ('event_id','instance_id','received_at','kind',
                                'device_id','status','command_id','topic')) + (Jsonb(event['payload']),))
                for path, _ in events:
                    path.unlink(missing_ok=True)
                self.last_saved_at = time.time_ns() // 1_000_000
                self.last_error = None
                return len(events)
            except Exception as error:
                self.last_error = 'Event storage delayed: ' + type(error).__name__
                log.warning(self.last_error)
                return 0

    def history(self, limit=50, before=None, device_id=None, kind=None):
        clauses, values = ['instance_id=%s'], [self.instance_id]
        if before is not None:
            clauses.append('sequence<%s')
            values.append(before)
        if device_id:
            clauses.append('device_id=%s')
            values.append(device_id)
        if kind:
            clauses.append('kind=%s')
            values.append(kind)
        with database(self.dsn) as db:
            return list(db.execute('SELECT * FROM runtime_events WHERE ' + ' AND '.join(clauses) +
                ' ORDER BY sequence DESC LIMIT %s', values + [limit]))

    def health(self):
        return dict(pending=len(list(self.spool.glob('*.json'))), last_error=self.last_error,
                    failed_records=self.failed_records, quarantined=len(list(self.spool.glob('*.invalid'))),
                    last_saved_at=self.last_saved_at)

    def stop(self):
        self.stopped.set()
        self.wake.set()
        if self.thread:
            self.thread.join(timeout=2)


event_store = EventStore()
atexit.register(event_store.stop)


def record_event(*args, **kwargs):
    return event_store.record(*args, **kwargs)


def record_mqtt(topic, payload, *, device_id=None, retained=False, outgoing=False, status=None):
    parts = topic.split('/')
    channel = parts[-1]
    if isinstance(payload, (bytes, str)):
        try:
            payload = json.loads(payload)
        except (ValueError, UnicodeError):
            payload = str(payload)
    data = payload if isinstance(payload, dict) else {}
    identity = device_id or data.get('device_id') or data.get('deviceId') or data.get('target_device') or data.get('target')
    if not identity:
        identity = parts[2] if len(parts) >= 4 and parts[:2] in (['masterhub','devices'], ['masterhub','mobile'], ['iot','device']) else (parts[1] if len(parts) >= 3 else '')
    kind = 'command' if outgoing else {'heartbeat':'status','control':'status','pong':'status'}.get(channel, channel)
    state = status or ('PUBLISHED' if outgoing else data.get('status') or data.get('result') or '')
    if not outgoing and channel == 'ack' and not data.get('command_id'):
        state = 'UNCONFIRMED'
    if not outgoing and channel in ('status', 'heartbeat') and not state:
        state = ('ONLINE' if data['online'] else 'OFFLINE') if isinstance(data.get('online'), bool) else str(payload) if isinstance(payload, str) else 'RECEIVED'
    record_event(kind, identity, state, dict(message=payload, retained=bool(retained)),
                 command_id=data.get('command_id'), topic=topic)
