import json
from unittest.mock import patch
from config.loader import load_config


def test_dotenv_identity_and_broker_override_json(tmp_path):
    folder = tmp_path / 'config'
    folder.mkdir()
    path = folder / 'agent_config.json'
    path.write_text(json.dumps({'device_id': 'PC_002', 'transport': {'type': 'mqtt'}}))
    (tmp_path / '.env').write_text('DEVICE_ID=PC_001\nMQTT_BROKER=192.0.2.10\nMQTT_PORT=1883\nMQTT_TLS_ENABLED=false\n')
    with patch.dict('os.environ', {}, clear=True):
        cfg = load_config(str(path))
    assert cfg['device_id'] == 'PC_001'
    assert cfg['transport']['mqtt']['broker'] == '192.0.2.10'
    assert cfg['transport']['mqtt']['port'] == 1883
    assert cfg['transport']['mqtt']['tls_enabled'] is False


def test_process_environment_overrides_dotenv_without_mutation(tmp_path):
    folder = tmp_path / 'config'
    folder.mkdir()
    path = folder / 'agent_config.json'
    path.write_text('{}')
    (tmp_path / '.env').write_text('DEVICE_ID=PC_001\nMQTT_BROKER=192.0.2.10\n')
    with patch.dict('os.environ', {'DEVICE_ID': 'PC_003'}, clear=True):
        import os
        cfg = load_config(str(path))
        assert cfg['device_id'] == 'PC_003'
        assert 'MQTT_BROKER' not in os.environ


def test_blank_client_id_uses_changed_device_id(tmp_path):
    folder = tmp_path / 'config'
    folder.mkdir()
    path = folder / 'agent_config.json'
    path.write_text(json.dumps({'device_id': 'PC_001', 'transport': {'type': 'mqtt', 'mqtt': {'client_id': 'masterhub-agent-PC_001'}}}))
    env = tmp_path / '.env'
    for device in ['PC_003', 'PC_004']:
        env.write_text('DEVICE_ID=' + device + '\nMASTERHUB_TRANSPORT=mqtt\nMQTT_CLIENT_ID=\n')
        with patch.dict('os.environ', {}, clear=True):
            config = load_config(str(path))
        assert config['device_id'] == device
        assert config['transport']['type'] == 'mqtt'
        assert config['transport']['mqtt']['client_id'] is None
