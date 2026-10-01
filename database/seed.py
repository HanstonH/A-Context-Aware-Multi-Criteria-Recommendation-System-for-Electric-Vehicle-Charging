"""Build database/ev_charging.db from project CSVs and GitHub TDX snapshots.

Does not use Supabase. Requires Python 3.10+ (stdlib only).
"""
from __future__ import annotations

import csv
import hashlib
import json
import sqlite3
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB_DIR = Path(__file__).resolve().parent
DB_PATH = DB_DIR / "ev_charging.db"
SCHEMA_PATH = DB_DIR / "schema.sql"
STATIONS_CSV = ROOT / "AI" / "data" / "taiwan_ev_stations.csv"
PRICES_CSV = ROOT / "AI" / "data" / "unit_price_by_station_taiwan.csv"
MANIFEST_PATH = ROOT / "Simulation" / "charging_station_manifest.json"
RECS_CSV = ROOT / "AI" / "Algorithm" / "final_recommendations_summary.csv"

TDX_CITIES = (
    "Taipei", "NewTaipei", "Taoyuan", "Taichung", "Tainan", "Kaohsiung",
    "Keelung", "Hsinchu", "HsinchuCounty", "MiaoliCounty", "ChanghuaCounty",
    "NantouCounty", "YunlinCounty", "ChiayiCounty", "Chiayi", "PingtungCounty",
    "YilanCounty", "HualienCounty", "TaitungCounty", "KinmenCounty",
    "PenghuCounty",
)
TDX_SNAPSHOT_DATE = "2026-07-02"
TDX_RATE_BLOB = f"origin/main:static/raw/charging_rates/Taipei/{TDX_SNAPSHOT_DATE}.json"

DEMO_EMAIL = "demo@ev.local"
DEMO_PASSWORD = "demo123"


def _hash_password(password: str) -> str:
    salt = "ev-local-v1"
    digest = hashlib.sha256(f"{salt}:{password}".encode("utf-8")).hexdigest()
    return f"sha256${salt}${digest}"


def _git_show_json(spec: str) -> dict:
    raw = subprocess.check_output(["git", "show", spec], cwd=ROOT)
    return json.loads(raw.decode("utf-8"))


def _connect() -> sqlite3.Connection:
    if DB_PATH.exists():
        DB_PATH.unlink()
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    return conn


def seed_users(conn: sqlite3.Connection) -> int:
    cur = conn.execute(
        """
        INSERT INTO users (email, password_hash, name, phone)
        VALUES (?, ?, ?, ?)
        """,
        (DEMO_EMAIL, _hash_password(DEMO_PASSWORD), "Demo Driver", "0900000000"),
    )
    user_id = cur.lastrowid
    conn.execute(
        """
        INSERT INTO user_vehicles (user_id, label, capacity_kwh, wh_per_km)
        VALUES (?, ?, ?, ?)
        """,
        (user_id, "Default EV", 60.0, 180.0),
    )
    return user_id


def seed_project_stations(conn: sqlite3.Connection) -> None:
    manifest = {}
    if MANIFEST_PATH.is_file():
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    prices = {}
    if PRICES_CSV.is_file():
        with PRICES_CSV.open(encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                prices[row["Station Name"]] = row

    with STATIONS_CSV.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            station_id = row["MAC Address"]
            info = manifest.get(station_id, {})
            conn.execute(
                """
                INSERT INTO stations (
                    station_id, source, name, address, operator, plug_type,
                    latitude, longitude, city, sumo_cs_id, sumo_lane
                ) VALUES (?, 'project', ?, ?, ?, ?, ?, ?, 'Taipei', ?, ?)
                """,
                (
                    station_id,
                    row["Station Name"],
                    row.get("Address 1"),
                    row.get("Address 1"),
                    row.get("Plug Type"),
                    float(row["Latitude"]),
                    float(row["Longitude"]),
                    info.get("cs_id"),
                    info.get("lane"),
                ),
            )
            price = prices.get(row["Station Name"])
            if price:
                conn.execute(
                    """
                    INSERT INTO station_prices (
                        station_id, price_ntd_per_kwh, price_tier, source
                    ) VALUES (?, ?, ?, 'project')
                    """,
                    (
                        station_id,
                        float(price["median_unit_price_per_kwh"]),
                        float(price["price_tier"]),
                    ),
                )


def seed_tdx_stations(conn: sqlite3.Connection) -> int:
    count = 0
    for city in TDX_CITIES:
        spec = f"origin/main:static/raw/stations/{city}/{TDX_SNAPSHOT_DATE}.json"
        try:
            body = _git_show_json(spec)
        except (subprocess.CalledProcessError, json.JSONDecodeError) as exc:
            print(f"skip TDX stations {city}: {exc}")
            continue
        for station in body.get("Stations") or []:
            station_id = station.get("StationID")
            lat = station.get("PositionLat")
            lon = station.get("PositionLon")
            if not station_id or lat is None or lon is None:
                continue
            name = (station.get("StationName") or {}).get("Zh_tw")
            try:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO stations (
                        station_id, source, name, latitude, longitude, city,
                        spaces, charging_points
                    ) VALUES (?, 'tdx', ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        station_id,
                        name,
                        float(lat),
                        float(lon),
                        city,
                        station.get("Spaces"),
                        station.get("ChargingPoints"),
                    ),
                )
                if conn.execute("SELECT changes()").fetchone()[0]:
                    count += 1
            except sqlite3.IntegrityError:
                continue
    return count


def seed_tdx_parking(conn: sqlite3.Connection) -> int:
    count = 0
    parking_by_station: dict[str, list[float]] = {}
    for city in TDX_CITIES:
        spec = f"origin/main:static/raw/parking_rates/{city}/{TDX_SNAPSHOT_DATE}.json"
        try:
            body = _git_show_json(spec)
        except (subprocess.CalledProcessError, json.JSONDecodeError) as exc:
            print(f"skip TDX parking {city}: {exc}")
            continue
        fetched_at = body.get("UpdateTime")
        for record in body.get("ParkingRates") or []:
            station_id = record.get("StationID")
            for rate in record.get("Rates") or []:
                conn.execute(
                    """
                    INSERT INTO parking_rates (
                        station_id, city, rate_type, pricing_type, day_type,
                        rate_price, max_price, fetched_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        station_id,
                        city,
                        rate.get("RateType"),
                        rate.get("PricingType"),
                        rate.get("DayType"),
                        rate.get("RatePrice"),
                        rate.get("MaxPrice"),
                        fetched_at,
                    ),
                )
                count += 1
                price = rate.get("RatePrice")
                if station_id and price is not None:
                    parking_by_station.setdefault(station_id, []).append(float(price))

    for station_id, prices in parking_by_station.items():
        median = _median(prices)
        if median is None:
            continue
        exists = conn.execute(
            "SELECT 1 FROM stations WHERE station_id = ?", (station_id,)
        ).fetchone()
        if not exists:
            continue
        updated = conn.execute(
            """
            UPDATE station_prices
            SET parking_cost = ?
            WHERE station_id = ? AND source = 'tdx'
            """,
            (median, station_id),
        ).rowcount
        if not updated:
            conn.execute(
                """
                INSERT OR IGNORE INTO station_prices (
                    station_id, parking_cost, source
                ) VALUES (?, ?, 'tdx')
                """,
                (station_id, median),
            )
    return count


def seed_tdx_rates(conn: sqlite3.Connection) -> int:
    try:
        body = _git_show_json(TDX_RATE_BLOB)
    except (subprocess.CalledProcessError, json.JSONDecodeError) as exc:
        print(f"skip TDX rates: {exc}")
        return 0
    fetched_at = body.get("UpdateTime")
    count = 0
    for record in body.get("ChargingRates") or []:
        station_id = record.get("StationID")
        for rate in record.get("Rates") or []:
            conn.execute(
                """
                INSERT INTO charging_rates (
                    station_id, charging_point_id, connector_id, city,
                    rate_type, pricing_type, rate_price, peak,
                    start_time, end_time, fetched_at
                ) VALUES (?, ?, ?, 'Taipei', ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    station_id,
                    record.get("ChargingPointID"),
                    record.get("ConnectorID"),
                    rate.get("RateType"),
                    rate.get("PricingType"),
                    rate.get("RatePrice"),
                    rate.get("Peak"),
                    rate.get("StartTime"),
                    rate.get("EndTime"),
                    fetched_at,
                ),
            )
            count += 1
    return count


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    values = sorted(values)
    mid = len(values) // 2
    if len(values) % 2:
        return values[mid]
    return (values[mid - 1] + values[mid]) / 2


def seed_tdx_price_summary(conn: sqlite3.Connection) -> None:
    rows = conn.execute(
        """
        SELECT station_id, rate_type, rate_price
        FROM charging_rates
        WHERE station_id IS NOT NULL AND rate_price IS NOT NULL
        """
    ).fetchall()
    by_station: dict[str, list[tuple[int | None, float]]] = {}
    for station_id, rate_type, rate_price in rows:
        by_station.setdefault(station_id, []).append((rate_type, float(rate_price)))

    for station_id, items in by_station.items():
        exists = conn.execute(
            "SELECT 1 FROM stations WHERE station_id = ?", (station_id,)
        ).fetchone()
        if not exists:
            continue
        preferred = [p for t, p in items if t == 2]
        prices = preferred or [p for _, p in items]
        median = _median(prices)
        if median is None:
            continue
        conn.execute(
            """
            INSERT OR IGNORE INTO station_prices (
                station_id, price_ntd_per_kwh, source
            ) VALUES (?, ?, 'tdx')
            """,
            (station_id, median),
        )


def seed_recommendations(conn: sqlite3.Connection, user_id: int) -> None:
    if not RECS_CSV.is_file():
        return
    cur = conn.execute(
        """
        INSERT INTO recommendation_requests (
            user_id, latitude, longitude, battery_pct, city
        ) VALUES (?, 25.0330, 121.5654, 45, 'Taipei')
        """,
        (user_id,),
    )
    request_id = cur.lastrowid
    with RECS_CSV.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            conn.execute(
                """
                INSERT INTO recommendation_results (
                    request_id, station_id, station_name, latitude, longitude,
                    distance_m, waiting_time, poi_sum, cost, total_score,
                    rank, explanation
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    request_id,
                    row.get("MAC Address"),
                    row.get("Station Name"),
                    float(row["lat"]) if row.get("lat") else None,
                    float(row["lon"]) if row.get("lon") else None,
                    float(row["distance"]) if row.get("distance") else None,
                    float(row["waiting_time"]) if row.get("waiting_time") else None,
                    float(row["poi_sum"]) if row.get("poi_sum") else None,
                    float(row["cost"]) if row.get("cost") else None,
                    float(row["total_score"]) if row.get("total_score") else None,
                    int(float(row["rank"])) if row.get("rank") else None,
                    row.get("score_explanation"),
                ),
            )


def main() -> None:
    conn = _connect()
    try:
        user_id = seed_users(conn)
        seed_project_stations(conn)
        tdx_n = seed_tdx_stations(conn)
        parking_n = seed_tdx_parking(conn)
        rate_n = seed_tdx_rates(conn)
        seed_tdx_price_summary(conn)
        seed_recommendations(conn, user_id)
        conn.commit()
        counts = {
            table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in (
                "users",
                "user_vehicles",
                "stations",
                "station_prices",
                "charging_rates",
                "parking_rates",
                "recommendation_requests",
                "recommendation_results",
            )
        }
        print(f"Created {DB_PATH}")
        print(f"TDX stations inserted: {tdx_n}")
        print(f"TDX parking rows inserted: {parking_n}")
        print(f"TDX rate rows inserted: {rate_n}")
        for table, n in counts.items():
            print(f"  {table}: {n}")
        print(f"Demo login: {DEMO_EMAIL} / {DEMO_PASSWORD}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
