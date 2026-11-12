"""Tests for the vectorised TOPSIS ranker (logic.py Part B)."""
import pytest

from logic import topsis_rank


def station(sid, distance, cost, pots):
    return {"id": sid, "distance": distance, "cost": cost, "available_pots": pots}


def order(ranked):
    return [s["id"] for s in ranked]


def score(ranked, sid):
    return next(s["topsis_score"] for s in ranked if s["id"] == sid)


def test_empty_input_returns_empty_list():
    assert topsis_rank([], 0.5, False) == []


def test_dominant_station_scores_one_and_dominated_scores_zero():
    best = station("best", 100, 5.0, 4)
    worst = station("worst", 900, 12.0, 0)
    ranked = topsis_rank([worst, best], 0.5, False)
    assert order(ranked) == ["best", "worst"]
    assert score(ranked, "best") == pytest.approx(1.0)
    assert score(ranked, "worst") == pytest.approx(0.0)


def test_identical_stations_get_neutral_score():
    ranked = topsis_rank([station("a", 500, 8, 2), station("b", 500, 8, 2)], 0.5, False)
    assert [s["topsis_score"] for s in ranked] == [0.5, 0.5]


def test_single_station_gets_neutral_score():
    ranked = topsis_rank([station("only", 500, 8, 2)], 0.5, False)
    assert ranked[0]["topsis_score"] == 0.5


def test_scores_are_bounded_and_sorted_descending():
    stations = [station(str(i), 100 * (i + 1), 5 + i % 4, i % 3) for i in range(10)]
    ranked = topsis_rank(stations, 0.4, False)
    scores = [s["topsis_score"] for s in ranked]
    assert all(0.0 <= s <= 1.0 for s in scores)
    assert scores == sorted(scores, reverse=True)
    assert sorted(order(ranked)) == sorted(s["id"] for s in stations)


def test_all_zero_column_does_not_divide_by_zero():
    # Every station free (cost 0) -> cost column norm is 0.
    ranked = topsis_rank([station("a", 100, 0, 2), station("b", 200, 0, 2)], 0.9, False)
    assert order(ranked) == ["a", "b"]


def test_input_is_not_mutated_and_penalty_not_leaked():
    stations = [station("busy", 100, 8, 0), station("free", 400, 8, 2)]
    snapshot = [dict(s) for s in stations]
    ranked = topsis_rank(stations, 0.1, is_available_now=True)
    assert stations == snapshot
    # Returned dicts carry the real distance, not distance + 1e9.
    assert next(s for s in ranked if s["id"] == "busy")["distance"] == 100


def test_battery_level_changes_the_winner():
    near_pricey = station("near_pricey", 300, 15.0, 2)
    far_cheap = station("far_cheap", 3000, 5.0, 2)
    low = topsis_rank([near_pricey, far_cheap], 0.05, False)
    high = topsis_rank([near_pricey, far_cheap], 1.0, False)
    assert order(low)[0] == "near_pricey"
    assert order(high)[0] == "far_cheap"


def test_more_available_pots_wins_when_otherwise_equal():
    ranked = topsis_rank([station("few", 500, 8, 1), station("many", 500, 8, 5)], 0.1, False)
    assert order(ranked) == ["many", "few"]


def test_urgent_mode_puts_fully_occupied_station_last():
    stations = [
        station("busy_close", 50, 5.0, 0),
        station("free_a", 800, 9.0, 1),
        station("free_b", 1200, 8.0, 3),
    ]
    ranked = topsis_rank(stations, 0.1, is_available_now=True)
    assert order(ranked)[-1] == "busy_close"


def test_occupied_station_is_not_penalised_when_not_urgent():
    # Without urgency, a very close full station can still win on distance.
    stations = [station("busy_close", 50, 5.0, 0), station("free_far", 5000, 9.0, 1)]
    ranked = topsis_rank(stations, 0.05, is_available_now=False)
    assert order(ranked)[0] == "busy_close"


# ---------------------------------------------------------------------------
# Regression: the old +1e9 m "occupied" penalty wrecked distance normalisation.
# ---------------------------------------------------------------------------

NEAR_PRICEY = station("A_near_pricey", 500, 12.0, 2)
FAR_CHEAP = station("B_far_cheap", 5000, 8.0, 2)
OCCUPIED = station("C_occupied", 300, 10.0, 0)


def test_urgent_ranking_without_occupied_station_prefers_near():
    # Baseline: urgent weights are 60% distance / 5% cost, so 0.5 km beats 5 km.
    ranked = topsis_rank([NEAR_PRICEY, FAR_CHEAP], 0.1, is_available_now=True)
    assert order(ranked) == ["A_near_pricey", "B_far_cheap"]


def test_occupied_station_does_not_flip_order_of_available_ones():
    ranked = topsis_rank([NEAR_PRICEY, FAR_CHEAP, OCCUPIED], 0.1, is_available_now=True)
    available_order = [sid for sid in order(ranked) if sid != "C_occupied"]
    assert available_order == ["A_near_pricey", "B_far_cheap"]


def test_occupied_station_keeps_distance_gap_meaningful():
    near = station("near", 500, 8.0, 2)
    far = station("far", 5000, 8.0, 2)
    ranked = topsis_rank([near, far, OCCUPIED], 0.1, is_available_now=True)
    assert score(ranked, "near") - score(ranked, "far") > 0.1


def test_cheap_occupied_station_still_ranks_last_when_urgent():
    stations = [
        station("occupied_free_charging", 100, 0.0, 0),
        station("far_pricey", 8000, 20.0, 1),
        station("near", 600, 9.0, 2),
    ]
    ranked = topsis_rank(stations, 0.1, is_available_now=True)
    assert order(ranked)[-1] == "occupied_free_charging"


def test_all_stations_occupied_when_urgent_still_returns_ranking():
    stations = [station("a", 300, 9.0, 0), station("b", 900, 6.0, 0)]
    ranked = topsis_rank(stations, 0.1, is_available_now=True)
    assert sorted(order(ranked)) == ["a", "b"]
    assert all(0.0 <= s["topsis_score"] <= 1.0 for s in ranked)
