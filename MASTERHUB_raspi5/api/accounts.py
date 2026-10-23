"""Authenticated Android registration APIs. Existing dashboard APIs stay unchanged."""
from collections import OrderedDict
import os
import threading
import time

from flask import Blueprint, current_app, jsonify, request
from core import account_store
from core.devices import device_registry

accounts_bp = Blueprint('accounts', __name__, url_prefix='/api')
_attempts = OrderedDict()
_lock = threading.Lock()


def path():
    return current_app.config.get('MASTERHUB_DATABASE', account_store.DEFAULT_DATABASE)


def token():
    value = request.headers.get('Authorization', '')
    return value[7:] if value.startswith('Bearer ') else ''


@accounts_bp.before_request
def guard():
    if request.content_length and request.content_length > 8192:
        return jsonify(error='Request is too large'), 413
    if request.endpoint in ('accounts.register', 'accounts.login'):
        key = request.remote_addr or 'unknown'
        now = time.monotonic()
        with _lock:
            recent = [stamp for stamp in _attempts.pop(key, []) if stamp > now - 60]
            _attempts[key] = recent
            while len(_attempts) > 4096:
                _attempts.popitem(last=False)
            if len(recent) >= 10:
                return jsonify(error='Too many login attempts. Try again in one minute.'), 429
            recent.append(now)


@accounts_bp.after_request
def private_response(response):
    response.headers['Cache-Control'] = 'no-store'
    return response


def payload():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ValueError('Expected a JSON object')
    return data


def auth(registering):
    try:
        return jsonify(account_store.authenticate(path(), payload(), registering)), 201 if registering else 200
    except ValueError as error:
        return jsonify(error=str(error)), 409 if str(error) == 'Username is already registered' else 400
    except PermissionError as error:
        return jsonify(error=str(error)), 401


@accounts_bp.post('/auth/register')
def register():
    return auth(True)


@accounts_bp.post('/auth/login')
def login():
    return auth(False)


@accounts_bp.post('/auth/logout')
def logout():
    with account_store.database(path()) as db:
        db.execute('DELETE FROM sessions WHERE token_hash=%s', (account_store.token_hash(token()),))
    return jsonify(success=True)


@accounts_bp.post('/mobile/devices/register')
def register_mobile():
    user = account_store.session_user(path(), token())
    if user is None:
        return jsonify(error='Session expired. Please log in again.'), 401
    try:
        phone = account_store.register_phone(path(), user['id'], payload())
    except ValueError as error:
        return jsonify(error=str(error)), 400
    record = device_registry.register(phone['device_id'], name=phone['name'], device_category='mobile',
                                      platform='android', capabilities=['ai_ml'], transport='mqtt')
    scheme = 'ssl' if os.getenv('BCI_MOBILE_MQTT_TLS', '').lower() == 'true' else 'tcp'
    mqtt = dict(uri=os.getenv('BCI_MOBILE_PUBLIC_MQTT_URI') or
                f"{scheme}://{os.getenv('BCI_MOBILE_MQTT_HOST', '52.21.249.6')}:{os.getenv('BCI_MOBILE_MQTT_PORT', '1883')}",
                prefix=f"masterhub/mobile/{phone['device_id']}",
                username=os.getenv('BCI_MOBILE_DEVICE_MQTT_USERNAME', ''),
                password=os.getenv('BCI_MOBILE_DEVICE_MQTT_PASSWORD', ''))
    return jsonify(device=record, mqtt=mqtt), 201
