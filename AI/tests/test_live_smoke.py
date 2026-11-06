"""Optional smoke tests against the REAL TDX and Google APIs.

Skipped by default. Run them manually before a demo with:
    RUN_LIVE_TESTS=1 pytest -m live
They need valid keys in AI/.env and they consume API quota.
"""
import os

import pytest
from dotenv import load_dotenv

from tests.conftest import ALGORITHM_DIR

pytestmark = pytest.mark.live

load_dotenv(ALGORITHM_DIR.parent / ".env", override=True)


def test_tdx_returns_taipei_stations():
    from API import TDXClient
    client = TDXClient(os.environ["TDX_CLIENT_ID"], os.environ["TDX_CLIENT_SECRET"])
    stations = client.get_ev_stations("Taipei", top=5)
    assert stations and "StationID" in stations[0]


def test_google_routes_returns_a_distance():
    from get_Distance_EV import get_distance_ev
    result = get_distance_ev((25.0478, 121.5170), (25.0330, 121.5654))
    assert result and result["routes"][0]["distanceMeters"] > 0
