# IoT tank monitoring

Open the dashboard and select IoT Smart Home. The tank panel remains visible during IoT device selection and command execution. Other domains do not show it.

Enter tank height, choose cm or ft, and click **Save & calculate**. MasterHub saves the setting in `.runtime/tank.json`; it survives restarts. Changing units converts the input rather than changing the physical height. Saving updates only MasterHub's calculation and does not send a firmware or pump command.

With the ultrasonic sensor at the tank top, water depth is `height_cm - distance_cm`; level is `100 * depth / height_cm`. One foot is exactly 30.48 cm. Valid heights are 5–5000 cm. Mounting offsets must be accounted for in calibration before trusting this simple top-mounted calculation. Height percentage is not a volume percentage for irregular tanks.

The existing MQTT sensor message must contain `distance` in centimetres and `float` (0 = not triggered, 1 = overflow). Optional `rssi` is shown in dBm. Example: `{"deviceId":"esp32","distance":84,"float":0,"rssi":-87}` on `iot/esp32/sensor`. A 300 cm height and 84 cm distance give 216 cm water depth and 72% level. No sample values are shown in production.

`MASTERHUB_TANK_DEVICE_ID` selects the sensor cache key; the default `esp32` maps to the unified gateway. For a MAC-scoped gateway use its device ID. This version supports one configured tank; a gateway multiplexing multiple LoRa sensors must expose a distinct device ID/topic for the selected tank. Confirm distance units and float polarity with the firmware before use.

`MASTERHUB_TANK_STALE_SECONDS` defaults to 30 seconds; choose a threshold above the normal telemetry interval. MQTT being connected does not mean LoRa readings are fresh. Retained messages and status-only `lastSensor` snapshots remain unverified. Invalid or missing distance never becomes an empty-tank value. Float overflow remains independent of the percentage calculation. No automatic pump control is included.

`GET /api/iot/status` keeps all existing fields and adds `tank`. `POST /api/iot/tank-height` accepts `{"height":300,"unit":"cm"}` or `{"height":10,"unit":"ft"}` and returns the saved configuration and recalculated tank data. Both use existing operator access protection; POST also uses existing cross-origin mutation protection. Historical charts are not included in this version.

Focused tests without a database: `.venv/Scripts/python.exe -m unittest discover -s tests -p test_tank_monitor.py`. Browser logic checks: `node tests/test_tank_frontend.cjs`.
