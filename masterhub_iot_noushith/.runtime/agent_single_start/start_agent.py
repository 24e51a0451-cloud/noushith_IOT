"""Start from saved settings, or inspect them without connecting to MQTT."""
import sys
from config.loader import load_config


def main():
    config = load_config()
    transport = config['transport']
    mqtt = transport.get('mqtt', {})
    print('Saved device ID:', config['device_id'], flush=True)
    print('Saved transport:', transport['type'], flush=True)
    if transport['type'] == 'mqtt':
        print('Saved MQTT broker:', str(mqtt.get('broker')) + ':' + str(mqtt.get('port') or 1883), flush=True)
        print('Saved MQTT client ID:', mqtt.get('client_id') or 'masterhub-agent-' + config['device_id'], flush=True)
    print('Edit .env to change this laptop settings. Explicit CLI options override saved settings.', flush=True)
    if sys.argv[1:] == ['--check-config']:
        return
    from agent.pc_agent import main as run_agent
    run_agent()


if __name__ == '__main__':
    main()
