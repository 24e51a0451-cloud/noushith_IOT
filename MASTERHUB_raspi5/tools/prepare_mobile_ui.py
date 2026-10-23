from pathlib import Path

project = Path(r'D:\GALATICX\BCI_remotecontroll_jiosaavn')
staging = Path(__file__).resolve().parents[1] / '.mobile-ui-update'
for name in ('app/src/main/AndroidManifest.xml', 'app/build.gradle.kts', 'app/src/main/res/values/strings.xml', 'README.md'):
    content = (project / name).read_text(encoding='utf-8')
    if name.endswith('AndroidManifest.xml'):
        content = content.replace('@android:style/Theme.Material.Light.NoActionBar', '@android:style/Theme.Material.NoActionBar')
    elif name.endswith('build.gradle.kts'):
        content = content.replace('versionCode = 2', 'versionCode = 3').replace('versionName = "0.2.0"', 'versionName = "0.3.0"')
    elif name.endswith('strings.xml'):
        content = content.replace('</resources>', '    <string name="track_time">%1$s / %2$s</string>\n    <string name="volume_percent">Volume %1$d%%</string>\n</resources>')
    else:
        content += '\n## Version 0.3 dark dashboard\n\nThe home screen shows broker connectivity, remote command readiness, now-playing metadata,\ntrack position, music volume, permission status and latest activity. Start/Stop controls\nremain visible in the connection card. Expand Connection Settings to edit the broker,\ntopic prefix and credentials while stopped; Start saves the changes.\n\nNow-playing is read from the existing JioSaavn session. It does not imply the BCI headset\nis connected. MQTT broker and mobile topics are unchanged from version 0.2.\n'
    destination = staging / name
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(content, encoding='utf-8')
print('Prepared UI-only project update, version 0.3.0')
