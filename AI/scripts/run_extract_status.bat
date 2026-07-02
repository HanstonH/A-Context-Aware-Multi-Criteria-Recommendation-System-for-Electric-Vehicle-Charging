@echo off
REM Show extraction progress (manifest + checkpoint).
setlocal
cd /d "%~dp0.."
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -m extraction status
) else (
    python -m extraction status
)
pause
