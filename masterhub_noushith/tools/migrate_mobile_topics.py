"""Apply the requested broker/namespace migration without exposing environment secrets."""
from pathlib import Path
from dotenv import set_key

root = Path(__file__).resolve().parents[1]
android = Path(r'D:\GALATICX\BCI_remotecontroll_jiosaavn')
staging = root / '.mobile-topic-update'
prefix = 'masterhub/mobile/MOBILE_001'
settings = {'BCI_MOBILE_MQTT_HOST': '52.21.249.6', 'BCI_MOBILE_MQTT_PORT': '1883',
            'BCI_MOBILE_MQTT_TLS': 'false', 'BCI_MOBILE_TOPIC_PREFIX': prefix}
for channel in ('commands', 'ack', 'error', 'media', 'status', 'heartbeat', 'control'):
    settings['BCI_MOBILE_' + channel.upper() + '_TOPIC'] = prefix + '/' + ('command' if channel == 'commands' else channel)
for filename in ('.env', '.env.mobile.example'):
    for key, value in settings.items():
        set_key(str(root / filename), key, value, quote_mode='never')

for relative in ('app/src/main/java/com/masterhub/bci/MainActivity.kt',
                 'app/src/main/java/com/masterhub/bci/RemoteService.kt',
                 'app/build.gradle.kts', 'README.md'):
    content = (android / relative).read_text(encoding='utf-8')
    content = content.replace('tcp://broker.emqx.io:1883', 'tcp://52.21.249.6:1883').replace('bci/rohan', prefix)
    if relative.endswith('MainActivity.kt'):
        content = content.replace('val prefs = getSharedPreferences("connection", MODE_PRIVATE)',
                                  'val prefs = ConnectionConfig.preferences(this)')
        content = content.replace('The default broker/topics are shared and unauthenticated. Use matching private broker credentials on MasterHub and this phone for personal use.',
                                  'Uses the MasterHub broker. Match its username and password if authentication is enabled.')
    elif relative.endswith('RemoteService.kt'):
        content = content.replace('val config = getSharedPreferences("connection", MODE_PRIVATE)',
                                  'val config = ConnectionConfig.preferences(this)')
        content = content.replace('$prefix/commands', '$prefix/command')
        content = content.replace('publish("ack", ack)', 'publish("ack", ack)\n            if (ack.optString("status") in listOf("FAILED", "REJECTED")) publish("error", ack)')
    elif relative.endswith('build.gradle.kts'):
        content = content.replace('versionCode = 1', 'versionCode = 2').replace('versionName = "0.1.0"', 'versionName = "0.2.0"')
    else:
        content = content.replace('The public default is shared and unauthenticated. For personal deployment use your own\nauthenticated TLS broker with topic ACLs and matching configuration on both ends.',
                                  'Both apps use 52.21.249.6:1883. Configure matching credentials if the broker requires authentication.')
        content += '\n## Version 0.2 connection migration\n\nOpening this update moves saved broker/topic settings to `tcp://52.21.249.6:1883` and\n`masterhub/mobile/MOBILE_001` once. Saved credentials are preserved. Restart remote control after updating.\n\nMobile channels: `/command`, `/ack`, `/error`, `/status`, `/media`, `/heartbeat`, `/control`.\nDesktop PC-agent channels remain `masterhub/devices/<PC_ID>/command|ack|status|error`.\nLocal Host desktop actions use no MQTT. Mobile command JSON remains the Android contract;\nit is not the PC-agent envelope. Use a unique mobile prefix for each phone.\n'
    destination = staging / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(content, encoding='utf-8')

doc = root / 'docs/mqtt_protocol.md'
content = doc.read_text(encoding='utf-8').replace('broker.emqx.io:1883', '52.21.249.6:1883').replace('bci/rohan', prefix)
content = content.replace('`/commands`', '`/command`').replace('`/ack`, `/media`', '`/ack`, `/error`, `/media`')
content = content.replace('The public defaults are intended for interoperability testing. They do not authenticate\nwho sends a command. For personal deployment use a private authenticated TLS broker,\nconfigure matching credentials on both sides and use topic ACLs. Do not retain commands.',
                        'This uses the same broker as hardware and desktop MasterHub. Configure matching\ncredentials if authentication is required. Do not retain commands. Failed/rejected ACKs\nare also published on `/error` for diagnostics; `/ack` remains authoritative.')
content += '\n## Verified desktop topic separation\n\nDesktop actions routed to PC agents use `masterhub/devices/<PC_ID>/command`, `/ack`,\n`/status`, `/error` (for example PC_001). Local Host actions bypass MQTT.\nThe legacy workflow `jiosaavn_topic` label is unused by the desktop handler.\nMobile uses `masterhub/mobile/MOBILE_001` so phone status is not consumed by the\nexisting `masterhub/devices/+/status` PC discovery subscription. Channel names match\nthe desktop convention; mobile retains its separate JSON contract and extra telemetry.\nThe `/api/jiosaavn/status` endpoint exposes effective broker and topic configuration.\n'
doc.write_text(content, encoding='utf-8')
print('Prepared Android topic migration and updated MasterHub mobile settings.')
