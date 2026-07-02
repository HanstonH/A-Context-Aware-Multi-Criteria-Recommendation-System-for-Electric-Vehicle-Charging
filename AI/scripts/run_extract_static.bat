@echo off
REM One-time (or weekly) static TDX extraction: stations + rates.
setlocal
cd /d "%~dp0.."
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -m extraction static
) else (
    python -m extraction static
)
exit /b %ERRORLEVEL%
