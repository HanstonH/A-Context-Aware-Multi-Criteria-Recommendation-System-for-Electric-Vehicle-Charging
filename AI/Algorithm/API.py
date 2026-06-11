"""TDX EV charging-station API client.

Fetches electric-vehicle charging data from Taiwan's TDX (Transport Data
eXchange) platform. Authentication uses the OAuth2 client-credentials flow.

Endpoints wrapped here (all return data for a single city):
  * /v1/EV/Station/City/{City}             -> static station info (name, lat/lon, ...)
  * /v1/EV/ConnectorLiveStatus/City/{City} -> live connector availability/usage
  * /v1/EV/ChargingRate/City/{City}        -> charging price rates
  * /v1/EV/ParkingRate/City/{City}         -> parking price rates

Designed to be reused later from the AI/ project.
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional
import os

import requests
from dotenv import load_dotenv

load_dotenv()


# Auth + service endpoints (see https://github.com/tdxmotc/SampleCode).
TDX_AUTH_URL = (
    "https://tdx.transportdata.tw/auth/realms/TDXConnect/"
    "protocol/openid-connect/token"
)
TDX_API_BASE = "https://tdx.transportdata.tw/api/basic"

# Valid {City} path values accepted by the TDX EV endpoints.
TDX_CITIES = (
    "Taipei", "NewTaipei", "Taoyuan", "Taichung", "Tainan", "Kaohsiung",
    "Keelung", "Hsinchu", "HsinchuCounty", "MiaoliCounty", "ChanghuaCounty",
    "NantouCounty", "YunlinCounty", "ChiayiCounty", "Chiayi", "PingtungCounty",
    "YilanCounty", "HualienCounty", "TaitungCounty", "KinmenCounty",
    "PenghuCounty", "LienchiangCounty",
)


class TDXAuthError(RuntimeError):
    """Raised when an access token cannot be obtained."""


class TDXClient:
    """Minimal TDX API client with automatic access-token management."""

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        *,
        timeout: int = 30,
        token_safety_margin: int = 60,
        max_retries: int = 4,
    ) -> None:
        self.client_id = client_id
        self.client_secret = client_secret
        self.timeout = timeout
        self.max_retries = max_retries
        # Refresh a bit before the real expiry to avoid edge-of-expiry 401s.
        self._token_safety_margin = token_safety_margin

        self._session = requests.Session()
        self._access_token: Optional[str] = None
        self._token_expiry: float = 0.0

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------
    def _get_access_token(self) -> str:
        """Return a valid token, fetching/refreshing it when needed."""
        if self._access_token and time.time() < self._token_expiry:
            return self._access_token

        payload = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }
        headers = {"content-type": "application/x-www-form-urlencoded"}

        try:
            resp = self._session.post(
                TDX_AUTH_URL, data=payload, headers=headers, timeout=self.timeout
            )
            resp.raise_for_status()
        except requests.RequestException as exc:
            raise TDXAuthError(f"Failed to obtain TDX access token: {exc}") from exc

        data = resp.json()
        token = data.get("access_token")
        if not token:
            raise TDXAuthError(f"No access_token in TDX auth response: {data}")

        expires_in = int(data.get("expires_in", 86400))
        self._access_token = token
        self._token_expiry = time.time() + expires_in - self._token_safety_margin
        return token

    # ------------------------------------------------------------------
    # Generic request
    # ------------------------------------------------------------------
    def _get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """GET a TDX API path and return the parsed JSON body."""
        query: Dict[str, Any] = {"$format": "JSON"}
        if params:
            query.update(params)

        url = f"{TDX_API_BASE}{path}"
        backoff = 2.0
        for attempt in range(self.max_retries + 1):
            headers = {
                "authorization": f"Bearer {self._get_access_token()}",
                "accept-encoding": "gzip",
            }
            resp = self._session.get(
                url, headers=headers, params=query, timeout=self.timeout
            )
            # Respect rate limiting: back off and retry on 429.
            if resp.status_code == 429 and attempt < self.max_retries:
                wait = float(resp.headers.get("Retry-After", backoff))
                time.sleep(wait)
                backoff *= 2
                continue
            resp.raise_for_status()
            return resp.json()
        # Loop only exits via return/raise; this satisfies type checkers.
        resp.raise_for_status()
        return resp.json()

    @staticmethod
    def _unwrap(body: Any, array_key: str) -> List[Dict[str, Any]]:
        """Return the data array from a TDX response.

        v1 EV responses are wrapped objects (e.g. ``{"Stations": [...]}``),
        but fall back gracefully if a bare list is returned.
        """
        if isinstance(body, dict):
            return body.get(array_key, []) or []
        if isinstance(body, list):
            return body
        return []

    @staticmethod
    def _validate_city(city: str) -> None:
        if city not in TDX_CITIES:
            raise ValueError(
                f"Unknown city {city!r}. Valid values: {', '.join(TDX_CITIES)}"
            )

    # ------------------------------------------------------------------
    # EV endpoints
    # ------------------------------------------------------------------
    def get_ev_stations(
        self, city: str, *, top: int = 10000, **odata: Any
    ) -> List[Dict[str, Any]]:
        """Static charging-station info (StationName, PositionLat/Lon, ...)."""
        self._validate_city(city)
        body = self._get(f"/v1/EV/Station/City/{city}", {"$top": top, **odata})
        return self._unwrap(body, "Stations")

    def get_ev_connector_live_status(
        self, city: str, *, top: int = 10000, **odata: Any
    ) -> List[Dict[str, Any]]:
        """Live connector availability / usage (updated every minute)."""
        self._validate_city(city)
        body = self._get(
            f"/v1/EV/ConnectorLiveStatus/City/{city}", {"$top": top, **odata}
        )
        return self._unwrap(body, "LiveStatuses")

    def get_ev_charging_rate(
        self, city: str, *, top: int = 10000, **odata: Any
    ) -> List[Dict[str, Any]]:
        """Charging price rates for the city's stations."""
        self._validate_city(city)
        body = self._get(f"/v1/EV/ChargingRate/City/{city}", {"$top": top, **odata})
        return self._unwrap(body, "ChargingRates")

    def get_ev_parking_rate(
        self, city: str, *, top: int = 10000, **odata: Any
    ) -> List[Dict[str, Any]]:
        """Parking price rates for the city's stations."""
        self._validate_city(city)
        body = self._get(f"/v1/EV/ParkingRate/City/{city}", {"$top": top, **odata})
        return self._unwrap(body, "ParkingRates")


# ==========================================
# Example Usage
# ==========================================
if __name__ == "__main__":
    import json
    import sys

    # Ensure non-ASCII (Chinese) output prints correctly on Windows consoles.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    # Replace with your actual TDX Client ID and Secret
    CLIENT_ID = os.getenv("TDX_CLIENT_ID")
    CLIENT_SECRET = os.getenv("TDX_CLIENT_SECRET")

    CITY = "Taipei"

    client = TDXClient(CLIENT_ID, CLIENT_SECRET)

    stations = client.get_ev_stations(CITY)
    live_status = client.get_ev_connector_live_status(CITY)
    charging_rate = client.get_ev_charging_rate(CITY)
    parking_rate = client.get_ev_parking_rate(CITY)

    print(f"[{CITY}] stations:        {len(stations)}")
    print(f"[{CITY}] live statuses:   {len(live_status)}")
    print(f"[{CITY}] charging rates:  {len(charging_rate)}")
    print(f"[{CITY}] parking rates:   {len(parking_rate)}")

    if stations:
        first = stations[0]
        print("\nSample station:")
        print(
            json.dumps(
                {
                    "StationID": first.get("StationID"),
                    "StationName": first.get("StationName"),
                    "PositionLat": first.get("PositionLat"),
                    "PositionLon": first.get("PositionLon"),
                    "Spaces": first.get("Spaces"),
                    "ChargingPoints": first.get("ChargingPoints"),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
