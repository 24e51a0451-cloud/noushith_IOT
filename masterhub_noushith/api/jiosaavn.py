from flask import Blueprint, jsonify
from services.mobile_mqtt_service import mobile_mqtt_service

jiosaavn_bp = Blueprint('jiosaavn', __name__, url_prefix='/api/jiosaavn')


@jiosaavn_bp.get('/status')
def status():
    mobile_mqtt_service.start()
    return jsonify(mobile_mqtt_service.snapshot())


@jiosaavn_bp.get('/media')
def media():
    mobile_mqtt_service.start()
    snapshot = mobile_mqtt_service.snapshot()
    return jsonify(media=snapshot['media'], online=snapshot['online'])
