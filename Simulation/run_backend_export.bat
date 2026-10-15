@echo off
REM Headless SUMO run — exports backend data to Simulation\output\
set SUMO_HOME=C:\Users\USER\Downloads\sumo-win64extra-1.26.0\sumo-1.26.0
set PATH=%SUMO_HOME%\bin;%PATH%
cd /d "%~dp0"

if not exist taipei.net.xml call build_taiwan_map.bat
if not exist charging_station_manifest.json python generate_charging_stations.py

python sumo_algorithm_traci.py --headless --telemetry-every 5
pause
