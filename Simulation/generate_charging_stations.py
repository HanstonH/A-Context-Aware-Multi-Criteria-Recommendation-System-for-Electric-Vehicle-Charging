"""Generate charging_stations.add.xml — Taiwan POIs + SUMO chargingStation elements."""
from __future__ import annotations

import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import sumolib

_SIM_DIR = Path(__file__).resolve().parent
_AI_DATA = _SIM_DIR.parent / "AI" / "data"
_ALGO_DIR = _SIM_DIR.parent / "AI" / "Algorithm"
if str(_ALGO_DIR) not in sys.path:
    sys.path.insert(0, str(_ALGO_DIR))

from config import REGION_BOUNDS  # noqa: E402

_NET = _SIM_DIR / "taipei.net.xml"
_OUT = _SIM_DIR / "charging_stations.add.xml"
_MANIFEST = _SIM_DIR / "charging_station_manifest.json"
_CSV = _AI_DATA / "taiwan_ev_stations.csv"

# 150 kW DC fast charger (Watts) — SUMO uses power * efficiency * time for energy transfer
CHARGE_POWER_W = 150_000
CHARGE_EFFICIENCY = 0.9
CHARGE_SPAN_M = 12.0
# POI marker size on SUMO map (metres) — default is ~1m, too small to see
POI_WIDTH_M = 60.0
POI_HEIGHT_M = 60.0


def _in_bounds(lat: float, lon: float) -> bool:
    b = REGION_BOUNDS
    return b["lat_min"] <= lat <= b["lat_max"] and b["lon_min"] <= lon <= b["lon_max"]


def _lane_ok_for_ev_stop(lane: sumolib.net.lane.Lane) -> bool:
    """Passenger EV must be allowed to drive and stop on this lane."""
    edge = lane.getEdge()
    if edge.isSpecial():
        return False
    if not lane.allows("passenger"):
        return False
    if lane.getLength() < 8.0:
        return False
    return True


def _nearest_lane(net: sumolib.net.Net, x: float, y: float) -> tuple[str, float] | None:
    candidates: list[tuple[float, str, float]] = []
    for radius in (80, 150, 300, 500, 800, 1200, 2000, 3000):
        for edge, dist in net.getNeighboringEdges(x, y, radius):
            if edge.isSpecial():
                continue
            for lane in edge.getLanes():
                if not _lane_ok_for_ev_stop(lane):
                    continue
                candidates.append((dist, lane.getID(), lane.getLength()))
        if candidates:
            break
    if not candidates:
        return None
    _dist, lane_id, lane_len = min(candidates, key=lambda item: item[0])
    return lane_id, lane_len


def main() -> None:
    import pandas as pd

    if not _CSV.is_file():
        raise FileNotFoundError(
            f"Taiwan station CSV not found: {_CSV}\n"
            f"Run: python {_AI_DATA / 'prepare_taiwan_stations.py'}"
        )
    if not _NET.is_file():
        raise FileNotFoundError(
            f"SUMO network not found: {_NET}\nRun: Simulation\\build_taiwan_map.bat"
        )

    net = sumolib.net.readNet(str(_NET))
    df = pd.read_csv(
        _CSV,
        usecols=["Station Name", "MAC Address", "Latitude", "Longitude"],
    )
    df = df.dropna(subset=["Latitude", "Longitude", "MAC Address"])
    df = df[df.apply(lambda r: _in_bounds(float(r["Latitude"]), float(r["Longitude"])), axis=1)]
    df = df.drop_duplicates("MAC Address", keep="first")

    root = ET.Element(
        "additional",
        {
            "xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance",
            "xsi:noNamespaceSchemaLocation": "http://sumo.dlr.de/xsd/additional_file.xsd",
        },
    )

    manifest: dict[str, dict] = {}
    poi_count = 0
    cs_count = 0

    for idx, row in df.iterrows():
        lon, lat = float(row["Longitude"]), float(row["Latitude"])
        try:
            x, y = net.convertLonLat2XY(lon, lat)
        except Exception:
            continue
        mac = str(row["MAC Address"]).replace(":", "").replace(" ", "")[:20]
        name = str(row["Station Name"])[:60]

        ET.SubElement(
            root,
            "poi",
            {
                "id": f"chg_{mac}_{idx}",
                "x": f"{x:.2f}",
                "y": f"{y:.2f}",
                "color": "0,200,80,255",
                "type": "charging_station",
                "layer": "202",
                "width": f"{POI_WIDTH_M:.1f}",
                "height": f"{POI_HEIGHT_M:.1f}",
            },
        )
        poi_count += 1

        lane_info = _nearest_lane(net, x, y)
        if lane_info is None:
            continue
        lane_id, lane_len = lane_info
        if lane_len < 8.0:
            continue

        span = min(CHARGE_SPAN_M, max(6.0, lane_len - 2.0))
        start_pos = max(0.5, (lane_len - span) / 2.0)
        end_pos = min(lane_len - 0.5, start_pos + span)
        cs_id = f"cs_{mac}"

        ET.SubElement(
            root,
            "chargingStation",
            {
                "id": cs_id,
                "lane": lane_id,
                "startPos": f"{start_pos:.2f}",
                "endPos": f"{end_pos:.2f}",
                "power": str(CHARGE_POWER_W),
                "efficiency": str(CHARGE_EFFICIENCY),
                "chargeInTransit": "false",
            },
        )
        cs_count += 1
        manifest[mac] = {
            "cs_id": cs_id,
            "lane": lane_id,
            "station_name": name,
            "lat": lat,
            "lon": lon,
        }

    tree = ET.ElementTree(root)
    ET.indent(tree, space="    ")
    tree.write(_OUT, encoding="UTF-8", xml_declaration=True)
    _MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {poi_count} POIs + {cs_count} chargingStation elements -> {_OUT}")
    print(f"Manifest: {_MANIFEST}")


if __name__ == "__main__":
    main()
