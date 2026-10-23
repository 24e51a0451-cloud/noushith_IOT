"""Reject cross-origin browser mutations without changing native API clients."""
from urllib.parse import urlsplit
import hmac

from flask import current_app, jsonify, request


def require_operator():
    """Keep phone accounts separate from the operator's hardware privileges."""
    if request.endpoint in {'healthz', 'accounts.login', 'accounts.register',
                            'accounts.logout', 'accounts.register_mobile'}:
        return None
    username = current_app.config.get('MASTERHUB_OPERATOR_USER', '')
    password = current_app.config.get('MASTERHUB_OPERATOR_PASSWORD', '')
    if not username and not password:
        if request.remote_addr in ('127.0.0.1', '::1'):
            return None
        return jsonify(error='Configure operator credentials before enabling network access.'), 403
    auth = request.authorization
    if username and password and auth and auth.type == 'basic':
        valid_user = hmac.compare_digest((auth.username or '').encode(), username.encode())
        valid_password = hmac.compare_digest((auth.password or '').encode(), password.encode())
        if valid_user and valid_password:
            return None
    return jsonify(error='Operator authentication required.'), 401, {
        'WWW-Authenticate': 'Basic realm="MasterHub", charset="UTF-8"'}


def security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Referrer-Policy'] = 'same-origin'
    if request.endpoint != 'static':
        response.headers['Cache-Control'] = 'no-store'
    return response


def _origin(url):
    try:
        parsed = urlsplit(url)
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            return None
        if parsed.username or parsed.password:
            return None
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        return parsed.scheme, parsed.hostname, port
    except ValueError:
        return None


def reject_cross_origin_mutation():
    """Origin/Fetch Metadata defense; this does not authenticate API callers."""
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return None

    source = request.headers.get("Origin")
    if source is None:
        source = request.headers.get("Referer")
    cross_origin = source is not None and (
        _origin(source) is None or _origin(source) != _origin(request.host_url)
    )
    cross_site = request.headers.get("Sec-Fetch-Site") in ("cross-site", "same-site")
    if cross_origin or cross_site:
        return jsonify(success=False, error="Cross-origin state-changing requests are not allowed."), 403
    return None
