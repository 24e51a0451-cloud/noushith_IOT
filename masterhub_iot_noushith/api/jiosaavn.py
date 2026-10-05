from flask import Blueprint, jsonify
from services.mobile_mqtt_service import mobile_mqtt_service, selected_mobile_service
from core.devices import device_registry

jiosaavn_bp = Blueprint('jiosaavn', __name__, url_prefix='/api/jiosaavn')


def current_service():
    device = device_registry.get(device_registry.get_active_target())
    return selected_mobile_service() if device and device.get('device_category') == 'mobile' else mobile_mqtt_service


@jiosaavn_bp.get('/status')
def status():
    service = current_service()
    service.start()
    return jsonify(service.snapshot())


@jiosaavn_bp.get('/media')
def media():
    service = current_service()
    service.start()
    snapshot = service.snapshot()
    return jsonify(media=snapshot['media'], online=snapshot['online'])
