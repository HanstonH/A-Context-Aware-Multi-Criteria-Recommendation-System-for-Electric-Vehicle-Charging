"""Read-only access to database/ev_charging.db.

Stations and their summary prices are loaded into memory once (about 3,000 rows);
rate tables are queried on demand for station details.
"""

from __future__ import annotations

import sqlite3
import statistics
from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path

from . import config
from .geo import City, city_label, haversine_km

# TDX RateType 2 is treated as NT$/kWh, the same choice database/seed.py makes.
RATE_TYPE_PER_KWH = 2


@dataclass
class Station:
    id: str
    name: str | None
    lat: float
    lng: float
    city: str | None
    source: str
    address: str | None
    operator: str | None
    plug_type: str | None
    spaces: int | None
    charging_points: int | None
    price_ntd_per_kwh: float | None
    parking_cost: float | None

    def brief(self, from_lat: float | None = None, from_lng: float | None = None, lang: str = "en") -> dict:
        """Compact form for the app and for Gemini tool results."""
        out = {
            "id": self.id,
            "name": self.name or self.id,
            "city": self.city,
            "city_name": city_label(self.city, lang),
            "lat": self.lat,
            "lng": self.lng,
            "source": self.source,
            "price_ntd_per_kwh": self.price_ntd_per_kwh,
        }
        if from_lat is not None and from_lng is not None:
            out["km"] = round(haversine_km(from_lat, from_lng, self.lat, self.lng), 2)
        return out


def _connect(path: Path) -> sqlite3.Connection:
    if not path.is_file():
        raise FileNotFoundError(f"Station database not found: {path}")
    conn = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


class StationStore:
    def __init__(self, path: Path = config.DB_PATH):
        self.path = path
        conn = _connect(path)
        try:
            self.stations = self._load(conn)
        finally:
            conn.close()
        self.by_id = {s.id: s for s in self.stations}

    @staticmethod
    def _load(conn: sqlite3.Connection) -> list[Station]:
        kwh_rates: dict[str, list[float]] = {}
        for row in conn.execute(
            "SELECT station_id, rate_price FROM charging_rates "
            "WHERE rate_type = ? AND rate_price IS NOT NULL",
            (RATE_TYPE_PER_KWH,),
        ):
            kwh_rates.setdefault(row["station_id"], []).append(float(row["rate_price"]))

        prices: dict[str, dict] = {}
        for row in conn.execute(
            "SELECT station_id, price_ntd_per_kwh, parking_cost FROM station_prices"
        ):
            entry = prices.setdefault(row["station_id"], {"kwh": None, "parking": None})
            if row["price_ntd_per_kwh"] is not None:
                entry["kwh"] = float(row["price_ntd_per_kwh"])
            if row["parking_cost"] is not None:
                entry["parking"] = float(row["parking_cost"])

        out: list[Station] = []
        for row in conn.execute("SELECT * FROM stations"):
            sid = row["station_id"]
            p = prices.get(sid, {})
            kwh = p.get("kwh")
            if kwh is None and sid in kwh_rates:
                kwh = statistics.median(kwh_rates[sid])
            out.append(
                Station(
                    id=sid,
                    name=row["name"],
                    lat=float(row["latitude"]),
                    lng=float(row["longitude"]),
                    city=row["city"],
                    source=row["source"],
                    address=row["address"],
                    operator=row["operator"],
                    plug_type=row["plug_type"],
                    spaces=row["spaces"],
                    charging_points=row["charging_points"],
                    price_ntd_per_kwh=round(kwh, 2) if kwh is not None else None,
                    parking_cost=p.get("parking"),
                )
            )
        return out

    # ── Queries ──────────────────────────────────────────────────────────────

    def get(self, station_id: str) -> Station | None:
        return self.by_id.get(station_id)

    def nearest(
        self,
        lat: float,
        lng: float,
        *,
        radius_km: float | None = None,
        city: City | None = None,
        limit: int | None = None,
    ) -> list[tuple[Station, float]]:
        """Stations sorted by straight-line distance, as (station, km) pairs."""
        rows = []
        for s in self.stations:
            if city and s.city != city.code:
                continue
            km = haversine_km(lat, lng, s.lat, s.lng)
            if radius_km is not None and km > radius_km:
                continue
            rows.append((s, km))
        rows.sort(key=lambda x: x[1])
        return rows[:limit] if limit else rows

    def search(self, query: str, *, city: City | None = None) -> list[Station]:
        needle = _fold(query)
        if len(needle) < 1:
            return []
        return [
            s
            for s in self.stations
            if (not city or s.city == city.code) and needle in _fold(s.name or "")
        ]

    def city_counts(self) -> dict[str, dict]:
        counts: dict[str, dict] = {}
        for s in self.stations:
            c = counts.setdefault(s.city or "unknown", {"stations": 0, "with_price": 0})
            c["stations"] += 1
            if s.price_ntd_per_kwh is not None:
                c["with_price"] += 1
        return counts

    def details(self, station_id: str) -> dict | None:
        s = self.get(station_id)
        if not s:
            return None
        conn = _connect(self.path)
        try:
            rates = [
                dict(r)
                for r in conn.execute(
                    "SELECT rate_type, pricing_type, rate_price, peak, start_time, end_time "
                    "FROM charging_rates WHERE station_id = ? LIMIT 20",
                    (station_id,),
                )
            ]
            parking = [
                dict(r)
                for r in conn.execute(
                    "SELECT rate_type, pricing_type, day_type, rate_price, max_price "
                    "FROM parking_rates WHERE station_id = ? LIMIT 10",
                    (station_id,),
                )
            ]
        finally:
            conn.close()
        for r in rates:
            r["unit"] = "NT$/kWh" if r["rate_type"] == RATE_TYPE_PER_KWH else "unit not confirmed"
        return {
            **asdict(s),
            "charging_rates": _dedupe(rates),
            "parking_rates": _dedupe(parking),
        }


def _fold(s: str) -> str:
    return "".join(s.lower().replace("台", "臺").split()).replace("-", "").replace("_", "")


def _dedupe(rows: list[dict]) -> list[dict]:
    seen, out = set(), []
    for r in rows:
        key = tuple(sorted(r.items()))
        if key not in seen:
            seen.add(key)
            out.append(r)
    return out


@lru_cache(maxsize=1)
def store() -> StationStore:
    return StationStore()
