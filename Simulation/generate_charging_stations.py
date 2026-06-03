"""Generate charging_stations.add.xml — Palo Alto chargers on the SUMO map."""
from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

import sumolib

_SIM_DIR = Path(__file__).resolve().parent
_AI_DATA = _SIM_DIR.parent / "AI" / "data"
_NET = _SIM_DIR / "paloalto.net.xml"
_OUT = _SIM_DIR / "charging_stations.add.xml"
_CSV = _AI_DATA / "ChargePointData2011-2020-ManullyPreCleaned3.csv"

PALO_ALTO_BOUNDS = {
    "lat_min": 37.3685,
    "lat_max": 37.4725,
    "lon_min": -122.1900,
    "lon_max": -122.0950,
}


def _in_bounds(lat: float, lon: float) -> bool:
    b = PALO_ALTO_BOUNDS
    return b["lat_min"] <= lat <= b["lat_max"] and b["lon_min"] <= lon <= b["lon_max"]


def main() -> None:
    import pandas as pd

    if not _CSV.is_file():
        raise FileNotFoundError(f"ChargePoint CSV not found: {_CSV}")

    net = sumolib.net.readNet(str(_NET))
    df = pd.read_csv(
        _CSV,
        usecols=["Station Name", "MAC Address", "Latitude", "Longitude"],
        low_memory=False,
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

    for idx, row in df.iterrows():
        lon, lat = float(row["Longitude"]), float(row["Latitude"])
        x, y = net.convertLonLat2XY(lon, lat)
        mac = str(row["MAC Address"]).replace(":", "").replace(" ", "")[:20]
        name = str(row["Station Name"])[:60]
        ET.SubElement(
            root,
            "poi",
            {
                "id": f"chg_{mac}_{idx}",
                "x": f"{x:.2f}",
                "y": f"{y:.2f}",
                "color": "0,160,0",
                "type": "charging_station",
                "layer": "202",
            },
        )
        # SUMO poi doesn't support free text attrs in all versions; name in id is enough for GUI

    tree = ET.ElementTree(root)
    ET.indent(tree, space="    ")
    tree.write(_OUT, encoding="UTF-8", xml_declaration=True)
    print(f"Wrote {len(df)} charging POIs to {_OUT}")


if __name__ == "__main__":
    main()
