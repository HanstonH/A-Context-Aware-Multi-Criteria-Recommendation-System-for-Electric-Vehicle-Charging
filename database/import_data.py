"""Build local SQLite DB and import TDX GitHub dumps + SUMO CSVs."""
from __future__ import annotations

import csv
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SCHEMA = ROOT / "schema.sql"
DB_PATH = ROOT / "ev_charging.db"

SUMO_ROOT = ROOT.parent
TEAM_ROOT = Path(r"C:\Users\USER\Desktop\ev-charging-full")

STATIONS_DIR = TEAM_ROOT / "static" / "raw" / "stations"
RATES_DIR = TEAM_ROOT / "static" / "raw" / "charging_rates"
TAIWAN_CSV = SUMO_ROOT / "AI" / "data" / "taiwan_ev_stations.csv"
TELEMETRY_CSV = SUMO_ROOT / "Simulation" / "output" / "telemetry.csv"
RECS_CSV = SUMO_ROOT / "Simulation" / "output" / "recommendations.csv"


def _station_name(raw) -> str:
    if isinstance(raw, dict):
        return str(raw.get("Zh_tw") or raw.get("En") or next(iter(raw.values()), "") or "")
    return str(raw or "")


def _latest_json(city_dir: Path) -> Path | None:
    files = sorted(city_dir.glob("*.json"))
    return files[-1] if files else None


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA.read_text(encoding="utf-8"))
    return conn


def import_tdx_stations(conn: sqlite3.Connection) -> int:
    if not STATIONS_DIR.is_dir():
        print(f"Skip TDX stations — missing {STATIONS_DIR}")
        return 0
    n = 0
    for city_dir in sorted(p for p in STATIONS_DIR.iterdir() if p.is_dir()):
        path = _latest_json(city_dir)
        if path is None:
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        city = city_dir.name
        updated = payload.get("UpdateTime")
        for st in payload.get("Stations") or []:
            sid = st.get("StationID")
            lat, lon = st.get("PositionLat"), st.get("PositionLon")
            if not sid or lat is None or lon is None:
                continue
            loc = ((st.get("Location") or {}).get("Place") or {})
            conn.execute(
                """
                INSERT OR REPLACE INTO stations (
                  station_id, source, city, station_name, description, operator_id,
                  lat, lon, spaces, charging_points, service_time, address,
                  telephone, plug_type, updated_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    sid,
                    "tdx",
                    city,
                    _station_name(st.get("StationName")),
                    st.get("Description"),
                    st.get("OperatorID"),
                    float(lat),
                    float(lon),
                    st.get("Spaces"),
                    st.get("ChargingPoints"),
                    st.get("ServiceTime"),
                    loc.get("POI"),
                    st.get("Telephone"),
                    None,
                    updated,
                ),
            )
            conn.execute("DELETE FROM station_connectors WHERE station_id = ?", (sid,))
            for c in st.get("Connectors") or []:
                conn.execute(
                    """
                    INSERT INTO station_connectors (station_id, type, power, quantity)
                    VALUES (?,?,?,?)
                    """,
                    (sid, c.get("Type"), c.get("Power"), c.get("Quantity")),
                )
            n += 1
        print(f"  stations {city}: {path.name}")
    return n


def import_tdx_rates(conn: sqlite3.Connection) -> int:
    if not RATES_DIR.is_dir():
        print(f"Skip charging rates — missing {RATES_DIR}")
        return 0
    conn.execute("DELETE FROM charging_rates")
    n = 0
    for city_dir in sorted(p for p in RATES_DIR.iterdir() if p.is_dir()):
        path = _latest_json(city_dir)
        if path is None:
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        for row in payload.get("ChargingRates") or []:
            sid = row.get("StationID")
            if not sid:
                continue
            for rate in row.get("Rates") or []:
                conn.execute(
                    """
                    INSERT INTO charging_rates (
                      station_id, charging_point_id, connector_id,
                      rate_type, pricing_type, rate_price, peak, start_time, end_time
                    ) VALUES (?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        sid,
                        row.get("ChargingPointID"),
                        row.get("ConnectorID"),
                        rate.get("RateType"),
                        rate.get("PricingType"),
                        rate.get("RatePrice"),
                        rate.get("Peak"),
                        rate.get("StartTime"),
                        rate.get("EndTime"),
                    ),
                )
                n += 1
        print(f"  rates {city_dir.name}: {path.name}")
    return n


def import_sumo_stations(conn: sqlite3.Connection) -> int:
    if not TAIWAN_CSV.is_file():
        print(f"Skip SUMO stations — missing {TAIWAN_CSV}")
        return 0
    n = 0
    with TAIWAN_CSV.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            sid = str(row.get("MAC Address") or "").strip()
            if not sid:
                continue
            conn.execute(
                """
                INSERT OR REPLACE INTO stations (
                  station_id, source, city, station_name, description, operator_id,
                  lat, lon, spaces, charging_points, service_time, address,
                  telephone, plug_type, updated_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    sid,
                    "sumo",
                    "Taipei",
                    row.get("Station Name"),
                    None,
                    None,
                    float(row["Latitude"]),
                    float(row["Longitude"]),
                    None,
                    None,
                    None,
                    row.get("Address 1"),
                    None,
                    row.get("Plug Type"),
                    None,
                ),
            )
            n += 1
    print(f"  SUMO stations: {n}")
    return n


def import_telemetry(conn: sqlite3.Connection) -> int:
    if not TELEMETRY_CSV.is_file():
        print(f"Skip telemetry — missing {TELEMETRY_CSV}")
        return 0
    conn.execute("DELETE FROM telemetry")
    n = 0
    with TELEMETRY_CSV.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            conn.execute(
                """
                INSERT INTO telemetry (
                  time_s, vehicle_id, lat, lon, speed_mps, remaining_wh, max_wh,
                  soc_percent, charging, charging_station_id,
                  total_energy_consumed_wh, energy_charged_wh, distance_m, is_tracked
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    row.get("time_s"),
                    row.get("vehicle_id"),
                    row.get("lat"),
                    row.get("lon"),
                    row.get("speed_mps"),
                    row.get("remaining_wh"),
                    row.get("max_wh"),
                    row.get("soc_percent"),
                    row.get("charging"),
                    row.get("charging_station_id") or None,
                    row.get("total_energy_consumed_wh"),
                    row.get("energy_charged_wh"),
                    row.get("distance_m"),
                    row.get("is_tracked"),
                ),
            )
            n += 1
    print(f"  telemetry rows: {n}")
    return n


def import_recommendations(conn: sqlite3.Connection) -> int:
    if not RECS_CSV.is_file():
        print(f"Skip recommendations — missing {RECS_CSV}")
        return 0
    conn.execute("DELETE FROM recommendation_logs")
    n = 0
    with RECS_CSV.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            conn.execute(
                """
                INSERT INTO recommendation_logs (
                  mac_address, station_name, lat, lon, distance_m,
                  waiting_time_s, cost, total_score, rank
                ) VALUES (?,?,?,?,?,?,?,?,?)
                """,
                (
                    row.get("MAC Address"),
                    row.get("Station Name"),
                    row.get("lat"),
                    row.get("lon"),
                    row.get("distance"),
                    row.get("waiting_time"),
                    row.get("cost"),
                    row.get("total_score"),
                    row.get("rank"),
                ),
            )
            n += 1
    print(f"  recommendation rows: {n}")
    return n


def main() -> None:
    print(f"Database: {DB_PATH}")
    conn = connect()
    try:
        print("Importing TDX stations...")
        n_st = import_tdx_stations(conn)
        print("Importing TDX charging rates...")
        n_rate = import_tdx_rates(conn)
        print("Importing SUMO stations...")
        n_sumo = import_sumo_stations(conn)
        print("Importing SUMO telemetry...")
        n_tel = import_telemetry(conn)
        print("Importing SUMO recommendations...")
        n_rec = import_recommendations(conn)
        conn.commit()
        print("\nDone.")
        print(f"  stations (tdx+sumo writes): {n_st} + {n_sumo}")
        print(f"  charging_rates: {n_rate}")
        print(f"  telemetry: {n_tel}")
        print(f"  recommendation_logs: {n_rec}")
        for table in (
            "stations",
            "station_connectors",
            "charging_rates",
            "telemetry",
            "recommendation_logs",
        ):
            count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            print(f"  {table}: {count} rows")
    finally:
        conn.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Import failed: {exc}", file=sys.stderr)
        raise
