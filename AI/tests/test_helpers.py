"""Unit tests for small pure helpers: geometry, polyline decoding, POI parsing, rates."""
import numpy as np
import pandas as pd
import pytest

from get_Distance_EV import decode_polyline
from logic import Calculation_Model, _format_distance, haversine_metres


# --- haversine ---------------------------------------------------------------
def test_haversine_zero_for_same_point():
    assert haversine_metres(25.03, 121.56, 25.03, 121.56) == pytest.approx(0.0)


def test_haversine_taipei_to_taichung_is_about_130_km():
    d = haversine_metres(25.0478, 121.5170, 24.1369, 120.6855)
    assert 125_000 < d < 135_000


def test_haversine_is_vectorised():
    out = haversine_metres(25.0, 121.5, [25.0, 25.01], [121.5, 121.5])
    assert out.shape == (2,)
    assert out[0] == pytest.approx(0.0)
    assert out[1] == pytest.approx(1112, rel=0.01)  # 0.01 deg lat ~ 1.11 km


# --- polyline ------------------------------------------------------------------
def test_decode_polyline_matches_google_reference_example():
    # Example from Google's "Encoded Polyline Algorithm Format" documentation.
    points = decode_polyline("_p~iF~ps|U_ulLnnqC_mqNvxq`@")
    assert points == [(38.5, -120.2), (40.7, -120.95), (43.252, -126.453)]


def test_decode_empty_polyline():
    assert decode_polyline("") == []


# --- formatting ----------------------------------------------------------------
@pytest.mark.parametrize("metres, text", [(0, "0 m"), (999.4, "999 m"), (1000, "1.00 km"), (12345, "12.35 km")])
def test_format_distance(metres, text):
    assert _format_distance(metres) == text


# --- POI parsing ---------------------------------------------------------------
def test_parse_nearby_pois_handles_empty_responses():
    assert Calculation_Model.parse_nearby_pois(None) == []
    assert Calculation_Model.parse_nearby_pois({}) == []
    assert Calculation_Model.parse_nearby_pois({"places": []}) == []


def test_parse_nearby_pois_sorts_by_walk_distance_and_skips_bad_locations():
    data = {
        "places": [
            {"id": "far", "displayName": {"text": "Far"}, "location": {"latitude": 1, "longitude": 2}},
            {"id": "broken", "location": {}},
            {"id": "near", "displayName": {"text": "Near"}, "location": {"latitude": 3, "longitude": 4},
             "currentOpeningHours": {"openNow": True}},
            {"id": "unknown", "location": {"latitude": 5, "longitude": 6}},
        ],
        "routingSummaries": [
            {"legs": [{"distanceMeters": 400}]},
            {"legs": [{"distanceMeters": 1}]},
            {"legs": [{"distanceMeters": 50}]},
            {},
        ],
    }
    pois = Calculation_Model.parse_nearby_pois(data)
    assert [p["id"] for p in pois] == ["near", "far", "unknown"]
    assert pois[0]["walk_distance_m"] == 50
    assert pois[0]["open_now"] is True
    assert pois[-1]["walk_distance_m"] is None


# --- rate collapsing -------------------------------------------------------------
def test_station_cost_prefers_per_kwh_and_treats_free_as_zero():
    rates = [
        {"StationID": "A", "Rates": [{"RateType": 2, "RatePrice": 10}, {"RateType": 4, "RatePrice": 100}]},
        {"StationID": "B", "Rates": [{"RateType": 1}]},
        {"StationID": "C", "Rates": [{"RateType": 3, "RatePrice": 4}, {"RateType": 3, "RatePrice": 6}]},
        {"StationID": "D", "Rates": None},
    ]
    table = Calculation_Model._station_cost_from_rates(rates).set_index("StationID")["cost"]
    assert table["A"] == 10      # per-kWh preferred over per-hour
    assert table["B"] == 0.0     # free
    assert table["C"] == 5.0     # median of fallback rates
    assert "D" not in table


def test_station_cost_with_no_rates_returns_empty_frame():
    out = Calculation_Model._station_cost_from_rates([])
    assert list(out.columns) == ["StationID", "cost"]
    assert out.empty


# --- normalisation ---------------------------------------------------------------
def test_normalize_lower_is_better():
    s = pd.Series([100, 200, 300])
    np.testing.assert_allclose(Calculation_Model._normalize_lower_is_better(s), [1.0, 0.5, 0.0])
    assert (Calculation_Model._normalize_lower_is_better(pd.Series([5, 5])) == 1.0).all()


def test_normalize_higher_is_better():
    s = pd.Series([0, 2, 4])
    np.testing.assert_allclose(Calculation_Model._normalize_higher_is_better(s), [0.0, 0.5, 1.0])
    assert (Calculation_Model._normalize_higher_is_better(pd.Series([3, 3])) == 0.5).all()
    assert (Calculation_Model._normalize_higher_is_better(pd.Series([0, 0])) == 0.0).all()
