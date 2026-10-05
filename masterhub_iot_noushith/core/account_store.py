"""SQLite account, session and phone ownership storage for one MasterHub server."""
from contextlib import contextmanager
import hashlib
import os
from pathlib import Path
import re
import secrets
import sqlite3
import time
import uuid

from werkzeug.security import check_password_hash, generate_password_hash
from dotenv import load_dotenv

load_dotenv()

DEFAULT_DATABASE = Path(os.getenv('MASTERHUB_DATABASE', str(Path(__file__).resolve().parents[1] / 'data' / 'masterhub.db')))


@contextmanager
def database(path=DEFAULT_DATABASE):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(path), timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute('PRAGMA foreign_keys=ON')
    try:
        with connection:
            connection.executescript('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY, username TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL, created_at INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS sessions (
                    token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id),
                    expires_at INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS mobile_devices (
                    device_id TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id),
                    installation_id TEXT NOT NULL, name TEXT NOT NULL,
                    UNIQUE(user_id, installation_id));
                CREATE TABLE IF NOT EXISTS device_registry (
                    id INTEGER PRIMARY KEY CHECK(id=1), payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS mqtt_devices (
                    device_id TEXT PRIMARY KEY, username TEXT NOT NULL UNIQUE,
                    device_type TEXT NOT NULL, updated_at INTEGER NOT NULL);
            ''')
            yield connection
    finally:
        connection.close()


def credentials(payload):
    username = payload.get('username')
    password = payload.get('password')
    if not isinstance(username, str) or not re.fullmatch(r'[A-Za-z0-9_]{3,32}', username.strip()):
        raise ValueError('Username must contain 3–32 letters, numbers or underscores')
    if not isinstance(password, str) or not 8 <= len(password) <= 128:
        raise ValueError('Password must contain 8–128 characters')
    return username.strip().lower(), password


def token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


def authenticate(path, payload, register=False):
    username, password = credentials(payload)
    password_hash = generate_password_hash(password) if register else None
    with database(path) as db:
        if register:
            try:
                db.execute('INSERT INTO users(username,password_hash,created_at) VALUES(?,?,?)',
                           (username, password_hash, int(time.time() * 1000)))
            except sqlite3.IntegrityError:
                raise ValueError('Username is already registered') from None
        user = db.execute('SELECT * FROM users WHERE username=?', (username,)).fetchone()
        if not user or (not register and not check_password_hash(user['password_hash'], password)):
            raise PermissionError('Invalid username or password')
        now = int(time.time() * 1000)
        expires = now + 30 * 24 * 60 * 60 * 1000
        token = secrets.token_urlsafe(32)
        db.execute('DELETE FROM sessions WHERE expires_at<=?', (now,))
        db.execute('INSERT INTO sessions VALUES(?,?,?)', (token_hash(token), user['id'], expires))
        return dict(token=token, expires_at=expires, user=dict(id=user['id'], username=user['username']))


def session_user(path, token):
    if not token or len(token) > 256:
        return None
    with database(path) as db:
        row = db.execute('''SELECT users.id, users.username FROM sessions JOIN users ON users.id=sessions.user_id
                            WHERE token_hash=? AND expires_at>?''', (token_hash(token), int(time.time() * 1000))).fetchone()
        return dict(row) if row else None


def register_phone(path, user_id, payload):
    installation = payload.get('installation_id')
    name = payload.get('name')
    if not isinstance(installation, str) or not re.fullmatch(r'[A-Za-z0-9_-]{16,100}', installation):
        raise ValueError('Invalid phone installation ID')
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 100:
        raise ValueError('Phone name must contain 1–100 characters')
    if payload.get('device_category') != 'mobile' or payload.get('platform') != 'android':
        raise ValueError('Expected an Android mobile device')
    with database(path) as db:
        db.execute('''INSERT INTO mobile_devices VALUES(?,?,?,?)
                      ON CONFLICT(user_id,installation_id) DO UPDATE SET name=excluded.name''',
                   ('MOBILE_' + uuid.uuid4().hex, user_id, installation, name.strip()))
        return dict(db.execute('SELECT * FROM mobile_devices WHERE user_id=? AND installation_id=?',
                               (user_id, installation)).fetchone())
