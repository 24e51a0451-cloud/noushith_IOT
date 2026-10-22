"""Read persisted runtime history without exposing database connection settings."""
from flask import Blueprint, jsonify, request
from services import event_store as storage

history_bp = Blueprint('history', __name__, url_prefix='/api/database')


@history_bp.get('/activity')
def activity():
    try:
        limit = int(request.args.get('limit', 50))
        before = int(request.args['before']) if 'before' in request.args else None
        if not 1 <= limit <= 200 or (before is not None and before < 1):
            raise ValueError()
    except ValueError:
        return jsonify(error='limit must be 1–200; before must be a positive integer'), 400
    try:
        rows = storage.event_store.history(limit, before, request.args.get('device_id'), request.args.get('kind'))
        return jsonify(events=rows, next_before=rows[-1]['sequence'] if len(rows) == limit else None,
                       storage=storage.event_store.health())
    except Exception:
        return jsonify(error='Database history unavailable. Live controls remain available.',
                       storage=storage.event_store.health()), 503
