import json
import uuid

from core.account_store import database
from core.devices import DeviceRegistry
from services.mobile_registration import register_device


def test_external_identity_delete_disappears_and_cannot_be_resaved(postgres_db):
    registry = DeviceRegistry(database_path=postgres_db)
    identifier = str(uuid.uuid4())
    register_device(dict(device_id=identifier, username='removed_phone', device_type='android'), postgres_db, registry)
    registry.set_active_target(identifier)
    with database(postgres_db) as db:
        db.execute('DELETE FROM mqtt_devices WHERE device_id=%s', (identifier,))
    registry._last_refresh = 0
    assert identifier not in {d['device_id'] for d in registry.list_all()}
    assert registry.get_active_target() == 'Local Host'
    registry.register('MANUAL_PC')
    restarted = DeviceRegistry(database_path=postgres_db)
    assert restarted.get(identifier) is None
    assert restarted.get('MANUAL_PC') is not None


def test_registry_json_edit_reloads_without_losing_live_presence(postgres_db):
    registry = DeviceRegistry(database_path=postgres_db)
    registry.register('DELETE_PC')
    registry.register('KEEP_PC', status='ONLINE')
    with database(postgres_db) as db:
        saved = json.loads(db.execute('SELECT payload FROM device_registry WHERE id=1').fetchone()['payload'])
        saved['devices'] = [d for d in saved['devices'] if d['device_id'] != 'DELETE_PC']
        db.execute('UPDATE device_registry SET payload=%s WHERE id=1', (json.dumps(saved),))
    registry._last_refresh = 0
    current = {d['device_id']: d for d in registry.list_all()}
    assert 'DELETE_PC' not in current
    assert current['KEEP_PC']['status'] == 'ONLINE'


def test_application_unregister_removes_identity(postgres_db):
    registry = DeviceRegistry(database_path=postgres_db)
    identifier = str(uuid.uuid4())
    register_device(dict(device_id=identifier, username='phone_delete', device_type='android'), postgres_db, registry)
    assert registry.unregister(identifier)
    with database(postgres_db) as db:
        assert db.execute('SELECT * FROM mqtt_devices WHERE device_id=%s', (identifier,)).fetchone() is None
    assert DeviceRegistry(database_path=postgres_db).get(identifier) is None
