"""Shared pytest fixtures for the recommender algorithm tests.

Run from AI/:  .venv/bin/python -m pytest Algorithm/tests
"""
import sys
from pathlib import Path

import pandas as pd
import pytest

# The Algorithm modules import each other by bare name (``from API import ...``),
# so put Algorithm/ itself on sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import logic  # noqa: E402


class FakeTDX:
    """Stand-in for TDXClient that serves canned records with no network."""

    def __init__(self, stations=(), live=(), rates=()):
        self.stations = list(stations)
        self.live = list(live)
        self.rates = list(rates)

    def get_ev_stations(self, city):
        return self.stations

    def get_ev_connector_live_status(self, city):
        return self.live

    def get_ev_charging_rate(self, city):
        return self.rates


@pytest.fixture
def make_model():
    """Build a Calculation_Model that never touches TDX unless given a FakeTDX."""

    def _make(battery_percent=50.0, *, location=(25.0478, 121.5170), tdx=None, **kwargs):
        return logic.Calculation_Model(
            location,
            battery_percent,
            tdx_client=tdx or FakeTDX(),
            **kwargs,
        )

    return _make


@pytest.fixture
def station_df():
    """Small station table near Taipei Main Station, nearest first."""
    return pd.DataFrame(
        {
            "StationID": ["S1", "S2", "S3", "S4"],
            "station_name": ["Near", "Mid", "Far", "Busy"],
            "lat": [25.0480, 25.0600, 25.1500, 25.0490],
            "lon": [121.5170, 121.5300, 121.6000, 121.5180],
            "available_points": [2, 1, 3, 0],
            "total_connectors": [4, 2, 3, 2],
            "cost": [10.0, 8.0, 6.0, 9.0],
        }
    )


@pytest.fixture
def no_google(monkeypatch):
    """Stub out Google Routes / Places calls made from logic.py."""

    def install(distance_by_dest=None, default_distance=None):
        distance_by_dest = distance_by_dest or {}

        def fake_distance(dest, origin):
            metres = distance_by_dest.get(dest, default_distance)
            if metres is None:
                return None  # simulate an API failure
            return {"routes": [{"distanceMeters": metres}]}

        monkeypatch.setattr(logic, "get_distance_ev", fake_distance)
        monkeypatch.setattr(logic.Calculation_Model, "get_POI", lambda self, lat, lon: None)

    return install
