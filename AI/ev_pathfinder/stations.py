"""Station registry — extracts unique Palo Alto chargers from the ChargePoint dataset."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Optional

import pandas as pd

from .config import (
    PALO_ALTO_BOUNDS,
    PALO_ALTO_CENTER,
    RAW_DATA_PATH,
    SEARCH_RADIUS_METRES,
)


@dataclass
class Station:
    mac: str
    name: str
    address: str
    latitude: float
    longitude: float
    plug_type: str
    plug_encoded: int


def _haversine_metres(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6_371_000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def is_within_palo_alto(lat: float, lon: float) -> bool:
    b = PALO_ALTO_BOUNDS
    return b["lat_min"] <= lat <= b["lat_max"] and b["lon_min"] <= lon <= b["lon_max"]


def _encode_plug(plug_type: str) -> int:
    if isinstance(plug_type, str) and "NEMA" in plug_type.upper():
        return 1
    return 0


class StationRegistry:
    """Singleton-style registry of all Palo Alto EV stations."""

    def __init__(self, csv_path: Optional[str] = None):
        self._stations: Dict[str, Station] = {}
        self._load(csv_path or str(RAW_DATA_PATH))

    def _load(self, csv_path: str) -> None:
        cols = [
            "Station Name", "MAC Address", "Address 1",
            "Latitude", "Longitude", "Plug Type",
        ]
        df = pd.read_csv(csv_path, usecols=cols, low_memory=False)
        df = df.dropna(subset=["Latitude", "Longitude"])
        grouped = df.groupby("MAC Address").first().reset_index()

        for _, row in grouped.iterrows():
            mac = row["MAC Address"]
            lat, lon = float(row["Latitude"]), float(row["Longitude"])
            if not is_within_palo_alto(lat, lon):
                continue
            self._stations[mac] = Station(
                mac=mac,
                name=str(row.get("Station Name", mac)),
                address=str(row.get("Address 1", "")),
                latitude=lat,
                longitude=lon,
                plug_type=str(row.get("Plug Type", "J1772")),
                plug_encoded=_encode_plug(str(row.get("Plug Type", "J1772"))),
            )

    @property
    def all_stations(self) -> List[Station]:
        return list(self._stations.values())

    def get(self, mac: str) -> Optional[Station]:
        return self._stations.get(mac)

    def find_nearby(
        self,
        lat: float,
        lon: float,
        radius_m: float = SEARCH_RADIUS_METRES,
    ) -> List[Station]:
        nearby: List[Station] = []
        for s in self._stations.values():
            if _haversine_metres(lat, lon, s.latitude, s.longitude) <= radius_m:
                nearby.append(s)
        return nearby

    def to_geojson(self) -> dict:
        features = []
        for s in self._stations.values():
            features.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [s.longitude, s.latitude]},
                "properties": {
                    "mac": s.mac,
                    "name": s.name,
                    "address": s.address,
                    "plug_type": s.plug_type,
                },
            })
        return {"type": "FeatureCollection", "features": features}
