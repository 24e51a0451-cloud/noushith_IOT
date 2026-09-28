@echo off
setlocal
cd /d "%~dp0"
echo Starting this laptop as PC_001 over MQTT.
echo Stop any other agent process on this laptop before starting.
call start_agent.bat --device-id PC_001 --transport mqtt --mqtt-client-id masterhub-agent-PC_001 %*
endlocal
