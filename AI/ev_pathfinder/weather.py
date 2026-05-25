"""Weather service — fetches current conditions for Palo Alto from Open-Meteo."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional

import requests

from .config import PALO_ALTO_CENTER, WEATHER_API_URL

_CACHE_TTL_SECS = 600  # 10 min


@dataclass
class WeatherSnapshot:
    temperature: float   # °C
    precipitation: float # mm
    cloud_cover: float   # %


class WeatherService:
    """Lightweight wrapper around Open-Meteo current-weather endpoint."""

    def __init__(self):
        self._cache: Optional[WeatherSnapshot] = None
        self._cache_ts: float = 0.0

    def get_current(self) -> WeatherSnapshot:
        now = time.time()
        if self._cache and (now - self._cache_ts) < _CACHE_TTL_SECS:
            return self._cache

        params = {
            "latitude": PALO_ALTO_CENTER[0],
            "longitude": PALO_ALTO_CENTER[1],
            "current_weather": "true",
            "hourly": "temperature_2m,precipitation,cloudcover",
            "timezone": "America/Los_Angeles",
            "forecast_days": 1,
        }

        try:
            resp = requests.get(WEATHER_API_URL, params=params, timeout=8)
            data = resp.json()
            cw = data.get("current_weather", {})
            snap = WeatherSnapshot(
                temperature=float(cw.get("temperature", 18.0)),
                precipitation=float(cw.get("precipitation", 0.0) or 0.0),
                cloud_cover=float(cw.get("cloudcover", 50.0) or 50.0),
            )

            if snap.cloud_cover == 50.0 and "hourly" in data:
                hourly = data["hourly"]
                idx = min(len(hourly.get("cloudcover", [])) - 1, 0)
                if hourly.get("cloudcover"):
                    snap = WeatherSnapshot(
                        temperature=snap.temperature,
                        precipitation=snap.precipitation,
                        cloud_cover=float(hourly["cloudcover"][idx]),
                    )

        except Exception:
            snap = WeatherSnapshot(temperature=18.0, precipitation=0.0, cloud_cover=50.0)

        self._cache = snap
        self._cache_ts = now
        return snap
