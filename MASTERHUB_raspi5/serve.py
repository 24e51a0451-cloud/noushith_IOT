"""Single-process production server for the shared hardware controller."""
import os


def main():
    from app import app
    if not app.config['MASTERHUB_OPERATOR_USER'] or len(app.config['MASTERHUB_OPERATOR_PASSWORD']) < 32:
        raise SystemExit('Set MASTERHUB_OPERATOR_USER and a unique operator password of at least 32 characters.')
    from waitress import serve
    from core.account_store import database
    from services.event_store import event_store
    from services.mobile_registration import mobile_registration
    with database() as db:
        db.execute('SELECT 1')
    event_store.start()
    from services.mqtt_service import mqtt_service
    mqtt_service.start()
    mobile_registration.start()
    try:
        # One process owns the hardware and in-memory state; SSE needs spare threads.
        serve(app, host=os.getenv('MASTERHUB_HOST', '127.0.0.1'),
              port=int(os.getenv('MASTERHUB_PORT', '5000')), threads=16,
              max_request_body_size=1024 * 1024)
    finally:
        event_store.stop()


if __name__ == '__main__':
    main()
