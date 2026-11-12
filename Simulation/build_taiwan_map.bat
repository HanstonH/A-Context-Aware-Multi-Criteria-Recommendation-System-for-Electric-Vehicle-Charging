@echo off
REM Build Taipei metro SUMO network + EV routes + charging POIs
set SUMO_HOME=C:\Users\USER\Downloads\sumo-win64extra-1.26.0\sumo-1.26.0
set PATH=%SUMO_HOME%\bin;%PATH%

cd /d "%~dp0"

echo [0/5] Prepare Taiwan station CSV from geojson ...
python "..\AI\data\prepare_taiwan_stations.py"
if errorlevel 1 exit /b 1

echo [1/5] Build taipei.net.xml (OSM or offline grid) ...
python build_taipei_network.py
if errorlevel 1 exit /b 1
echo [2/5] randomTrips EV routes (1 hour, downtown-biased) ...
python -c "from sim_config import TRIP_END_S,TRIP_PERIOD_S,TRIP_FRINGE_FACTOR,TRIP_MIN_DISTANCE_M; print(f'  end={TRIP_END_S}s period={TRIP_PERIOD_S}s fringe={TRIP_FRINGE_FACTOR} min_dist={TRIP_MIN_DISTANCE_M}m')"
python -c "import os,subprocess,sys; from pathlib import Path; from sim_config import TRIP_END_S,TRIP_PERIOD_S,TRIP_FRINGE_FACTOR,TRIP_MIN_DISTANCE_M; sh=os.environ.get('SUMO_HOME',r'C:\Users\USER\Downloads\sumo-win64extra-1.26.0\sumo-1.26.0'); rt=Path(sh)/'tools'/'randomTrips.py'; subprocess.run([sys.executable,str(rt),'-n','taipei.net.xml','-r','taipei_more.rou.xml','-e',str(TRIP_END_S),'-p',str(TRIP_PERIOD_S),'--vehicle-class','passenger','--prefix','EV','--fringe-factor',str(TRIP_FRINGE_FACTOR),'--min-distance',str(TRIP_MIN_DISTANCE_M),'--min-success-rate','0.5','--validate'],check=True)"
python patch_taiwan_routes.py

echo [3/5] charging_stations.add.xml ...
python generate_charging_stations.py

echo [4/5] Done — open SUMO with open_sumo_taiwan.bat or simulation.sumocfg
pause
