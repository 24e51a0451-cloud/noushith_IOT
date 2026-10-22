# Microsoft Office client for Masterhub

This Windows client runs Excel, Word and PowerPoint commands sent by Masterhub's existing MQTT or UART backend. Both transports use the unchanged `masterhub` v1 `action/params` envelope. Masterhub owns menus/gestures; the client owns execution and documents.

Office behavior/content was adapted from `D:/GALATICX/15-10/desktop/subplugins/office/`. The supplied source folder is unchanged. The new client retains the stock/degree Excel examples, Word project text and Python-domain PowerPoint slides, with explicit action names and owned-document handling instead of attaching to whichever document the user has active. Stock figures are static sample data.

## Requirements

- Windows x64, signed-in interactive user, installed/activated desktop Excel, Word and PowerPoint.
- One Office client process per device ID. Do not share its identity with another desktop agent.
- For MQTT: a reachable broker with authentication and topic ACLs. Allow only the Masterhub operator to publish to this client's `/command` topic; allow the client to publish its own status/ack/error. Use TLS outside a trusted isolated network. The client does not authenticate an arbitrary sender just because the sender knows its device ID.
- For UART: a supported direct PC-to-PC serial link, its drivers and matching 115200 baud, 8-N-1 settings. Each PC uses its own COM port name; an ordinary PC-to-PC USB cable is not a serial bridge.
- Keep both PC clocks synchronized; commands older than two minutes or more than 30 seconds in the future are rejected.

## Run the client on the target desktop

Copy `MasterhubOfficeClient.exe` and a copy of `config.example.json` to the client PC. Rename the copy to `config.json` and edit the actual connection settings.

```powershell
.\MasterhubOfficeClient.exe --config .\config.json
```

For source use, copy the `office_client` folder and run from its parent folder:

```powershell
python -m pip install -r office_client/requirements.txt
python -m office_client --config office_client/config.example.json
```

The example uses ID `PC_OFFICE_001`, UART `COM3`, 115200 baud and MQTT disabled. COM3 is only an example: replace it with the client's actual port. For MQTT-only use, set `uart.port` to an empty string and set `mqtt.host` to your broker. For both, configure both sections. Choose the desired transport for the registered target in Masterhub; commands are not broadcast automatically over both links.

Example MQTT settings (replace the hostname with your broker):

```json
{
  "device_id": "PC_OFFICE_001",
  "mqtt": {"host": "YOUR_BROKER", "port": 8883, "tls": true},
  "uart": {"port": "", "baudrate": 115200}
}
```

Set `MASTERHUB_MQTT_USERNAME` and `MASTERHUB_MQTT_PASSWORD` in the client process environment. For a private certificate authority, set `mqtt.ca_file` to its certificate path. Credentials are not embedded in the executable or example configuration.

On the Masterhub process, configure the same broker in the existing hardware connection settings. For an authenticated TLS broker, set `MASTERHUB_MQTT_USERNAME`, `MASTERHUB_MQTT_PASSWORD`, `MASTERHUB_MQTT_TLS=true` and optionally `MASTERHUB_MQTT_CA_FILE` before starting Masterhub. Broker accounts may be different; their ACLs must permit the corresponding publish/subscribe directions.

Existing topics:

```text
masterhub/devices/PC_OFFICE_001/command
masterhub/devices/PC_OFFICE_001/ack
masterhub/devices/PC_OFFICE_001/error
masterhub/devices/PC_OFFICE_001/status
```

The Office client is Office-only. It is not a replacement for the existing browser/JioSaavn client. Use a separate device ID to keep that client available; one process must own each serial port. Integrating the two runtimes into a single broader client is separate from this Office delivery.

## Masterhub setup and operation

1. Restart Masterhub so it reloads the new mode/command mappings.
2. Register `PC_OFFICE_001` as a desktop PC with transport `mqtt` or `usb`/`uart`, then select it as the active target. For UART, connect Masterhub to its own end of the link at 115200 baud.
3. Open **Python / Desktop**, choose **Microsoft Office**, then choose **Microsoft Excel**, **Microsoft PowerPoint** or **Microsoft Word**. Phase 4 shows that application's internal commands. Selection alone does not open Office.
4. Choose Open/Create first, then the application's actions. Use disposable documents for initial acceptance testing.
5. Save with a filename, for example `demo.xlsx`, `demo.pptx` or `demo.docx`. Files are saved under the client user's `Documents/Masterhub` folder. Set `output_dir` in client configuration to change this root; remote commands cannot choose arbitrary directories or overwrite existing unrelated files.
6. Wait for an execution result. A sent command is PENDING; SUCCESS means the client reported completion. Missing confirmation is UNKNOWN, not success. Do not blindly retry an uncertain edit/delete.

In the Desktop menu, Left selects Microsoft Office and Left+Right selects Notepad. In the Office submenu (Phase 3), Push selects Excel, Pull selects PowerPoint and Right selects Word. Phase 4 contains internal commands: Push opens a managed document; Excel uses Pull for Sheet1, Left for Sheet2 and Right for Save; PowerPoint uses Pull for Title, Left for New Slide and Right for Save; Word uses Pull for Save. Additional Word edits remain available as manual controls. Back (Push+Right) returns one menu level and Home (Push+Left) returns to the main menu, without closing documents. Parameterized commands open a form when triggered by the dashboard keyboard; API/BCI callers must provide required parameters for find/replace and destructive edits.

Edit/delete actions require boolean `confirm: true`. Close refuses unsaved changes unless the user has saved or explicitly supplied `discard: true`. These flags are checkboxes in Masterhub's Office forms. Only owned documents are closed; the application itself is not quit.

Example request to Masterhub's existing command endpoint:

```json
{"command":"office_excel_open","target":"PC_OFFICE_001","params":{}}
```

Remote responses include `command_id`, `status: PENDING` and `result_url`. Query that relative URL to obtain the final result. The normal dashboard does this automatically. Result tracking is bounded/in-memory on Masterhub; a server restart loses pending UI correlation. Raw MQTT/UART events still follow the existing event logging path.

## Reliability and limits

- No Office application opens at client startup. Office calls run on one COM thread; serial reads and MQTT network/heartbeat processing remain separate.
- The client records command IDs before execution in a local SQLite journal. Same-ID retries do not repeat a completed operation, even across MQTT/UART and restarts. Interrupted commands require human reconciliation. New intentional actions require new IDs. Retained MQTT commands are rejected.
- Logs and duplicate journal live in `%LOCALAPPDATA%/MasterhubOffice/<device_id>`. Do not delete the journal to force retries without checking the document.
- A disconnected broker/cable cannot confirm execution. Restart/reconnect does not automatically replay unknown commands. A full client queue rejects further work rather than executing a delayed backlog indefinitely.
- Closing a managed document manually requires a client restart before a new session for that application. Restarting leaves existing documents open for the user; the client never adopts them automatically.
- Office dialogs can block COM. Communication stays responsive, but operations are serialized and a timeout cannot safely cancel Office. Resolve the dialog on the target PC; do not send repeated edits. No claim of unattended Windows-service support is made.
- MQTT status reports the client and supported action vocabulary, not a successful Office installation check. Actual open attempts report missing Office/COM errors.

## Build the single Office EXE

From the project root, on Windows x64:

```powershell
python -m pip install -r office_client/requirements-build.txt
python -m PyInstaller --noconfirm --clean --onefile --name MasterhubOfficeClient --paths . --hidden-import pythoncom --hidden-import pywintypes --hidden-import win32com.client --distpath dist/office-client --workpath artifacts/office-client-build --specpath artifacts office_client/launcher.py
```

Distribute `dist/office-client/MasterhubOfficeClient.exe` with a user-edited config. Python is bundled; Microsoft Office is not. This is an unsigned executable; test it on the actual target Windows PC before deployment.

## Verification

Run the isolated tests from the project root:

```powershell
python -m pytest office_client/tests -q
node --check static/masterhub.js
```

The focused tests mock COM, broker publishing and serial devices while exercising actual Masterhub routing and response parsing. They do not use the production database or send live commands. Physical serial wiring, real broker ACLs and actual Office document round trips still require acceptance testing on the client PC.
