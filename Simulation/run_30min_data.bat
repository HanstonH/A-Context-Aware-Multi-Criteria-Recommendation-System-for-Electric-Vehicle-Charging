@echo off
REM 30-minute headless run — max telemetry for backend (Simulation\output\)
set SUMO_HOME=C:\Users\USER\Downloads\sumo-win64extra-1.26.0\sumo-1.26.0
set PATH=%SUMO_HOME%\bin;%PATH%
cd /d "%~dp0"

if not exist taipei.net.xml call build_taiwan_map.bat
if not exist charging_station_manifest.json python generate_charging_stations.py

python ..\AI\data\prepare_taiwan_stations.py
python generate_charging_stations.py
python ensure_routes.py
echo Sim duration: 3600s (1 hour), 150 kW fast charge, telemetry every 3 steps
python sumo_algorithm_traci.py --headless --telemetry-every 3
pause
