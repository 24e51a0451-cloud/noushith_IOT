@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Run install_agent.bat once on this laptop first.
    exit /b 1
)
".venv\Scripts\python.exe" -c "import dotenv, websocket" >nul 2>nul
if errorlevel 1 (
    echo Installing updated agent dependencies...
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
    if errorlevel 1 exit /b 1
)
".venv\Scripts\python.exe" start_agent.py %*
exit /b %errorlevel%
