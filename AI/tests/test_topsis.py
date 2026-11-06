"""Unit tests for the pure TOPSIS ranking function (logic.py Part B)."""
import pytest

from logic import topsis_rank


def _s(id_, distance, cost, pots):
    return {"id": id_, "distance": distance, "cost": cost, "available_pots": pots}


def test_empty_input_returns_empty_list():
    assert topsis_rank([], 0.5, False) == []


def test_dominant_station_ranks_first_with_score_one():
    # A is better on every criterion -> it IS the ideal solution.
    stations = [_s("B", 5000, 12, 1), _s("A", 500, 6, 4), _s("C", 3000, 10, 2)]
    ranked = topsis_rank(stations, 0.5, False)
    assert ranked[0]["id"] == "A"
    assert ranked[0]["topsis_score"] == pytest.approx(1.0)
    assert ranked[-1]["id"] == "B"
    assert ranked[-1]["topsis_score"] == pytest.approx(0.0)


def test_scores_are_in_unit_interval_and_sorted_descending():
    stations = [_s(str(i), 1000 * (i + 1), 5 + (i % 3), i % 4) for i in range(10)]
    ranked = topsis_rank(stations, 0.3, False)
    scores = [s["topsis_score"] for s in ranked]
    assert all(0.0 <= sc <= 1.0 for sc in scores)
    assert scores == sorted(scores, reverse=True)
    assert len(ranked) == len(stations)


def test_identical_stations_get_neutral_score():
    stations = [_s("A", 1000, 8, 2), _s("B", 1000, 8, 2)]
    ranked = topsis_rank(stations, 0.5, False)
    assert {s["topsis_score"] for s in ranked} == {0.5}


def test_single_station_does_not_crash():
    ranked = topsis_rank([_s("only", 1200, 9, 1)], 0.5, False)
    assert len(ranked) == 1
    assert ranked[0]["topsis_score"] == 0.5


def test_battery_level_changes_the_winner():
    near_expensive = _s("near", 500, 20, 2)
    far_cheap = _s("far", 8000, 2, 2)
    low = topsis_rank([near_expensive, far_cheap], battery_percentage=0.05, is_available_now=False)
    high = topsis_rank([near_expensive, far_cheap], battery_percentage=0.95, is_available_now=False)
    assert low[0]["id"] == "near"   # survival mode: distance wins
    assert high[0]["id"] == "far"   # comfort mode: price wins


def test_urgent_user_never_gets_a_full_station_first():
    full_but_closest = _s("full", 100, 1, 0)
    free_but_further = _s("free", 4000, 15, 1)
    ranked = topsis_rank([full_but_closest, free_but_further], 0.5, is_available_now=True)
    assert ranked[0]["id"] == "free"
    # The penalty is applied to a copy: the caller's distance is untouched.
    assert full_but_closest["distance"] == 100
    assert next(s for s in ranked if s["id"] == "full")["distance"] == 100


def test_input_list_is_not_mutated():
    stations = [_s("A", 500, 6, 4), _s("B", 900, 3, 1)]
    snapshot = [dict(s) for s in stations]
    topsis_rank(stations, 0.5, True)
    assert stations == snapshot


def test_extra_fields_are_preserved():
    stations = [{**_s("A", 500, 6, 4), "name": "Alpha"}, _s("B", 900, 3, 1)]
    ranked = topsis_rank(stations, 0.5, False)
    assert next(s for s in ranked if s["id"] == "A")["name"] == "Alpha"
