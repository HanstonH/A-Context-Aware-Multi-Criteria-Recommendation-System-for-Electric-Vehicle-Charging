"""Unit tests for the exponential, battery-aware weight engine (logic.py Part A)."""
import numpy as np
import pytest

from logic import (
    WeightVector,
    _URGENCY_WEIGHTS,
    _context_state_label,
    get_dynamic_weights,
    get_exponential_weights,
)


@pytest.mark.parametrize("battery", [0.0, 0.05, 0.2, 0.35, 0.5, 0.8, 1.0])
def test_weights_always_sum_to_one(battery):
    weights = get_exponential_weights(battery, is_available_now=False)
    assert len(weights) == 3
    assert sum(weights) == pytest.approx(1.0)
    assert all(w >= 0 for w in weights)


def test_urgent_user_gets_fixed_override_vector():
    for battery in (0.0, 0.5, 1.0):
        assert get_exponential_weights(battery, is_available_now=True) == _URGENCY_WEIGHTS


def test_low_battery_prioritises_distance_and_free_connectors():
    w_dist, w_cost, w_pots = get_exponential_weights(0.05, is_available_now=False)
    assert w_dist > w_cost
    assert w_pots > w_cost


def test_high_battery_prioritises_cost():
    w_dist, w_cost, w_pots = get_exponential_weights(0.95, is_available_now=False)
    assert w_cost > w_dist
    assert w_cost > w_pots


def test_distance_weight_decreases_as_battery_rises():
    batteries = np.linspace(0, 1, 11)
    dist_weights = [get_exponential_weights(b, False)[0] for b in batteries]
    cost_weights = [get_exponential_weights(b, False)[1] for b in batteries]
    assert dist_weights == sorted(dist_weights, reverse=True)
    assert cost_weights == sorted(cost_weights)


@pytest.mark.parametrize("bad, clamped", [(-0.5, 0.0), (1.7, 1.0)])
def test_out_of_range_battery_is_clamped(bad, clamped):
    assert get_exponential_weights(bad, False) == get_exponential_weights(clamped, False)


def test_weight_vector_rejects_weights_not_summing_to_one():
    with pytest.raises(ValueError):
        WeightVector(w_distance=0.5, w_cost=0.5, w_pots=0.5)


def test_get_dynamic_weights_wraps_list_in_weight_vector():
    wv = get_dynamic_weights(0.3, False)
    assert isinstance(wv, WeightVector)
    np.testing.assert_allclose(wv.as_array(), get_exponential_weights(0.3, False))


@pytest.mark.parametrize(
    "battery, urgent, label",
    [
        (0.10, False, "LOW BATTERY"),
        (0.19, False, "LOW BATTERY"),
        (0.20, False, "MID BATTERY"),
        (0.49, False, "MID BATTERY"),
        (0.50, False, "HIGH BATTERY"),
        (0.90, True, "URGENT"),
    ],
)
def test_context_state_label_boundaries(battery, urgent, label):
    assert _context_state_label(battery, urgent) == label
