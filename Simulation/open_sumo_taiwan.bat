@echo off
REM Taiwan SUMO: auto-track orange EV + real charging + recommendations
set SUMO_HOME=C:\Users\USER\Downloads\sumo-win64extra-1.26.0\sumo-1.26.0
set PATH=%SUMO_HOME%\bin;%PATH%
cd /d "%~dp0"

if not exist taipei.net.xml (
    echo Building Taiwan map first...
    call build_taiwan_map.bat
)

python ..\AI\data\prepare_taiwan_stations.py
python generate_charging_stations.py

python ensure_routes.py
python sumo_algorithm_traci.py
