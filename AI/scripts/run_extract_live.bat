@echo off
REM Hourly live connector status extraction (run via Windows Task Scheduler).
setlocal
cd /d "%~dp0.."
set "LOCAL_LOG=%~dp0..\.extraction_state\scheduler.log"
if not exist "%~dp0..\.extraction_state" mkdir "%~dp0..\.extraction_state"

echo [%DATE% %TIME%] START live extract>> "%LOCAL_LOG%"

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -m extraction live >> "%LOCAL_LOG%" 2>&1
) else (
    python -m extraction live >> "%LOCAL_LOG%" 2>&1
)
set ERR=%ERRORLEVEL%
echo [%DATE% %TIME%] END exit=%ERR%>> "%LOCAL_LOG%"
exit /b %ERR%
