@echo off
REM ============================================================
REM MasterHub PC Agent - start_agent.bat
REM Activates the virtual environment and starts the agent using
REM config\agent_config.json (device_id, COM port, etc. all come
REM from that file - nothing to edit in this script for normal use).
REM
REM Optional overrides, e.g.:
REM     start_agent.bat --device-id PC_002 --port COM7
REM     start_agent.bat --fake-serial          (no real hardware)
REM ============================================================

setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\activate.bat" (
    echo [ERROR] Virtual environment not found. Run install_agent.bat first.
    exit /b 1
)

call .venv\Scripts\activate.bat

if not exist "logs" mkdir logs

echo.
echo === Starting MasterHub PC Agent ===
echo Config: config\agent_config.json
echo Log file: logs\pc_agent.log ^(also printed below^)
echo Press Ctrl+C to stop.
echo.

python -m agent.pc_agent %*

endlocal
