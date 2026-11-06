"""Shared pytest fixtures for the AI recommender.

Every test runs fully offline:
  * ``AI/Algorithm`` is put on ``sys.path`` so ``import logic`` works the same
    way it does when you run ``python logic.py``.
  * Dummy TDX credentials are set so ``app.py`` can be imported without a
    real ``.env`` file.
  * All outgoing HTTP via ``requests`` is blocked, so a test that forgets to
    mock Google / TDX fails loudly instead of burning paid API quota.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Dict, List

import pytest

ALGORITHM_DIR = Path(__file__).resolve().parent.parent / "Algorithm"
if str(ALGORITHM_DIR) not in sys.path:
    sys.path.insert(0, str(ALGORITHM_DIR))

# Must be set before app.py is imported (it raises without them).
os.environ.setdefault("TDX_CLIENT_ID", "test-client-id")
os.environ.setdefault("TDX_CLIENT_SECRET", "test-client-secret")
os.environ.setdefault("GOOGLE_MAPS_API_KEY", "test-google-key")


def pytest_collection_modifyitems(config, items):
    if os.getenv("RUN_LIVE_TESTS") == "1":
        return
    skip_live = pytest.mark.skip(reason="live API test; set RUN_LIVE_TESTS=1 to run")
    for item in items:
        if "live" in item.keywords:
            item.add_marker(skip_live)


@pytest.fixture(autouse=True)
def block_network(request, monkeypatch):
    """Fail any real HTTP request made through ``requests``."""
    if "live" in request.keywords:
        return

    def _blocked(self, method, url, *args, **kwargs):
        raise RuntimeError(f"Network access is disabled in tests: {method} {url}")

    monkeypatch.setattr("requests.sessions.Session.request", _blocked)


# ---------------------------------------------------------------------------
# Fake TDX data (shape mirrors the real TDX v1 EV responses)
# ---------------------------------------------------------------------------
USER_LOCATION = (25.0330, 121.5654)  # Taipei 101


def _station(station_id: str, name: str, lat: float, lon: float, points: int) -> Dict[str, Any]:
    return {
        "StationID": station_id,
        "StationName": {"Zh_tw": name},
        "PositionLat": lat,
        "PositionLon": lon,
        "Spaces": points,
        "ChargingPoints": points,
    }


FAKE_STATIONS: List[Dict[str, Any]] = [
    _station("S1", "Near & cheap", 25.0340, 121.5660, 4),
    _station("S2", "Near but full", 25.0335, 121.5650, 2),
    _station("S3", "Medium distance", 25.0450, 121.5750, 6),
    _station("S4", "Far away (out of range at low battery)", 24.1477, 120.6736, 8),
]

FAKE_LIVE_STATUS: List[Dict[str, Any]] = [
    # S1: 3 of 4 free
    *({"StationID": "S1", "ConnectorStatus": s} for s in (1, 1, 1, 2)),
    # S2: all occupied
    *({"StationID": "S2", "ConnectorStatus": s} for s in (2, 2)),
    # S3: 1 free, 1 faulty
    *({"StationID": "S3", "ConnectorStatus": s} for s in (1, 3)),
    # S4: everything free
    *({"StationID": "S4", "ConnectorStatus": 1} for _ in range(8)),
]

FAKE_RATES: List[Dict[str, Any]] = [
    {"StationID": "S1", "Rates": [{"RateType": 2, "RatePrice": 8.0}]},
    {"StationID": "S2", "Rates": [{"RateType": 1, "RatePrice": None}]},  # free
    {"StationID": "S3", "Rates": [
        {"RateType": 2, "RatePrice": 12.0},
        {"RateType": 4, "RatePrice": 50.0},  # per-hour, ignored when per-kWh exists
    ]},
    # S4 has no rate record -> should fall back to the median
]


class FakeTDXClient:
    """Drop-in replacement for ``API.TDXClient`` that never touches the network."""

    def __init__(self, stations=None, live=None, rates=None):
        self.stations = FAKE_STATIONS if stations is None else stations
        self.live = FAKE_LIVE_STATUS if live is None else live
        self.rates = FAKE_RATES if rates is None else rates
        self.calls: List[str] = []

    def get_ev_stations(self, city, **_):
        self.calls.append(f"stations:{city}")
        return list(self.stations)

    def get_ev_connector_live_status(self, city, **_):
        self.calls.append(f"live:{city}")
        return list(self.live)

    def get_ev_charging_rate(self, city, **_):
        self.calls.append(f"rates:{city}")
        return list(self.rates)


@pytest.fixture
def fake_tdx() -> FakeTDXClient:
    return FakeTDXClient()


# ---------------------------------------------------------------------------
# Fake Google APIs
# ---------------------------------------------------------------------------
@pytest.fixture
def fake_google(monkeypatch):
    """Replace Google Routes + Places inside ``logic`` with deterministic fakes.

    Road distance = straight-line distance * 1.3 (a typical detour factor).
    Each station gets one coffee shop POI 120 m away.
    """
    import logic

    def fake_distance(destination, user_location):
        d = float(logic.haversine_metres(user_location[0], user_location[1],
                                         destination[0], destination[1]))
        return {"routes": [{"distanceMeters": int(d * 1.3), "duration": "60s"}]}

    class FakePOI:
        def call_API(self, latitude, longitude):
            return {
                "places": [{
                    "id": f"poi-{latitude:.4f}",
                    "displayName": {"text": "Test Coffee"},
                    "primaryType": "coffee_shop",
                    "location": {"latitude": latitude + 0.001, "longitude": longitude},
                    "rating": 4.5,
                }],
                "routingSummaries": [{"legs": [{"distanceMeters": 120}]}],
            }

    monkeypatch.setattr(logic, "get_distance_ev", fake_distance)
    monkeypatch.setattr(logic, "Get_POI", FakePOI)
    return {"distance": fake_distance, "poi": FakePOI}
