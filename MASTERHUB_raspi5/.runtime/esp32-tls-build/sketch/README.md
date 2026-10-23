#line 1 "D:\\GALATICX\\masterhub_iot_noushith\\firmware\\masterhub_esp32_tls\\README.md"
# MasterHub ESP32 TLS firmware

Open `masterhub_esp32_tls.ino` in Arduino IDE. This is the complete supplied sketch with a focused MQTT migration.

- Broker: `13.49.213.239:8883`, TLS with certificate verification.
- The supplied username/password and `broker.crt` are already embedded. Keep the sketch private.
- Clock synchronization starts after Wi-Fi connects. MQTT waits for the clock without blocking the main loop; connection attempts themselves remain synchronous.
- Existing BLE Wi-Fi provisioning, GPIO assignments, device identity, topics, LoRa tank logic, relays and DFPlayer behavior are preserved.
- Firmware version: `2.4.2-unified-tls`.

## Upload

1. Select your actual ESP32 board and USB port. The compile target used here is ESP32 Dev Module (`esp32:esp32:esp32`).
2. Use ESP32 core 3.3.2, PubSubClient 2.8, NimBLE-Arduino 2.5.1 and ArduinoJson 7.4.3 (the installed versions).
3. Verify and upload through USB. Keep your existing flash/partition choices unless the compiler reports insufficient application space.
4. Open Serial Monitor at 115200 baud. Provision Wi-Fi through the existing BLE flow if needed.
5. Look for `[MQTT] Connecting securely to 13.49.213.239:8883... CONNECTED!` and verify sensor data in MasterHub before testing actuators.

If the log keeps reporting that it is waiting for NTP, allow the device to reach `pool.ntp.org` or `time.google.com` over UDP 123. Do not disable certificate verification.

The embedded certificate expires on 22 October 2027. Replace it and update the firmware before then. The existing HTTP OTA implementation is unchanged and is not secured by MQTT TLS.

This sketch retains the supplied device ID `00:4B:12:30:81:02` and shared `iot/esp32/...` topics. Do not flash multiple independently controlled nodes with the same identity/topic configuration.

No board has been flashed or physically tested by this task.
