@echo off
REM Hourly live connector status extraction (run via Windows Task Scheduler).
setlocal
cd /d "%~dp0.."
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -m extraction live
) else (
    python -m extraction live
)
exit /b %ERRORLEVEL%
