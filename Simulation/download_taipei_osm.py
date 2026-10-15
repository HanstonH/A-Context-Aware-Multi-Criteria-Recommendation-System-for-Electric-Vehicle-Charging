"""Download highway OSM for Taipei metro via Overpass (with validation)."""
from __future__ import annotations

import sys
from pathlib import Path

import requests

SIM_DIR = Path(__file__).resolve().parent
QUERY_FILE = SIM_DIR / "overpass_taipei_highways.txt"
OUT = SIM_DIR / "map_taipei.osm"

OVERPASS_URLS = [
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass-api.de/api/interpreter",
]


def main() -> None:
    query = QUERY_FILE.read_text(encoding="utf-8")
    last_err = None
    for url in OVERPASS_URLS:
        print(f"Downloading from {url} ...")
        try:
            resp = requests.post(url, data={"data": query}, timeout=600)
            resp.raise_for_status()
            text = resp.text
            if "</osm>" not in text:
                raise ValueError("Response missing </osm> — incomplete download")
            OUT.write_text(text, encoding="utf-8")
            print(f"Wrote {OUT} ({len(text) // 1024} KB)")
            return
        except Exception as exc:
            print(f"  failed: {exc}")
            last_err = exc
    raise SystemExit(last_err)


if __name__ == "__main__":
    main()
