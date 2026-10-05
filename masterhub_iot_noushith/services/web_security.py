"""Reject cross-origin browser mutations without changing native API clients."""
from urllib.parse import urlsplit

from flask import jsonify, request


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
