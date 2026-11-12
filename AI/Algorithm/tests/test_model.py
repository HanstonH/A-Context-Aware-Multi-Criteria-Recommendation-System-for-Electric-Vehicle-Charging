"""Tests for Calculation_Model: data merging, candidate selection, scoring and
the full recommend() pipeline with TDX and Google stubbed out.
"""
import numpy as np
import pandas as pd
import pytest

import logic
from conftest import FakeTDX
from logic import Calculation_Model, _ROAD_DETOUR_FACTOR, haversine_metres


# ---------------------------------------------------------------------------
# Geometry / range
# ---------------------------------------------------------------------------

def test_haversine_zero_and_one_degree_latitude():
    assert haversine_metres(25.0, 121.5, 25.0, 121.5) == pytest.approx(0.0)
    assert haversine_metres(0.0, 0.0, 1.0, 0.0) == pytest.approx(111_195, rel=1e-3)


def test_haversine_is_vectorised():
    out = haversine_metres(0.0, 0.0, [0.0, 1.0], [0.0, 0.0])
    assert out.shape == (2,)
    assert out[0] == pytest.approx(0.0)


@pytest.mark.parametrize(
    "battery, expected_m",
    [(50, 0.5 * 300 * 1000 * 0.8), (0, 0.0), (-10, 0.0), (100, 240_000)],
)
def test_reachable_metres(make_model, battery, expected_m):
    assert make_model(battery).reachable_metres == pytest.approx(expected_m)


# ---------------------------------------------------------------------------
# TDX merging: availability and cost
# ---------------------------------------------------------------------------

def test_attach_availability_counts_idle_connectors():
    df = pd.DataFrame({"StationID": ["A", "B", "C"]})
    live = [
        {"StationID": "A", "ConnectorStatus": 1},
        {"StationID": "A", "ConnectorStatus": 2},
        {"StationID": "A", "ConnectorStatus": 1},
        {"StationID": "B", "ConnectorStatus": 3},
    ]
    out = Calculation_Model._attach_availability(df, live).set_index("StationID")
    assert out.loc["A", "available_points"] == 2
    assert out.loc["A", "total_connectors"] == 3
    assert out.loc["B", "available_points"] == 0
    # No live record at all -> 0/0 rather than NaN.
    assert out.loc["C", "available_points"] == 0
    assert out.loc["C", "total_connectors"] == 0


def test_attach_availability_with_no_live_data():
    out = Calculation_Model._attach_availability(pd.DataFrame({"StationID": ["A"]}), [])
    assert out.loc[0, "available_points"] == 0
    assert out.loc[0, "total_connectors"] == 0


def test_cost_prefers_per_kwh_rate_over_other_types():
    rates = [
        {"StationID": "A", "Rates": [
            {"RateType": 4, "RatePrice": 100.0},  # per hour
            {"RateType": 2, "RatePrice": 9.0},
            {"RateType": 2, "RatePrice": 11.0},
        ]},
    ]
    out = Calculation_Model._station_cost_from_rates(rates).set_index("StationID")
    assert out.loc["A", "cost"] == pytest.approx(10.0)  # median of per-kWh only


def test_free_station_costs_zero():
    rates = [{"StationID": "F", "Rates": [{"RateType": 1, "RatePrice": None}]}]
    out = Calculation_Model._station_cost_from_rates(rates)
    assert out.loc[0, "cost"] == 0.0


def test_no_rates_gives_empty_table():
    out = Calculation_Model._station_cost_from_rates([{"StationID": "A", "Rates": None}])
    assert list(out.columns) == ["StationID", "cost"]
    assert out.empty


def test_missing_cost_is_filled_with_median(make_model):
    df = pd.DataFrame({"StationID": ["A", "B", "C"]})
    rates = [
        {"StationID": "A", "Rates": [{"RateType": 2, "RatePrice": 6.0}]},
        {"StationID": "B", "Rates": [{"RateType": 2, "RatePrice": 10.0}]},
    ]
    out = make_model()._attach_costs(df, rates).set_index("StationID")
    assert out.loc["C", "cost"] == pytest.approx(8.0)


def test_non_kwh_price_is_not_compared_as_per_kwh():
    rates = [
        {"StationID": "kwh", "Rates": [{"RateType": 2, "RatePrice": 8.0}]},
        {"StationID": "hourly", "Rates": [{"RateType": 4, "RatePrice": 150.0}]},
    ]
    out = Calculation_Model._station_cost_from_rates(rates).set_index("StationID")
    assert "hourly" not in out.index


# ---------------------------------------------------------------------------
# Candidate selection
# ---------------------------------------------------------------------------

def test_select_candidates_keeps_reachable_available_nearest_first(make_model, station_df):
    out = make_model(50).select_candidates(station_df)
    # S4 "Busy" has 0 free connectors and is dropped.
    assert list(out["StationID"]) == ["S1", "S2", "S3"]
    assert out["straight_line_m"].is_monotonic_increasing


def test_select_candidates_respects_battery_range(make_model, station_df):
    # 1% battery -> 2.4 km range; S3 (~14 km away) is out of reach.
    out = make_model(1).select_candidates(station_df)
    assert "S3" not in set(out["StationID"])


def test_select_candidates_falls_back_to_busy_stations(make_model, station_df):
    busy = station_df.assign(available_points=0)
    out = make_model(50).select_candidates(busy)
    assert len(out) == 4


def test_select_candidates_caps_at_max_candidates(make_model, station_df):
    assert len(make_model(50, max_candidates=2).select_candidates(station_df)) == 2


def test_select_candidates_raises_when_nothing_reachable(make_model, station_df):
    with pytest.raises(ValueError, match="No station reachable"):
        make_model(0).select_candidates(station_df)


# ---------------------------------------------------------------------------
# Road distance
# ---------------------------------------------------------------------------

def test_process_distances_uses_route_and_fallbacks(make_model, monkeypatch):
    responses = {
        (1.0, 1.0): {"routes": [{"distanceMeters": 1234}]},
        (2.0, 2.0): {"routes": [{}]},  # degenerate trip, no distanceMeters
        (3.0, 3.0): None,              # API failure
    }
    monkeypatch.setattr(logic, "get_distance_ev", lambda dest, origin: responses[dest])
    df = pd.DataFrame({
        "lat": [1.0, 2.0, 3.0],
        "lon": [1.0, 2.0, 3.0],
        "straight_line_m": [1000.0, 42.0, 5000.0],
    })
    out = make_model().process_distances(df)
    assert list(out["distance"]) == [1234, 42.0, 5000.0 * _ROAD_DETOUR_FACTOR]


# ---------------------------------------------------------------------------
# Weighted-sum auxiliary score
# ---------------------------------------------------------------------------

def test_total_score_uses_dynamic_weights(make_model):
    df = pd.DataFrame({
        "distance": [100.0, 900.0],
        "cost": [10.0, 5.0],
        "available_points": [4, 2],
    })
    model = make_model(30)
    out = model.total_score(df)
    w = model.weights
    expected = w.w_distance * out["n_dist"] + w.w_cost * out["n_cost"] + w.w_pots * out["n_avail"]
    np.testing.assert_allclose(out["total_score"], expected)
    assert list(out["n_dist"]) == [1.0, 0.0]
    assert list(out["n_cost"]) == [0.0, 1.0]


def test_total_score_requires_columns(make_model):
    with pytest.raises(ValueError, match="missing required columns"):
        make_model().total_score(pd.DataFrame({"distance": [1.0]}))


def test_total_score_treats_constant_columns_consistently(make_model):
    df = pd.DataFrame({"distance": [500.0, 500.0], "cost": [8.0, 8.0], "available_points": [2, 2]})
    out = make_model().total_score(df)
    assert out.loc[0, "n_dist"] == out.loc[0, "n_cost"] == out.loc[0, "n_avail"]


# ---------------------------------------------------------------------------
# apply_topsis id mapping
# ---------------------------------------------------------------------------

def _scored_frame(ids):
    return pd.DataFrame({
        "StationID": ids,
        "distance": [100.0, 900.0],
        "cost": [5.0, 12.0],
        "available_points": [4, 0],
    })


def test_apply_topsis_maps_scores_back_by_station_id(make_model):
    out = make_model(50).apply_topsis(_scored_frame(["A", "B"])).set_index("StationID")
    assert out.loc["A", "topsis_score"] == pytest.approx(1.0)
    assert out.loc["B", "topsis_score"] == pytest.approx(0.0)


def test_apply_topsis_handles_numeric_station_ids(make_model):
    out = make_model(50).apply_topsis(_scored_frame([101, 202])).set_index("StationID")
    assert out.loc[101, "topsis_score"] == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# Snapshot mode
# ---------------------------------------------------------------------------

def test_snapshot_availability_is_synthetic():
    """Documents that offline mode invents availability as round(0.7 * plugs).

    Every station with at least one plug therefore looks "available", so the
    available-now filter and the pots criterion carry no real signal.
    """
    df = logic.load_all_stations_from_snapshot("Taipei")
    assert not df.empty
    expected = (df["total_connectors"] * 0.7).round().astype(int)
    assert (df["available_points"] == expected).all()
    with_plugs = df[df["total_connectors"] >= 1]
    assert (with_plugs["available_points"] >= 1).all()


# ---------------------------------------------------------------------------
# Full pipeline with TDX + Google stubbed
# ---------------------------------------------------------------------------

def _tdx_station(sid, lat, lon):
    return {
        "StationID": sid,
        "StationName": {"Zh_tw": sid},
        "PositionLat": lat,
        "PositionLon": lon,
        "Spaces": 2,
        "ChargingPoints": 2,
    }


NEAR = _tdx_station("A_near_pricey", 25.0500, 121.5170)
FAR = _tdx_station("B_far_cheap", 25.0900, 121.5170)
UNROUTABLE = _tdx_station("F_no_route", 25.0700, 121.5170)

ROAD_M = {(NEAR["PositionLat"], NEAR["PositionLon"]): 500,
          (FAR["PositionLat"], FAR["PositionLon"]): 5000}


def _fake_tdx(*stations):
    live = [{"StationID": s["StationID"], "ConnectorStatus": 1}
            for s in stations for _ in range(2)]
    price = {"A_near_pricey": 12.0, "B_far_cheap": 8.0, "F_no_route": 10.0}
    rates = [{"StationID": s["StationID"],
              "Rates": [{"RateType": 2, "RatePrice": price[s["StationID"]]}]}
             for s in stations]
    return FakeTDX(stations, live, rates)


def test_recommend_pipeline_end_to_end(make_model, no_google):
    no_google(ROAD_M)
    model = make_model(10, tdx=_fake_tdx(NEAR, FAR), use_snapshot=False)
    ranked = model.recommend()
    assert list(ranked["StationID"]) == ["A_near_pricey", "B_far_cheap"]
    assert ranked["topsis_score"].is_monotonic_decreasing
    for col in ("distance", "cost", "available_points", "total_score", "nearby_pois", "poi_count"):
        assert col in ranked.columns
    assert ranked.loc[0, "poi_count"] == 0


def test_failed_route_does_not_change_ranking_of_other_stations(make_model, no_google):
    no_google(ROAD_M)  # UNROUTABLE has no entry -> API returns None
    model = make_model(10, tdx=_fake_tdx(NEAR, FAR, UNROUTABLE), use_snapshot=False)
    ranked = model.recommend()
    others = [sid for sid in ranked["StationID"] if sid != "F_no_route"]
    assert others == ["A_near_pricey", "B_far_cheap"]


def test_availability_is_min_max_scaled_like_other_criteria(make_model):
    df = pd.DataFrame({"distance": [100.0, 200.0, 300.0], "cost": [8.0, 8.0, 8.0],
                       "available_points": [2, 3, 4]})
    out = make_model().total_score(df)
    assert list(out["n_avail"]) == [0.0, 0.5, 1.0]
    assert list(out["n_cost"]) == [0.5, 0.5, 0.5]
