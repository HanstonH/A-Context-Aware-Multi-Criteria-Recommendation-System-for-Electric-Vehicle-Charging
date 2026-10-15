"""Build taipei.net.xml: try OSM download, else offline georeferenced grid."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import requests

SIM_DIR = Path(__file__).resolve().parent
OUT = SIM_DIR / "map_taipei.osm"
NET = SIM_DIR / "taipei.net.xml"
SUMO_HOME = Path(r"C:\Users\USER\Downloads\sumo-win64extra-1.26.0\sumo-1.26.0")

BBOX_QUERIES = [
    ("taipei_metro", 24.98, 121.48, 25.08, 121.60),
    ("taipei_core", 25.03, 121.54, 25.05, 121.56),
]
OVERPASS_URLS = [
    "https://lz4.overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]
HEADERS = {"User-Agent": "MCU_EV_Project_V2/1.0 (SUMO simulation)"}


def _query(min_lat: float, min_lon: float, max_lat: float, max_lon: float) -> str:
    return f"""[out:xml][timeout:120];
(
  way["highway"]({min_lat},{min_lon},{max_lat},{max_lon});
);
(._;>;);
out body;
"""


def download_osm() -> bool:
    for name, min_lat, min_lon, max_lat, max_lon in BBOX_QUERIES:
        query = _query(min_lat, min_lon, max_lat, max_lon)
        for url in OVERPASS_URLS:
            print(f"Trying {name} via {url} ...")
            try:
                resp = requests.post(
                    url,
                    data={"data": query},
                    headers=HEADERS,
                    timeout=120,
                )
                if not resp.ok:
                    print(f"  HTTP {resp.status_code}")
                    continue
                text = resp.text
                if "</osm>" not in text:
                    print("  incomplete XML")
                    continue
                OUT.write_text(text, encoding="utf-8")
                print(f"  OK — {len(text) // 1024} KB")
                return True
            except Exception as exc:
                print(f"  {exc}")
    return False


def netconvert_osm() -> None:
    subprocess.run(
        [
            str(SUMO_HOME / "bin" / "netconvert.exe"),
            "--osm-files",
            str(OUT),
            "-o",
            str(NET),
            "--proj.utm",
            "--geometry.remove",
            "--ramps.guess",
            "--junctions.join",
            "--tls.guess-signals",
            "--tls.discard-simple",
            "--tls.default-type",
            "actuated",
        ],
        check=True,
        cwd=SIM_DIR,
    )


def netgenerate_grid() -> None:
    print("Building offline grid network (georeferenced to Taipei center) ...")
    subprocess.run(
        [
            str(SUMO_HOME / "bin" / "netgenerate.exe"),
            "--grid",
            "--grid.x-number",
            "24",
            "--grid.y-number",
            "24",
            "--grid.length",
            "350",
            "--default.lanenumber",
            "2",
            "--default.speed",
            "13.89",
            "--output-file",
            str(NET),
        ],
        check=True,
        cwd=SIM_DIR,
    )
    subprocess.run([sys.executable, str(SIM_DIR / "georef_grid_net.py"), str(NET)], check=True)


def main() -> None:
    if download_osm():
        print("Converting OSM -> taipei.net.xml ...")
        netconvert_osm()
    else:
        netgenerate_grid()
    print(f"Ready: {NET}")


if __name__ == "__main__":
    main()
