"""Apply EV battery vType to randomTrips output and write taipei.rou.xml."""
import re
from pathlib import Path

SRC = Path("taipei_more.rou.xml")
DST = Path("taipei.rou.xml")

VTYPE = """    <vType id="EV_Car" vClass="passenger" accel="2.6" decel="4.5" sigma="0.5" length="5" minGap="2.5" maxSpeed="33.33" carFollowModel="IDM">
        <param key="has.battery.device" value="true"/>
        <param key="device.battery.capacity" value="60000"/>
        <param key="device.battery.chargeLevel" value="5000"/>
        <param key="stoppingPowerConsumption" value="500"/>
    </vType>"""

if not SRC.is_file():
    raise SystemExit(f"Missing {SRC} — run build_taiwan_map.bat first.")

text = SRC.read_text(encoding="utf-8")
text = re.sub(r'    <vType id="EV_passenger" vClass="passenger"/>', VTYPE, text)
text = text.replace('type="EV_passenger"', 'type="EV_Car"')
text = text.replace('id="EV0"', 'id="MCU_EV_TEST_01"', 1)
DST.write_text(text, encoding="utf-8")
print(f"Wrote {DST} with {text.count('<vehicle id=')} vehicles")
