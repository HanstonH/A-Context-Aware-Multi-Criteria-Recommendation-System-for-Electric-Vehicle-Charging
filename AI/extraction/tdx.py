"""TDX client helpers that return full API JSON bodies for archival."""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

# Algorithm/API.py lives next to the extraction package under AI/.
_ALGO_DIR = Path(__file__).resolve().parents[1] / "Algorithm"
_ENV_PATH = Path(__file__).resolve().parents[1] / ".env"
if str(_ALGO_DIR) not in sys.path:
    sys.path.insert(0, str(_ALGO_DIR))

load_dotenv(_ENV_PATH)

from API import TDXClient, TDX_CITIES  # noqa: E402

# Some city values in TDX_CITIES can return 400 for EV endpoints.
UNSUPPORTED_EV_CITIES = {"LienchiangCounty"}
SUPPORTED_EV_CITIES = tuple(c for c in TDX_CITIES if c not in UNSUPPORTED_EV_CITIES)


class RawTDXClient(TDXClient):
    """Fetch complete TDX JSON responses (not unwrapped arrays)."""

    def fetch_stations_body(self, city: str, *, top: int = 10000) -> Any:
        self._validate_city(city)
        return self._get(f"/v1/EV/Station/City/{city}", {"$top": top})

    def fetch_charging_rate_body(self, city: str, *, top: int = 10000) -> Any:
        self._validate_city(city)
        return self._get(f"/v1/EV/ChargingRate/City/{city}", {"$top": top})

    def fetch_parking_rate_body(self, city: str, *, top: int = 10000) -> Any:
        self._validate_city(city)
        return self._get(f"/v1/EV/ParkingRate/City/{city}", {"$top": top})

    def fetch_live_status_body(self, city: str, *, top: int = 10000) -> Any:
        self._validate_city(city)
        return self._get(
            f"/v1/EV/ConnectorLiveStatus/City/{city}", {"$top": top}
        )


def build_client() -> RawTDXClient:
    client_id = os.getenv("TDX_CLIENT_ID")
    client_secret = os.getenv("TDX_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise RuntimeError(
            "TDX_CLIENT_ID and TDX_CLIENT_SECRET must be set in AI/.env"
        )
    return RawTDXClient(client_id, client_secret)


__all__ = [
    "RawTDXClient",
    "TDX_CITIES",
    "UNSUPPORTED_EV_CITIES",
    "SUPPORTED_EV_CITIES",
    "build_client",
]
