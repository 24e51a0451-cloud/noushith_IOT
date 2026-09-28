"""Translate MasterHub action parameters into the shared Android contract."""
import math
from services.mobile_mqtt_service import mobile_mqtt_service

COMMANDS = {
    'mobile_jiosaavn_next': 'Right_Next_Song',
    'mobile_jiosaavn_previous': 'Right_Previous_Song',
    'mobile_jiosaavn_play_pause': 'Right_Play_Pause',
    'mobile_jiosaavn_volume_up': 'Right_Volume_Up',
    'mobile_jiosaavn_volume_down': 'Right_Volume_Down',
    'mobile_jiosaavn_search': 'SEARCH',
    'mobile_jiosaavn_launch': 'LAUNCH',
    'mobile_jiosaavn_home': 'Right_Return_to_Home',
}


def execute(action, params=None):
    params = params or {}
    if action not in COMMANDS:
        return {'success': False, 'error': 'Unknown mobile action'}
    try:
        confidence = float(params.get('confidence', 1.0))
        if not math.isfinite(confidence) or not 0 <= confidence <= 1:
            raise ValueError()
    except (ValueError, TypeError):
        return {'success': False, 'error': 'confidence must be between 0 and 1'}
    if params.get('Is_Actionable', True) is not True:
        return {'success': False, 'error': 'Command is not actionable'}
    if action.endswith(('_search', '_launch')) and str(params.get('source', '')).lower() in ('cortex', 'bci'):
        return {'success': False, 'error': 'Search and Launch require manual input'}
    query = params.get('query', '')
    if not isinstance(query, str) or len(query) > 500:
        return {'success': False, 'error': 'query must be text of at most 500 characters'}
    if action.endswith('_search') and not query.strip():
        return {'success': False, 'error': 'Search requires a query'}
    return mobile_mqtt_service.publish_command(COMMANDS[action], confidence, query.strip())
