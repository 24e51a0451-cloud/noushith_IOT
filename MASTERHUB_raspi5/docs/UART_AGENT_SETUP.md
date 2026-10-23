# UART commands to agent_H

In the dashboard's Python / Desktop section, open **UART Configuration** and
connect the MasterHub-side serial port (COM14 in the supplied screenshot) at
115200 baud. Click **Register UART Node**, enter the agent's effective Device ID,
and register. Registration adds a selectable UART target and selects it for
subsequent Desktop and AI/ML commands. You can select another target later.
The UART dot indicates an open serial port, not a verified agent response.
Registration and serial connection are in memory; repeat after a server restart.

## Agent files

The agent root on this machine is `D:\GALATICX\agent_H\agent`.
Edit `.env` beside `start_agent.py` (recommended). The current file selects MQTT
and DEVICE_ID=PC_003. For a separate UART identity, use:

```dotenv
DEVICE_ID=PC_UART_001
MASTERHUB_TRANSPORT=usb
MASTERHUB_AGENT_PORT=COM4
MASTERHUB_AGENT_BAUDRATE=115200
```

COM4 is an example: replace it with the **agent-side** port. Register
PC_UART_001 in MasterHub, or keep PC_003 and register that ID with UART transport.
If MASTERHUB_AGENT_DEVICE_ID is set, it overrides DEVICE_ID.

Alternatively, edit `config/agent_config.json`: set `device_id`,
`transport.type` to `usb`, `transport.port` to the agent-side port, and
`transport.baudrate` to 115200. Existing `.env` and process environment settings
override JSON, so changing JSON alone while `.env` selects MQTT will not work.

Start from the agent root:

```powershell
.\start_agent.bat --check-config
.\start_agent.bat
```

For a one-run override (replace COM4):

```powershell
.\start_agent.bat --transport usb --port COM4 --baudrate 115200 --device-id PC_UART_001
```

No Python source edits are required. `config/loader.py` already loads these
settings; `agent/pc_agent.py` already opens pyserial and receives newline-delimited
MasterHub JSON commands. Avoid `register_and_start.py` for this setup: it starts
the MQTT path. Manual dashboard registration does not need register_url.

MasterHub and agent must use opposite endpoints of the serial connection.
On the same PC, they cannot both open COM14; use paired virtual serial ports
or a physical serial bridge with a port for each endpoint. Between PCs, each
uses its own adapter/port. Match baud rates at both ends.

After registration, confirm the active target is your UART ID, then try Notepad
Open. Check MasterHub TX, agent receive/action logs, and MasterHub RX for a reply.
A successful write alone does not confirm execution. The included simulated
routing tests do not verify the physical wiring or the running agent.
