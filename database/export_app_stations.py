"""Write the phone app's built-in station list (app/assets/stations.json) from the database.

The app bundles this file so the map works offline. Regenerate it whenever
database/ev_charging.db changes, so the app and the backend show the same stations:

    python database/export_app_stations.py           # rewrite the file
    python database/export_app_stations.py --check   # exit 1 if it is out of date

Standard library only.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "database" / "ev_charging.db"
OUT_PATH = ROOT / "app" / "assets" / "stations.json"


def load_stations(db_path: Path = DB_PATH) -> list[dict]:
    conn = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True)
    try:
        rows = conn.execute(
            "SELECT station_id, name, latitude, longitude, city, source FROM stations ORDER BY id"
        ).fetchall()
    finally:
        conn.close()
    return [
        {"id": sid, "name": name, "lat": lat, "lng": lng, "city": city, "source": source}
        for sid, name, lat, lng, city, source in rows
        if sid and lat is not None and lng is not None
    ]


def render(stations: list[dict]) -> str:
    """One station per line, like the original file, so diffs stay readable."""
    lines = [json.dumps(s, ensure_ascii=False, separators=(",", ":")) for s in stations]
    return "[" + ",\n".join(lines) + "]\n"


def main(argv: list[str]) -> int:
    stations = load_stations()
    if "--check" in argv:
        # utf-8-sig: the original file was written with a byte-order mark.
        current = json.loads(OUT_PATH.read_text(encoding="utf-8-sig")) if OUT_PATH.is_file() else None
        if current == stations:
            print(f"{OUT_PATH.relative_to(ROOT)} is up to date ({len(stations)} stations).")
            return 0
        print(f"{OUT_PATH.relative_to(ROOT)} is out of date; run without --check to regenerate.")
        return 1
    OUT_PATH.write_text(render(stations), encoding="utf-8")
    print(f"Wrote {len(stations)} stations to {OUT_PATH.relative_to(ROOT)}.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
