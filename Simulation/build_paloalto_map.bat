@echo off
REM Regenerate Palo Alto SUMO network from OpenStreetMap (map.osm)
set SUMO_HOME=C:\Users\USER\Downloads\sumo-win64extra-1.26.0\sumo-1.26.0
set PATH=%SUMO_HOME%\bin;%PATH%

cd /d "%~dp0"

echo [1/2] Converting map.osm to paloalto.net.xml ...
netconvert --osm-files map.osm -o paloalto.net.xml --proj.utm

echo [2/2] Generating EV routes (600s, ~60 vehicles every 10s) ...
python "%SUMO_HOME%\tools\randomTrips.py" -n paloalto.net.xml -r paloalto_more.rou.xml -e 600 -p 10 --vehicle-class passenger --prefix EV --fringe-factor 5 --validate
python patch_paloalto_routes.py

echo Done. Open simulation.sumocfg in sumo-gui to view Palo Alto map.
