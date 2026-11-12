"""Tests for the exponential context-aware weight engine (logic.py Part A)."""
import numpy as np
import pytest

from logic import (
    WeightVector,
    _URGENCY_WEIGHTS,
    _context_state_label,
    get_dynamic_weights,
    get_exponential_weights,
)

BATTERY_LEVELS = np.linspace(0.0, 1.0, 21)


@pytest.mark.parametrize("battery", BATTERY_LEVELS)
def test_weights_sum_to_one_and_are_positive(battery):
    weights = get_exponential_weights(battery, is_available_now=False)
    assert len(weights) == 3
    assert sum(weights) == pytest.approx(1.0)
    assert all(w >= 0 for w in weights)


def test_distance_and_pots_weights_fall_as_battery_rises():
    dist = [get_exponential_weights(b, False)[0] for b in BATTERY_LEVELS]
    pots = [get_exponential_weights(b, False)[2] for b in BATTERY_LEVELS]
    assert all(np.diff(dist) < 0)
    assert all(np.diff(pots) < 0)


def test_cost_weight_rises_as_battery_rises():
    cost = [get_exponential_weights(b, False)[1] for b in BATTERY_LEVELS]
    assert all(np.diff(cost) > 0)


def test_empty_battery_ignores_cost():
    w_dist, w_cost, w_pots = get_exponential_weights(0.0, False)
    assert w_cost == 0.0
    assert w_dist > w_pots > 0


def test_full_battery_prioritises_cost():
    w_dist, w_cost, w_pots = get_exponential_weights(1.0, False)
    assert w_cost > w_dist
    assert w_cost > w_pots


@pytest.mark.parametrize("battery", [0.0, 0.15, 0.9])
def test_urgency_overrides_battery(battery):
    assert get_exponential_weights(battery, is_available_now=True) == _URGENCY_WEIGHTS


def test_urgency_vector_is_a_copy():
    get_exponential_weights(0.5, True).append(99)
    assert len(_URGENCY_WEIGHTS) == 3


@pytest.mark.parametrize("raw, clamped", [(-0.5, 0.0), (1.7, 1.0)])
def test_out_of_range_battery_is_clamped(raw, clamped):
    assert get_exponential_weights(raw, False) == get_exponential_weights(clamped, False)


def test_dynamic_weights_wraps_exponential_weights():
    wv = get_dynamic_weights(0.35, False)
    assert isinstance(wv, WeightVector)
    np.testing.assert_allclose(wv.as_array(), get_exponential_weights(0.35, False))


def test_weight_vector_rejects_bad_sum():
    with pytest.raises(ValueError):
        WeightVector(w_distance=0.5, w_cost=0.5, w_pots=0.5)


@pytest.mark.parametrize(
    "battery, urgent, label",
    [
        (0.10, False, "LOW BATTERY"),
        (0.20, False, "MID BATTERY"),
        (0.49, False, "MID BATTERY"),
        (0.50, False, "HIGH BATTERY"),
        (0.90, True, "URGENT"),
    ],
)
def test_context_state_label(battery, urgent, label):
    assert _context_state_label(battery, urgent) == label
