"""Integration tests for the full Calculation_Model pipeline with fake TDX + Google."""
import pandas as pd
import pytest

from logic import Calculation_Model, _FAILED_DISTANCE_M
from tests.conftest import USER_LOCATION, FakeTDXClient


def make_model(fake_tdx, battery=50, **kwargs):
    return Calculation_Model(USER_LOCATION, battery, tdx_client=fake_tdx, **kwargs)


# --- properties --------------------------------------------------------------
def test_reachable_range_uses_battery_range_and_safety_factor(fake_tdx):
    model = make_model(fake_tdx, battery=50, full_range_km=300, range_safety_factor=0.8)
    assert model.battery_fraction == 0.5
    assert model.reachable_metres == pytest.approx(120_000)


def test_negative_battery_is_treated_as_zero(fake_tdx):
    assert make_model(fake_tdx, battery=-10).reachable_metres == 0


# --- step 1-2: building the station table -------------------------------------
def test_build_station_dataframe_merges_availability_and_cost(fake_tdx):
    df = make_model(fake_tdx).build_station_dataframe().set_index("StationID")

    assert fake_tdx.calls == ["stations:Taipei", "live:Taipei", "rates:Taipei"]
    assert df.loc["S1", "available_points"] == 3
    assert df.loc["S1", "total_connectors"] == 4
    assert df.loc["S2", "available_points"] == 0
    assert df.loc["S3", "available_points"] == 1   # faulty connector is not "available"
    assert df.loc["S1", "cost"] == 8.0
    assert df.loc["S2", "cost"] == 0.0             # free station
    assert df.loc["S4", "cost"] == 8.0             # missing rate -> median(8, 0, 12)


def test_build_station_dataframe_drops_rows_without_coordinates_and_duplicates():
    stations = [
        {"StationID": "A", "PositionLat": 25.0, "PositionLon": 121.5},
        {"StationID": "A", "PositionLat": 25.0, "PositionLon": 121.5},
        {"StationID": "B", "PositionLat": None, "PositionLon": 121.5},
    ]
    model = make_model(FakeTDXClient(stations=stations, live=[], rates=[]))
    df = model.build_station_dataframe()
    assert df["StationID"].tolist() == ["A"]
    assert df.loc[0, "available_points"] == 0
    assert df.loc[0, "cost"] == 0.0


# --- step 3: candidate selection --------------------------------------------------
def test_select_candidates_keeps_only_reachable_and_available(fake_tdx):
    model = make_model(fake_tdx, battery=10)  # ~24 km range
    candidates = model.select_candidates(model.build_station_dataframe())
    ids = candidates["StationID"].tolist()
    assert "S4" not in ids          # Taichung: out of range
    assert "S2" not in ids          # fully occupied
    assert ids == ["S1", "S3"]      # sorted by straight-line distance


def test_select_candidates_respects_max_candidates(fake_tdx):
    model = make_model(fake_tdx, battery=100, max_candidates=2)
    candidates = model.select_candidates(model.build_station_dataframe())
    assert len(candidates) == 2


def test_select_candidates_falls_back_to_busy_stations_when_none_are_free():
    live = [{"StationID": sid, "ConnectorStatus": 2} for sid in ("S1", "S2", "S3", "S4")]
    model = make_model(FakeTDXClient(live=live), battery=10)
    candidates = model.select_candidates(model.build_station_dataframe())
    assert set(candidates["StationID"]) == {"S1", "S2", "S3"}


def test_select_candidates_raises_when_nothing_is_reachable(fake_tdx):
    far_only = [s for s in fake_tdx.stations if s["StationID"] == "S4"]
    model = make_model(FakeTDXClient(stations=far_only), battery=5)
    with pytest.raises(ValueError, match="No station reachable"):
        model.select_candidates(model.build_station_dataframe())


# --- step 4: road distance ---------------------------------------------------------
def test_process_distances_uses_routes_api_result(fake_tdx, fake_google):
    model = make_model(fake_tdx)
    candidates = model.select_candidates(model.build_station_dataframe())
    out = model.process_distances(candidates)
    assert (out["distance"] >= out["straight_line_m"].astype(int)).all()


def test_process_distances_penalises_api_failure(fake_tdx, monkeypatch):
    import logic
    monkeypatch.setattr(logic, "get_distance_ev", lambda dest, user: None)
    model = make_model(fake_tdx)
    out = model.process_distances(pd.DataFrame({"lat": [25.03], "lon": [121.56]}))
    assert out.loc[0, "distance"] == _FAILED_DISTANCE_M


def test_process_distances_falls_back_to_straight_line_when_distance_missing(fake_tdx, monkeypatch):
    import logic
    monkeypatch.setattr(logic, "get_distance_ev", lambda dest, user: {"routes": [{"duration": "0s"}]})
    model = make_model(fake_tdx)
    out = model.process_distances(pd.DataFrame({"lat": [25.03], "lon": [121.56], "straight_line_m": [42.0]}))
    assert out.loc[0, "distance"] == 42.0


# --- step 5: scoring ------------------------------------------------------------------
def test_total_score_requires_columns(fake_tdx):
    with pytest.raises(ValueError, match="missing required columns"):
        make_model(fake_tdx).total_score(pd.DataFrame({"distance": [1]}))


def test_total_score_equals_sum_of_contributions(fake_tdx):
    df = pd.DataFrame({"distance": [100, 500, 900], "cost": [10, 5, 0], "available_points": [1, 2, 4]})
    out = make_model(fake_tdx).total_score(df)
    expected = out["contrib_dist"] + out["contrib_cost"] + out["contrib_avail"]
    pd.testing.assert_series_equal(out["total_score"], expected, check_names=False)
    assert out["total_score"].between(0, 1).all()


# --- full pipeline -----------------------------------------------------------------------
def test_recommend_end_to_end_with_live_tdx(fake_tdx, fake_google):
    ranked = make_model(fake_tdx, battery=15).recommend()

    assert not ranked.empty
    assert ranked["topsis_score"].is_monotonic_decreasing
    assert ranked["topsis_score"].between(0, 1).all()
    for col in ("distance", "cost", "available_points", "total_score", "nearby_pois", "poi_count"):
        assert col in ranked.columns
    assert (ranked["poi_count"] == 1).all()
    assert ranked.iloc[0]["StationID"] == "S1"   # closest station with free connectors


def test_recommend_from_offline_snapshot(fake_tdx, fake_google):
    ranked = make_model(fake_tdx, battery=40, use_snapshot=True).recommend()
    assert fake_tdx.calls == []                   # snapshot mode never calls TDX
    assert 1 <= len(ranked) <= 10
    assert ranked["topsis_score"].is_monotonic_decreasing
